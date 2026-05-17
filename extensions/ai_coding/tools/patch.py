"""Patch preview and validation helpers."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..schemas import PatchApplyResult, PatchFileChange, PatchPreview


DIFF_HEADER_RE = re.compile(r"^\+\+\+\s+b/(.+)$")
OLD_HEADER_RE = re.compile(r"^---\s+a/(.+)$")


def _git_env_for_repo(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    return env


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


def apply_patch_to_repo(repo_path: str | Path, patch_text: str) -> PatchApplyResult:
    root = Path(repo_path).resolve()
    preview = validate_patch_against_repo(root, patch_text)
    if not preview.valid:
        return PatchApplyResult(
            applied=False,
            files=preview.files,
            summary="patch was not applied because validation failed",
            errors=preview.errors,
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
        )

    return PatchApplyResult(
        applied=True,
        files=preview.files,
        summary=f"applied patch: {preview.summary}",
    )
