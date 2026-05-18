"""Small orchestration functions for AI Coding task loops."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import get_config
from .context_engineering import build_context_package
from .memory import retrieve_lessons, write_lesson
from .patch_generator import generate_patch_for_task_with_strategy
from .rag.retriever import retrieve_code_context
from .schemas import CodingTask, CodingTaskResult, PatchApplyResult, RepairIteration, SandboxResult
from .tools.patch import apply_patch_to_repo, validate_patch_against_repo
from .tools.repository import scan_repository
from .tools.sandbox import run_pytest_docker_sandbox, run_pytest_sandbox


def _task_id(user_request: str, repo_path: str | Path) -> str:
    raw = f"{Path(repo_path).resolve()}:{user_request}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def _run_sandbox(repo_path: str | Path, patch_text: str, sandbox_backend: str) -> SandboxResult:
    if sandbox_backend == "docker":
        return run_pytest_docker_sandbox(repo_path, patch_text=patch_text)
    if sandbox_backend == "local":
        return run_pytest_sandbox(repo_path, patch_text=patch_text)
    raise ValueError(f"unsupported sandbox backend: {sandbox_backend}")


def _failure_feedback(errors: list[str], sandbox_result: SandboxResult | None) -> str:
    parts = list(errors)
    if sandbox_result:
        parts.extend([sandbox_result.summary, sandbox_result.stdout[-2000:], sandbox_result.stderr[-2000:]])
    return "\n".join(part for part in parts if part)


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
    max_repair_attempts: int = 0,
    use_memory: bool = True,
    write_memory: bool = False,
) -> CodingTaskResult:
    task = CodingTask(
        task_id=_task_id(user_request, repo_path),
        user_request=user_request,
        repo_path=str(Path(repo_path).resolve()),
        task_type="bugfix",
    )
    repository = scan_repository(repo_path)
    lessons = retrieve_lessons(repo_path, user_request) if use_memory else []
    lesson_texts = [f"{lesson.task} {lesson.summary} {' '.join(lesson.files)}" for lesson in lessons]
    attempts = 1 if patch_text is not None else max(1, max_repair_attempts + 1)
    repair_iterations: list[RepairIteration] = []
    generated_patch = None
    patch_preview = None
    sandbox_result = None
    context = None
    failure_feedback = ""
    working_patch_text = patch_text

    for attempt in range(1, attempts + 1):
        query = user_request if not failure_feedback else f"{user_request}\n\nPrevious failure:\n{failure_feedback}"
        retrieved = retrieve_code_context(
            repo_path,
            query,
            project_id=project_id,
            top_k=get_config().default_top_k,
            feedback=failure_feedback,
            lessons=lesson_texts,
        )
        context = build_context_package(task, repository, retrieved, lessons=lessons)
        if patch_text is None:
            generated_patch = generate_patch_for_task_with_strategy(task, context, strategy=patch_generator)
            working_patch_text = generated_patch.patch_text if generated_patch.generated else None

        patch_preview = validate_patch_against_repo(repo_path, working_patch_text) if working_patch_text else None
        sandbox_result = None
        if patch_preview and patch_preview.valid and working_patch_text:
            sandbox_result = _run_sandbox(repo_path, working_patch_text, sandbox_backend)

        errors = []
        if generated_patch and generated_patch.errors and not generated_patch.generated:
            errors.extend(generated_patch.errors)
        if patch_preview and patch_preview.errors:
            errors.extend(patch_preview.errors)
        repair_iterations.append(
            RepairIteration(
                attempt=attempt,
                query=query,
                patch_generated=bool(working_patch_text),
                patch_valid=bool(patch_preview and patch_preview.valid),
                sandbox_exit_code=sandbox_result.exit_code if sandbox_result else None,
                summary=sandbox_result.summary if sandbox_result else "sandbox not run",
                errors=errors,
            )
        )

        if patch_preview and patch_preview.valid and sandbox_result and sandbox_result.exit_code == 0:
            break
        if patch_text is not None or attempt >= attempts:
            break
        failure_feedback = _failure_feedback(errors, sandbox_result)

    if context is None:
        retrieved = retrieve_code_context(repo_path, user_request, project_id=project_id, top_k=get_config().default_top_k)
        context = build_context_package(task, repository, retrieved, lessons=lessons)

    apply_result = None
    if apply_to_repo:
        if patch_preview and patch_preview.valid and sandbox_result and sandbox_result.exit_code == 0 and working_patch_text:
            apply_result = apply_patch_to_repo(
                repo_path,
                working_patch_text,
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
    memory_written = False
    if write_memory and patch_preview and patch_preview.valid and sandbox_result and sandbox_result.exit_code == 0:
        write_lesson(
            repo_path,
            task=user_request,
            summary=f"Successful patch: {patch_preview.summary}; sandbox: {sandbox_result.summary}",
            patch_preview=patch_preview,
        )
        memory_written = True

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
    if repair_iterations:
        final_parts.append(f"Repair iterations: {len(repair_iterations)}")
    if lessons:
        final_parts.append(f"Memory lessons used: {len(lessons)}")
    if memory_written:
        final_parts.append("Memory: wrote lesson")
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
        repair_iterations=repair_iterations,
        memory_lessons=lessons,
        memory_written=memory_written,
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
