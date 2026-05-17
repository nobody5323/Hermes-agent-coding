"""Tool wrapper for sandbox verification."""

from __future__ import annotations

from pathlib import Path

from ..schemas import SandboxResult
from ..sandbox.runner import run_in_copied_repo, run_in_docker


def run_pytest_sandbox(repo_path: str | Path, patch_text: str | None = None) -> SandboxResult:
    return run_in_copied_repo(repo_path, "python -m pytest", patch_text=patch_text)


def run_pytest_docker_sandbox(
    repo_path: str | Path,
    patch_text: str | None = None,
    *,
    image: str | None = None,
) -> SandboxResult:
    return run_in_docker(repo_path, "python -m pytest", patch_text=patch_text, image=image)
