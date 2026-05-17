"""Patch generation for the MVP demo loop."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from .llm_client import LLMClientError, OpenAICompatibleClient, load_llm_config_from_env
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
    return generate_patch_for_task_with_strategy(task, context_package, strategy="auto")


def _extract_unified_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else text
    lines = candidate.strip().splitlines()
    for index, line in enumerate(lines):
        if line.startswith("diff --git ") or line.startswith("--- "):
            return "\n".join(lines[index:]).strip() + "\n"
    return candidate.strip() + "\n"


def _line_numbered_file(path: Path, *, max_lines: int = 220) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    else:
        truncated = False
    numbered = [f"{index:>4}: {line}" for index, line in enumerate(lines, start=1)]
    if truncated:
        numbered.append(f"... truncated after {max_lines} lines ...")
    return "\n".join(numbered)


def _build_llm_file_context(context_package: ContextPackage) -> str:
    repo_root = Path(context_package.task.repo_path).resolve()
    paths: list[str] = []
    for item in context_package.retrieved_chunks:
        paths.append(item.chunk.path)
    sections: list[str] = []
    for relative_path in dict.fromkeys(paths):
        target = (repo_root / relative_path).resolve()
        if repo_root not in target.parents and target != repo_root:
            continue
        if not target.exists() or not target.is_file():
            continue
        sections.append(
            "\n".join(
                [
                    f"### {relative_path}",
                    "```text",
                    _line_numbered_file(target),
                    "```",
                ]
            )
        )
    return "\n\n".join(sections) or "No full file context available."


def _build_llm_messages(task: CodingTask, context_package: ContextPackage) -> list[dict[str, str]]:
    system = (
        "You are an AI coding patch generator. Return only a valid git-style unified diff. "
        "Do not include markdown, prose, explanations, or shell commands. "
        "Every changed file must start with `diff --git a/<path> b/<path>`, followed by "
        "`--- a/<path>` and `+++ b/<path>`. "
        "Hunk headers must use exact line numbers from the file context. "
        "Use repository-relative paths with a/ and b/ prefixes. "
        "Make the smallest safe change that satisfies the task."
    )
    user = "\n\n".join(
        [
            "Generate a unified diff for this coding task.",
            f"Task: {task.user_request}",
            "Context package:",
            context_package.markdown,
            "Full file context with line numbers:",
            _build_llm_file_context(context_package),
            "Output only the diff.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


DIFF_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
OLD_FILE_RE = re.compile(r"^---\s+(?:a/)?(.+)$")
NEW_FILE_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+)$")


def _file_path_from_diff(patch_text: str) -> str | None:
    old_path: str | None = None
    for line in patch_text.splitlines():
        diff_match = DIFF_FILE_RE.match(line)
        if diff_match and diff_match.group(1) == diff_match.group(2):
            return diff_match.group(1)
        old_match = OLD_FILE_RE.match(line)
        if old_match:
            old_path = old_match.group(1)
            continue
        new_match = NEW_FILE_RE.match(line)
        if new_match:
            new_path = new_match.group(1)
            if old_path is None or old_path == new_path:
                return new_path
    return None


def _hunk_before_after_lines(patch_text: str) -> tuple[list[str], list[str]] | None:
    before: list[str] = []
    after: list[str] = []
    in_hunk = False
    for line in patch_text.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith(("diff --git ", "--- ", "+++ ")):
            break
        if not line:
            marker = " "
            value = ""
        else:
            marker = line[0]
            value = line[1:]
        if marker == " ":
            before.append(value)
            after.append(value)
        elif marker == "-":
            before.append(value)
        elif marker == "+":
            after.append(value)
        elif marker == "\\":
            continue
        else:
            return None
    if before == after or not before:
        return None
    return before, after


def _find_subsequence(haystack: list[str], needle: list[str]) -> int:
    if not needle:
        return -1
    limit = len(haystack) - len(needle) + 1
    for index in range(max(0, limit)):
        if haystack[index : index + len(needle)] == needle:
            return index
    return -1


def _git_style_diff(relative_path: str, before: list[str], after: list[str]) -> str:
    body = "\n".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )
    return f"diff --git a/{relative_path} b/{relative_path}\n{body}\n"


def _normalize_llm_patch(patch_text: str, repo_path: str) -> str:
    relative_path = _file_path_from_diff(patch_text)
    if relative_path is None:
        return patch_text

    repo_root = Path(repo_path).resolve()
    target = (repo_root / relative_path).resolve()
    if repo_root not in target.parents and target != repo_root:
        return patch_text
    if not target.exists() or not target.is_file():
        return patch_text

    hunk = _hunk_before_after_lines(patch_text)
    if hunk is not None:
        before_hunk, after_hunk = hunk
        original = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = _find_subsequence(original, before_hunk)
        if start >= 0:
            repaired = original[:start] + after_hunk + original[start + len(before_hunk) :]
            return _git_style_diff(relative_path, original, repaired)

    if patch_text.startswith("diff --git "):
        return patch_text if patch_text.endswith("\n") else patch_text + "\n"
    return f"diff --git a/{relative_path} b/{relative_path}\n{patch_text.rstrip()}\n"


def generate_llm_patch_for_task(
    task: CodingTask,
    context_package: ContextPackage,
    *,
    client: OpenAICompatibleClient | None = None,
) -> GeneratedPatch:
    config = load_llm_config_from_env()
    if client is None:
        if config is None:
            return GeneratedPatch(
                generated=False,
                strategy="llm",
                reason="LLM patch generation skipped because no API key is configured",
                errors=["set AI_CODING_LLM_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY"],
            )
        client = OpenAICompatibleClient(config)

    try:
        content = client.complete(_build_llm_messages(task, context_package))
        patch_text = _normalize_llm_patch(_extract_unified_diff(content), task.repo_path)
        model = config.model if config else getattr(getattr(client, "config", None), "model", None)
        return GeneratedPatch(
            generated=True,
            patch_text=patch_text,
            strategy="llm",
            reason="generated unified diff from Context Package",
            model=model,
        )
    except LLMClientError as exc:
        return GeneratedPatch(generated=False, strategy="llm", reason="LLM patch generation failed", errors=[str(exc)])


def generate_rule_based_patch_for_task(task: CodingTask, context_package: ContextPackage) -> GeneratedPatch:
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


def generate_patch_for_task_with_strategy(
    task: CodingTask,
    context_package: ContextPackage,
    *,
    strategy: str = "auto",
    client: OpenAICompatibleClient | None = None,
) -> GeneratedPatch:
    if strategy not in {"auto", "llm", "rule"}:
        return GeneratedPatch(generated=False, strategy=strategy, reason="unsupported patch generation strategy")

    if strategy in {"auto", "llm"}:
        llm_patch = generate_llm_patch_for_task(task, context_package, client=client)
        if llm_patch.generated or strategy == "llm":
            return llm_patch
        llm_error = llm_patch.errors
    else:
        llm_error = []

    rule_patch = generate_rule_based_patch_for_task(task, context_package)
    if strategy == "auto" and llm_error:
        rule_patch = rule_patch.model_copy(
            update={
                "used_fallback": True,
                "errors": [f"LLM fallback reason: {'; '.join(llm_error)}", *rule_patch.errors],
            }
        )
    return rule_patch
