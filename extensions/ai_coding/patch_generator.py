"""Conservative rule-based patch generation for the MVP demo loop."""

from __future__ import annotations

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


def _build_llm_messages(task: CodingTask, context_package: ContextPackage) -> list[dict[str, str]]:
    system = (
        "You are an AI coding patch generator. Return only a valid unified diff. "
        "Do not include markdown, prose, explanations, or shell commands. "
        "Use repository-relative paths with a/ and b/ prefixes. "
        "Make the smallest safe change that satisfies the task."
    )
    user = "\n\n".join(
        [
            "Generate a unified diff for this coding task.",
            f"Task: {task.user_request}",
            "Context package:",
            context_package.markdown,
            "Output only the diff.",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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
        patch_text = _extract_unified_diff(content)
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
