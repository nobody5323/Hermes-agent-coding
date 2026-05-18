"""Small repository-local lessons store for AI Coding runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .rag.embeddings import tokenize
from .schemas import MemoryLesson, PatchPreview


def lessons_path(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / ".ai-coding" / "memory" / "lessons.jsonl"


def load_lessons(repo_path: str | Path, *, limit: int = 50) -> list[MemoryLesson]:
    path = lessons_path(repo_path)
    if not path.exists():
        return []
    lessons: list[MemoryLesson] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            lessons.append(MemoryLesson.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError):
            continue
    return lessons[-limit:]


def retrieve_lessons(repo_path: str | Path, query: str, *, top_k: int = 3) -> list[MemoryLesson]:
    query_tokens = set(tokenize(query))
    scored: list[tuple[float, MemoryLesson]] = []
    for lesson in load_lessons(repo_path):
        text = " ".join([lesson.task, lesson.summary, " ".join(lesson.files), lesson.outcome])
        lesson_tokens = set(tokenize(text))
        overlap = query_tokens & lesson_tokens
        score = len(overlap) / max(1, len(query_tokens))
        if score > 0:
            scored.append((score, lesson))
    return [lesson for _, lesson in sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]]


def write_lesson(
    repo_path: str | Path,
    *,
    task: str,
    summary: str,
    patch_preview: PatchPreview | None = None,
    outcome: str = "success",
) -> MemoryLesson:
    lesson = MemoryLesson(
        task=task,
        summary=summary,
        files=[item.path for item in patch_preview.files] if patch_preview else [],
        outcome=outcome,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    path = lessons_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(lesson.model_dump(), ensure_ascii=False) + "\n")
    return lesson
