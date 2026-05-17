"""Code chunking for the local AI Coding MVP."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ..schemas import CodeChunk
from ..tools.repository import LANGUAGE_BY_EXTENSION, _classify_file


def _chunk_id(project_id: str, rel_path: str, start: int, end: int) -> str:
    raw = f"{project_id}:{rel_path}:{start}:{end}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _make_chunk(
    *,
    project_id: str,
    rel_path: str,
    language: str,
    file_type: str,
    start: int,
    end: int,
    symbol_name: str | None,
    lines: list[str],
) -> CodeChunk:
    content = "\n".join(lines[start - 1 : end])
    return CodeChunk(
        chunk_id=_chunk_id(project_id, rel_path, start, end),
        project_id=project_id,
        path=rel_path,
        language=language,
        file_type=file_type,
        start_line=start,
        end_line=end,
        symbol_name=symbol_name,
        content=content,
    )


def _sliding_chunks(
    path: Path,
    *,
    repo_path: Path,
    project_id: str,
    max_lines: int = 80,
    overlap: int = 10,
) -> list[CodeChunk]:
    rel_path = path.relative_to(repo_path).as_posix()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    language = LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "text")
    file_type = _classify_file(path.relative_to(repo_path))
    chunks: list[CodeChunk] = []
    step = max(1, max_lines - overlap)
    for start_index in range(0, len(lines), step):
        start = start_index + 1
        end = min(len(lines), start_index + max_lines)
        chunks.append(
            _make_chunk(
                project_id=project_id,
                rel_path=rel_path,
                language=language,
                file_type=file_type,
                start=start,
                end=end,
                symbol_name=None,
                lines=lines,
            )
        )
        if end == len(lines):
            break
    return chunks


def _python_chunks(path: Path, *, repo_path: Path, project_id: str) -> list[CodeChunk]:
    rel_path = path.relative_to(repo_path).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _sliding_chunks(path, repo_path=repo_path, project_id=project_id)

    chunks: list[CodeChunk] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            chunks.append(
                _make_chunk(
                    project_id=project_id,
                    rel_path=rel_path,
                    language="python",
                    file_type=_classify_file(path.relative_to(repo_path)),
                    start=start,
                    end=end,
                    symbol_name=node.name,
                    lines=lines,
                )
            )

    if chunks:
        first_symbol_line = min(chunk.start_line for chunk in chunks)
        if first_symbol_line > 1:
            chunks.insert(
                0,
                _make_chunk(
                    project_id=project_id,
                    rel_path=rel_path,
                    language="python",
                    file_type=_classify_file(path.relative_to(repo_path)),
                    start=1,
                    end=first_symbol_line - 1,
                    symbol_name="module_preamble",
                    lines=lines,
                ),
            )
        return [chunk for chunk in chunks if chunk.content.strip()]
    return _sliding_chunks(path, repo_path=repo_path, project_id=project_id)


def chunk_file(path: str | Path, *, repo_path: str | Path | None = None, project_id: str = "default") -> list[CodeChunk]:
    source = Path(path).resolve()
    root = Path(repo_path).resolve() if repo_path else source.parent
    if source.suffix.lower() == ".py":
        return _python_chunks(source, repo_path=root, project_id=project_id)
    return _sliding_chunks(source, repo_path=root, project_id=project_id)
