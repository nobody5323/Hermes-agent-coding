"""Small orchestration functions for AI Coding task loops."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import get_config
from .context_engineering import build_context_package
from .patch_generator import generate_patch_for_task_with_strategy
from .rag.retriever import retrieve_code_context
from .schemas import CodingTask, CodingTaskResult, PatchApplyResult
from .tools.patch import apply_patch_to_repo, validate_patch_against_repo
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
    apply_to_repo: bool = False,
    create_branch: bool = False,
    branch_name: str | None = None,
    allow_dirty: bool = False,
    save_artifacts: bool = False,
    artifact_dir: str | Path | None = None,
    commit: bool = False,
    commit_message: str | None = None,
    write_review: bool = False,
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
    apply_result = None
    if apply_to_repo:
        if patch_preview and patch_preview.valid and sandbox_result and sandbox_result.exit_code == 0 and patch_text:
            apply_result = apply_patch_to_repo(
                repo_path,
                patch_text,
                task_id=task.task_id,
                task=user_request,
                create_branch=create_branch,
                branch_name=branch_name,
                allow_dirty=allow_dirty,
                save_artifacts=save_artifacts,
                artifact_dir=artifact_dir,
                sandbox_result=sandbox_result,
                commit=commit,
                commit_message=commit_message,
                write_review=write_review,
            )
        else:
            apply_result = PatchApplyResult(
                applied=False,
                summary="patch was not applied because validation or sandbox verification did not pass",
                errors=["apply requires a valid patch preview and sandbox exit code 0"],
            )

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
    if apply_result:
        final_parts.append(f"Apply: applied={apply_result.applied}, {apply_result.summary}")
        if apply_result.branch_name:
            final_parts.append(f"Branch: {apply_result.branch_name}, created={apply_result.branch_created}")
        if apply_result.commit_sha:
            final_parts.append(f"Commit: {apply_result.commit_sha}")
        if apply_result.pr_summary_path:
            final_parts.append(f"PR summary: {apply_result.pr_summary_path}")
        if apply_result.test_report_path:
            final_parts.append(f"Test report: {apply_result.test_report_path}")

    return CodingTaskResult(
        task=task,
        context_package=context,
        generated_patch=generated_patch,
        patch_preview=patch_preview,
        apply_result=apply_result,
        sandbox_result=sandbox_result,
        final_summary="\n".join(final_parts),
    )


def run_coding_task_loop(
    repo_path: str | Path,
    user_request: str,
    **kwargs,
) -> CodingTaskResult:
    """Run the general task loop.

    This keeps the original bugfix loop API intact while making the entrypoint
    naming less demo-specific for real repositories.
    """

    return run_minimum_bugfix_loop(repo_path, user_request, **kwargs)
