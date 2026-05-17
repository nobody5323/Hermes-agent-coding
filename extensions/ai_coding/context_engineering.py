"""Context package assembly for the local AI Coding MVP."""

from __future__ import annotations

from .config import get_config
from .schemas import CodingTask, ContextPackage, RepositorySummary, RetrievedChunk


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context_package(
    task: CodingTask,
    repository: RepositorySummary,
    retrieved_chunks: list[RetrievedChunk],
    *,
    token_budget: int | None = None,
) -> ContextPackage:
    token_budget = token_budget or get_config().default_token_budget
    ordered = sorted(retrieved_chunks, key=lambda item: item.score, reverse=True)
    selected: list[RetrievedChunk] = []
    used_ranges: set[tuple[str, int, int]] = set()

    header = [
        "# Context Package",
        "",
        "## Task",
        task.user_request,
        "",
        "## Repository Summary",
        f"- Files: {repository.total_files}",
        f"- Languages: {repository.languages}",
        f"- Dependency files: {repository.dependency_files}",
        f"- Test commands: {repository.test_commands}",
        "",
        "## Relevant Chunks",
    ]
    markdown_parts = ["\n".join(header)]
    current_tokens = estimate_tokens(markdown_parts[0])

    for item in ordered:
        chunk = item.chunk
        key = (chunk.path, chunk.start_line, chunk.end_line)
        if key in used_ranges:
            continue
        block = "\n".join(
            [
                f"### {chunk.path}:{chunk.start_line}-{chunk.end_line}",
                f"- Score: {item.score}",
                f"- Reason: {'; '.join(item.reasons) or 'selected by retriever'}",
                "```" + chunk.language,
                chunk.content,
                "```",
            ]
        )
        block_tokens = estimate_tokens(block)
        if current_tokens + block_tokens > token_budget:
            continue
        selected.append(item)
        used_ranges.add(key)
        markdown_parts.append(block)
        current_tokens += block_tokens

    markdown = "\n\n".join(markdown_parts)
    return ContextPackage(
        task=task,
        repository=repository,
        retrieved_chunks=selected,
        token_budget=token_budget,
        token_estimate=estimate_tokens(markdown),
        markdown=markdown,
    )
