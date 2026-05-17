"""A small orchestration function for the minimum bug-fix loop."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import get_config
from .context_engineering import build_context_package
from .patch_generator import generate_patch_for_task_with_strategy
from .rag.retriever import retrieve_code_context
from .schemas import CodingTask, CodingTaskResult
from .tools.patch import validate_patch_against_repo
from .tools.repository import scan_repository
from .tools.sandbox import run_pytest_docker_sandbox, run_pytest_sandbox


def _task_id(user_request: str, repo_path: str | Path) -> str:
    raw = f"{Path(repo_path).resolve()}:{user_request}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def run_minimum_bugfix_loop(
    repo_path: str | Path,
    user_request: str,
    *,
    patch_text: str | None = None,
    project_id: str = "demo",
    sandbox_backend: str = "local",
    patch_generator: str = "auto",
) -> CodingTaskResult:
    task = CodingTask(
        task_id=_task_id(user_request, repo_path),
        user_request=user_request,
        repo_path=str(Path(repo_path).resolve()),
        task_type="bugfix",
    )
    repository = scan_repository(repo_path)
    retrieved = retrieve_code_context(repo_path, user_request, project_id=project_id, top_k=get_config().default_top_k)
    context = build_context_package(task, repository, retrieved)
    generated_patch = None
    if patch_text is None:
        generated_patch = generate_patch_for_task_with_strategy(task, context, strategy=patch_generator)
        if generated_patch.generated:
            patch_text = generated_patch.patch_text
    patch_preview = validate_patch_against_repo(repo_path, patch_text) if patch_text else None
    sandbox_result = None
    if patch_preview and patch_preview.valid:
        if sandbox_backend == "docker":
            sandbox_result = run_pytest_docker_sandbox(repo_path, patch_text=patch_text)
        elif sandbox_backend == "local":
            sandbox_result = run_pytest_sandbox(repo_path, patch_text=patch_text)
        else:
            raise ValueError(f"unsupported sandbox backend: {sandbox_backend}")

    final_parts = [
        f"Task {task.task_id}: {task.task_type}",
        f"Repository files scanned: {repository.total_files}",
        f"Context chunks selected: {len(context.retrieved_chunks)}",
    ]
    if patch_preview:
        final_parts.append(f"Patch preview: {patch_preview.summary}, valid={patch_preview.valid}")
    if generated_patch:
        final_parts.append(f"Patch generator: generated={generated_patch.generated}, strategy={generated_patch.strategy}")
    if sandbox_result:
        final_parts.append(f"Sandbox: exit={sandbox_result.exit_code}, {sandbox_result.summary}")

    return CodingTaskResult(
        task=task,
        context_package=context,
        generated_patch=generated_patch,
        patch_preview=patch_preview,
        sandbox_result=sandbox_result,
        final_summary="\n".join(final_parts),
    )
