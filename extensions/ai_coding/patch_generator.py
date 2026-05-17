"""Conservative rule-based patch generation for the MVP demo loop."""

from __future__ import annotations

from pathlib import Path

from .schemas import CodingTask, ContextPackage, GeneratedPatch


EMPTY_PASSWORD_OLD = '        raise ValueError("empty password")'
EMPTY_PASSWORD_NEW = "        return False"


def _mentions_empty_password_bug(text: str) -> bool:
    lowered = text.lower()
    return (
        ("empty password" in lowered or "空密码" in text)
        and ("return false" in lowered or "返回 false" in lowered or "返回 False" in text)
    )


def _unified_single_line_patch(path: str, lines: list[str], line_index: int, new_line: str) -> str:
    start = max(0, line_index - 2)
    end = min(len(lines), line_index + 3)
    old_count = end - start
    new_count = old_count
    hunk_lines: list[str] = []
    for index in range(start, end):
        line = lines[index]
        if index == line_index:
            hunk_lines.append(f"-{line}")
            hunk_lines.append(f"+{new_line}")
        else:
            hunk_lines.append(f" {line}")
    hunk = "\n".join(hunk_lines)
    return "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            f"--- a/{path}",
            f"+++ b/{path}",
            f"@@ -{start + 1},{old_count} +{start + 1},{new_count} @@",
            hunk,
            "",
        ]
    )


def generate_patch_for_task(task: CodingTask, context_package: ContextPackage) -> GeneratedPatch:
    """Generate a patch for known low-risk demo tasks.

    This is intentionally narrow: it proves the agent loop can create a patch
    without pretending to be a general code-generation system.
    """

    if not _mentions_empty_password_bug(task.user_request):
        return GeneratedPatch(
            generated=False,
            strategy="rule_based_demo",
            reason="no rule matched the task request",
            errors=["supported demo rule requires empty password returning False"],
        )

    repo_root = Path(task.repo_path)
    candidate_paths = ["src/user_service.py"]
    candidate_paths.extend(
        item.chunk.path
        for item in context_package.retrieved_chunks
        if item.chunk.path.endswith("user_service.py")
    )

    for relative_path in dict.fromkeys(candidate_paths):
        target = repo_root / relative_path
        if not target.exists():
            continue
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if line == EMPTY_PASSWORD_OLD:
                patch_text = _unified_single_line_patch(relative_path, lines, index, EMPTY_PASSWORD_NEW)
                return GeneratedPatch(
                    generated=True,
                    patch_text=patch_text,
                    strategy="rule_based_empty_password",
                    target_file=relative_path,
                    reason="matched empty-password ValueError and task asks to return False",
                )

    return GeneratedPatch(
        generated=False,
        strategy="rule_based_empty_password",
        reason="target pattern was not found",
        errors=[f"could not find `{EMPTY_PASSWORD_OLD.strip()}` in user_service.py"],
    )
