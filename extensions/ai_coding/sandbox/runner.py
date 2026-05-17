"""Run verification commands in isolated repository copies or Docker."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ..config import get_config
from ..schemas import SandboxResult
from .policy import is_dangerous_command, validate_mount_path


def find_docker_cli() -> str | None:
    docker = shutil.which("docker")
    if docker:
        return docker
    common_paths = [
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        Path("C:/Program Files/Docker/Docker/docker.exe"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    return None


def _copy_repo(source: Path, destination: Path) -> None:
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
    shutil.copytree(source, destination, ignore=ignore)


def _apply_patch(copied: Path, patch_text: str, temp_dir: str | Path, timeout_seconds: int) -> SandboxResult | None:
    patch_file = Path(temp_dir) / "change.diff"
    patch_file.write_text(patch_text, encoding="utf-8")
    apply_process = subprocess.run(
        ["git", "apply", "--ignore-whitespace", str(patch_file)],
        cwd=copied,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    if apply_process.returncode != 0:
        return SandboxResult(
            command="git apply",
            exit_code=apply_process.returncode,
            stdout=apply_process.stdout,
            stderr=apply_process.stderr,
            summary="patch failed to apply in copied repository",
            copied_repo_path=str(copied),
        )
    return None


def _summarize_failure(stdout: str, stderr: str, exit_code: int) -> str:
    if exit_code == 0:
        return "command succeeded"
    combined = (stderr or stdout).splitlines()
    interesting = [
        line
        for line in combined
        if "failed" in line.lower() or "error" in line.lower() or "traceback" in line.lower() or "assert" in line.lower()
    ]
    tail = interesting[-8:] if interesting else combined[-8:]
    return "\n".join(tail) if tail else f"command failed with exit code {exit_code}"


def run_in_copied_repo(
    repo_path: str | Path,
    command: str,
    *,
    patch_text: str | None = None,
    timeout_seconds: int | None = None,
) -> SandboxResult:
    if is_dangerous_command(command):
        return SandboxResult(command=command, exit_code=126, rejected=True, summary="command rejected by sandbox policy")
    source = Path(repo_path).resolve()
    if not validate_mount_path(source):
        return SandboxResult(command=command, exit_code=126, rejected=True, summary="repository path rejected by sandbox policy")
    timeout_seconds = timeout_seconds or get_config().sandbox_timeout_seconds

    with tempfile.TemporaryDirectory(prefix="ai-coding-sandbox-") as temp_dir:
        copied = Path(temp_dir) / "repo"
        _copy_repo(source, copied)
        if patch_text:
            patch_result = _apply_patch(copied, patch_text, temp_dir, timeout_seconds)
            if patch_result:
                return patch_result.model_copy(update={"command": f"git apply && {command}"})

        started = time.perf_counter()
        try:
            process = subprocess.run(
                command,
                cwd=copied,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return SandboxResult(
                command=command,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=duration_ms,
                summary=_summarize_failure(process.stdout, process.stderr, process.returncode),
                copied_repo_path=str(copied),
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return SandboxResult(
                command=command,
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_ms=duration_ms,
                summary=f"command timed out after {timeout_seconds}s",
                copied_repo_path=str(copied),
            )


def build_docker_run_command(
    copied_repo_path: str | Path,
    command: str,
    *,
    image: str | None = None,
) -> list[str]:
    config = get_config()
    image = image or config.docker_image
    copied = Path(copied_repo_path).resolve()
    return [
        find_docker_cli() or "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        "512m",
        "-v",
        f"{copied.as_posix()}:{config.docker_workdir}",
        "-w",
        config.docker_workdir,
        image,
        "/bin/sh",
        "-lc",
        command,
    ]


def run_in_docker(
    repo_path: str | Path,
    command: str,
    *,
    patch_text: str | None = None,
    image: str | None = None,
    timeout_seconds: int | None = None,
) -> SandboxResult:
    if is_dangerous_command(command):
        return SandboxResult(command=command, exit_code=126, rejected=True, summary="command rejected by sandbox policy")
    source = Path(repo_path).resolve()
    if not validate_mount_path(source):
        return SandboxResult(command=command, exit_code=126, rejected=True, summary="repository path rejected by sandbox policy")
    if find_docker_cli() is None:
        return SandboxResult(
            command=command,
            exit_code=127,
            rejected=True,
            summary="docker CLI is not installed or not on PATH",
        )
    timeout_seconds = timeout_seconds or get_config().sandbox_timeout_seconds

    with tempfile.TemporaryDirectory(prefix="ai-coding-docker-") as temp_dir:
        copied = Path(temp_dir) / "repo"
        _copy_repo(source, copied)
        if patch_text:
            patch_result = _apply_patch(copied, patch_text, temp_dir, timeout_seconds)
            if patch_result:
                return patch_result.model_copy(update={"command": f"git apply && docker run {command}"})

        docker_command = build_docker_run_command(copied, command, image=image)
        started = time.perf_counter()
        try:
            process = subprocess.run(
                docker_command,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            command_text = " ".join(docker_command)
            return SandboxResult(
                command=command_text,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=duration_ms,
                summary=_summarize_failure(process.stdout, process.stderr, process.returncode),
                copied_repo_path=str(copied),
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return SandboxResult(
                command=" ".join(docker_command),
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_ms=duration_ms,
                summary=f"docker command timed out after {timeout_seconds}s",
                copied_repo_path=str(copied),
            )
