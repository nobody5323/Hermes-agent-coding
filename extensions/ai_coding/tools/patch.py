"""Patch preview and validation helpers."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import PatchApplyResult, PatchFileChange, PatchPreview, SandboxResult


DIFF_HEADER_RE = re.compile(r"^\+\+\+\s+b/(.+)$")
OLD_HEADER_RE = re.compile(r"^---\s+a/(.+)$")


def _git_env_for_repo(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    return env


def _run_git(root: Path, args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=_git_env_for_repo(root),
    )


def _is_git_repo(root: Path) -> bool:
    process = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return process.returncode == 0 and process.stdout.strip() == "true"


def _current_branch(root: Path) -> str | None:
    process = _run_git(root, ["branch", "--show-current"])
    branch = process.stdout.strip()
    return branch or None


def _dirty_files(root: Path) -> list[str]:
    process = _run_git(root, ["status", "--porcelain", "--untracked-files=all"])
    if process.returncode != 0:
        return []
    return [line for line in process.stdout.splitlines() if line.strip()]


def _safe_task_slug(task_id: str | None) -> str:
    raw = task_id or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-") or "task"


def _artifact_dir(root: Path, task_id: str | None, artifact_dir: str | Path | None) -> Path:
    if artifact_dir:
        path = Path(artifact_dir)
        return path if path.is_absolute() else root / path
    return root / ".ai-coding" / "runs" / _safe_task_slug(task_id)


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve())


def _write_artifacts(
    *,
    root: Path,
    patch_text: str,
    task_id: str | None,
    task: str | None,
    patch_preview: PatchPreview,
    sandbox_result: SandboxResult | None,
    artifact_dir: str | Path | None,
    write_review: bool,
) -> tuple[str | None, str | None, str | None]:
    target_dir = _artifact_dir(root, task_id, artifact_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    patch_path = target_dir / "change.diff"
    patch_path.write_text(patch_text, encoding="utf-8", newline="\n")

    test_report_path: Path | None = None
    pr_summary_path: Path | None = None
    if write_review:
        test_report_path = target_dir / "test_report.md"
        test_report = [
            "# Test Report",
            "",
            f"- Task: {task or task_id or 'coding task'}",
            f"- Patch: {patch_preview.summary}",
        ]
        if sandbox_result:
            test_report.extend(
                [
                    f"- Command: `{sandbox_result.command}`",
                    f"- Exit code: {sandbox_result.exit_code}",
                    f"- Summary: {sandbox_result.summary}",
                    "",
                    "## Stdout",
                    "```text",
                    sandbox_result.stdout[-4000:],
                    "```",
                    "",
                    "## Stderr",
                    "```text",
                    sandbox_result.stderr[-4000:],
                    "```",
                ]
            )
        test_report_path.write_text("\n".join(test_report) + "\n", encoding="utf-8", newline="\n")

        changed = "\n".join(f"- `{item.path}` (+{item.additions}/-{item.deletions})" for item in patch_preview.files)
        pr_summary_path = target_dir / "pr_summary.md"
        pr_summary = [
            "# PR Summary",
            "",
            "## Summary",
            f"- {task or 'Apply AI-generated coding patch.'}",
            "",
            "## Changed Files",
            changed or "- No changed files detected.",
            "",
            "## Verification",
            f"- Patch validation: {patch_preview.summary}, valid={patch_preview.valid}",
        ]
        if sandbox_result:
            pr_summary.append(f"- Sandbox: exit={sandbox_result.exit_code}, {sandbox_result.summary}")
        pr_summary_path.write_text("\n".join(pr_summary) + "\n", encoding="utf-8", newline="\n")

    return (
        _relative_or_absolute(root, patch_path),
        _relative_or_absolute(root, test_report_path) if test_report_path else None,
        _relative_or_absolute(root, pr_summary_path) if pr_summary_path else None,
    )


def _create_branch(root: Path, branch_name: str) -> tuple[bool, str | None]:
    process = _run_git(root, ["switch", "-c", branch_name])
    if process.returncode == 0:
        return True, None
    return False, (process.stderr or process.stdout or "failed to create branch").strip()


def _rollback_patch(root: Path, patch_text: str) -> bool:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", suffix=".diff", delete=False) as handle:
        handle.write(patch_text)
        patch_file = Path(handle.name)
    try:
        process = _run_git(root, ["apply", "-R", str(patch_file)])
        return process.returncode == 0
    finally:
        patch_file.unlink(missing_ok=True)


def _commit_changes(root: Path, paths: list[str], message: str) -> tuple[str | None, str | None]:
    add_process = _run_git(root, ["add", "--", *paths])
    if add_process.returncode != 0:
        return None, (add_process.stderr or add_process.stdout or "git add failed").strip()
    commit_process = _run_git(root, ["commit", "-m", message], timeout=30)
    if commit_process.returncode != 0:
        return None, (commit_process.stderr or commit_process.stdout or "git commit failed").strip()
    rev = _run_git(root, ["rev-parse", "HEAD"])
    if rev.returncode != 0:
        return None, (rev.stderr or rev.stdout or "commit created but HEAD could not be read").strip()
    return rev.stdout.strip(), None


def preview_patch(patch_text: str) -> PatchPreview:
    errors: list[str] = []
    changes: dict[str, PatchFileChange] = {}
    current_path: str | None = None
    saw_hunk = False
    old_headers: set[str] = set()

    for line in patch_text.splitlines():
        old_match = OLD_HEADER_RE.match(line)
        if old_match:
            old_headers.add(old_match.group(1))
            continue
        new_match = DIFF_HEADER_RE.match(line)
        if new_match:
            current_path = new_match.group(1)
            changes.setdefault(current_path, PatchFileChange(path=current_path))
            continue
        if line.startswith("@@"):
            saw_hunk = True
            if current_path is None:
                errors.append("hunk appears before file header")
            continue
        if current_path is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changes[current_path].additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            changes[current_path].deletions += 1

    if not changes:
        errors.append("no changed files found in unified diff")
    if not saw_hunk:
        errors.append("no diff hunk found")
    for path in changes:
        if path.startswith("../") or Path(path).is_absolute():
            errors.append(f"patch path escapes repository: {path}")

    files = list(changes.values())
    additions = sum(item.additions for item in files)
    deletions = sum(item.deletions for item in files)
    summary = f"{len(files)} file(s), +{additions}/-{deletions}"
    return PatchPreview(
        valid=not errors,
        files=files,
        additions=additions,
        deletions=deletions,
        errors=errors,
        summary=summary,
        patch_text=patch_text,
    )


def validate_patch_against_repo(repo_path: str | Path, patch_text: str) -> PatchPreview:
    root = Path(repo_path).resolve()
    preview = preview_patch(patch_text)
    errors = list(preview.errors)
    for change in preview.files:
        target = (root / change.path).resolve()
        if root not in target.parents and target != root:
            errors.append(f"patch path escapes repository: {change.path}")
        if not target.exists():
            errors.append(f"target file does not exist: {change.path}")
    if not errors:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", suffix=".diff", delete=False) as handle:
            handle.write(patch_text)
            patch_file = Path(handle.name)
        try:
            check = subprocess.run(
                ["git", "apply", "--ignore-whitespace", "--check", str(patch_file)],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=10,
                env=_git_env_for_repo(root),
            )
            if check.returncode != 0:
                errors.append((check.stderr or check.stdout or "patch does not apply").strip())
        finally:
            patch_file.unlink(missing_ok=True)
    return preview.model_copy(update={"valid": not errors, "errors": errors})


def apply_patch_to_repo(
    repo_path: str | Path,
    patch_text: str,
    *,
    task_id: str | None = None,
    task: str | None = None,
    create_branch: bool = False,
    branch_name: str | None = None,
    allow_dirty: bool = False,
    save_artifacts: bool = False,
    artifact_dir: str | Path | None = None,
    sandbox_result: SandboxResult | None = None,
    commit: bool = False,
    commit_message: str | None = None,
    write_review: bool = False,
    rollback_on_failure: bool = True,
) -> PatchApplyResult:
    root = Path(repo_path).resolve()
    preview = validate_patch_against_repo(root, patch_text)
    git_repo = _is_git_repo(root)
    original_branch = _current_branch(root) if git_repo else None
    if not preview.valid:
        return PatchApplyResult(
            applied=False,
            files=preview.files,
            summary="patch was not applied because validation failed",
            errors=preview.errors,
            git_repo=git_repo,
            original_branch=original_branch,
        )
    if git_repo and not allow_dirty:
        dirty = _dirty_files(root)
        if dirty:
            return PatchApplyResult(
                applied=False,
                files=preview.files,
                summary="patch was not applied because the git worktree is dirty",
                errors=["commit, stash, or pass allow_dirty=true before applying"],
                git_repo=True,
                original_branch=original_branch,
                dirty_files=dirty,
            )

    branch_created = False
    actual_branch = branch_name
    if git_repo and create_branch:
        actual_branch = branch_name or f"ai-coding/{_safe_task_slug(task_id)}"
        branch_created, error = _create_branch(root, actual_branch)
        if error:
            return PatchApplyResult(
                applied=False,
                files=preview.files,
                summary="patch was not applied because branch creation failed",
                errors=[error],
                git_repo=True,
                original_branch=original_branch,
                branch_name=actual_branch,
            )

    patch_artifact_path = None
    test_report_path = None
    pr_summary_path = None
    if save_artifacts or write_review:
        patch_artifact_path, test_report_path, pr_summary_path = _write_artifacts(
            root=root,
            patch_text=patch_text,
            task_id=task_id,
            task=task,
            patch_preview=preview,
            sandbox_result=sandbox_result,
            artifact_dir=artifact_dir,
            write_review=write_review,
        )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", suffix=".diff", delete=False) as handle:
        handle.write(patch_text)
        patch_file = Path(handle.name)
    try:
        process = subprocess.run(
            ["git", "apply", str(patch_file)],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            env=_git_env_for_repo(root),
        )
    finally:
        patch_file.unlink(missing_ok=True)

    if process.returncode != 0:
        return PatchApplyResult(
            applied=False,
            files=preview.files,
            summary="git apply failed",
            errors=[(process.stderr or process.stdout or "patch failed to apply").strip()],
            git_repo=git_repo,
            original_branch=original_branch,
            branch_name=actual_branch,
            branch_created=branch_created,
            patch_artifact_path=patch_artifact_path,
            test_report_path=test_report_path,
            pr_summary_path=pr_summary_path,
        )

    commit_sha = None
    errors: list[str] = []
    rolled_back = False
    if commit:
        if not git_repo:
            errors.append("commit requested but target is not a git repository")
        else:
            artifact_paths = [path for path in [patch_artifact_path, test_report_path, pr_summary_path] if path]
            commit_paths = [item.path for item in preview.files] + artifact_paths
            commit_sha, error = _commit_changes(root, commit_paths, commit_message or f"AI coding task: {task or task_id or 'update'}")
            if error:
                errors.append(error)
                if rollback_on_failure:
                    rolled_back = _rollback_patch(root, patch_text)

    if errors:
        return PatchApplyResult(
            applied=False,
            files=preview.files,
            summary="patch was applied but a post-apply step failed",
            errors=errors,
            git_repo=git_repo,
            original_branch=original_branch,
            branch_name=actual_branch,
            branch_created=branch_created,
            patch_artifact_path=patch_artifact_path,
            test_report_path=test_report_path,
            pr_summary_path=pr_summary_path,
            commit_sha=commit_sha,
            rolled_back=rolled_back,
        )

    return PatchApplyResult(
        applied=True,
        files=preview.files,
        summary=f"applied patch: {preview.summary}",
        git_repo=git_repo,
        original_branch=original_branch,
        branch_name=actual_branch,
        branch_created=branch_created,
        patch_artifact_path=patch_artifact_path,
        test_report_path=test_report_path,
        pr_summary_path=pr_summary_path,
        commit_sha=commit_sha,
    )
