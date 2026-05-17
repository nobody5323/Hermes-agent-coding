"""Keyword plus mock-embedding retrieval."""

from __future__ import annotations

from pathlib import Path

from ..config import get_config
from ..schemas import CodeChunk, RetrievedChunk
from ..tools.repository import scan_repository
from .chunker import chunk_file
from .embeddings import MockEmbedding, cosine_similarity, tokenize


def index_repository_chunks(repo_path: str | Path, *, project_id: str = "default") -> list[CodeChunk]:
    root = Path(repo_path).resolve()
    summary = scan_repository(root)
    chunks: list[CodeChunk] = []
    for item in summary.files:
        if item.file_type not in {"source", "test", "doc", "config"}:
            continue
        chunks.extend(chunk_file(root / item.path, repo_path=root, project_id=project_id))
    return chunks


def retrieve_code_context(
    repo_path: str | Path,
    query: str,
    *,
    project_id: str = "default",
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or get_config().default_top_k
    chunks = index_repository_chunks(repo_path, project_id=project_id)
    query_tokens = set(tokenize(query))
    embedder = MockEmbedding()
    query_vector = embedder.embed(query)
    retrieved: list[RetrievedChunk] = []

    for chunk in chunks:
        content_tokens = set(tokenize(chunk.content + " " + chunk.path + " " + (chunk.symbol_name or "")))
        overlap = query_tokens & content_tokens
        keyword_score = len(overlap) / max(1, len(query_tokens))
        vector_score = cosine_similarity(query_vector, embedder.embed(chunk.content))
        path_score = 0.2 if any(token in chunk.path.lower() for token in query_tokens) else 0.0
        test_bonus = 0.1 if chunk.file_type == "test" and {"test", "pytest", "测试"} & query_tokens else 0.0
        score = keyword_score * 0.65 + vector_score * 0.25 + path_score + test_bonus
        reasons: list[str] = []
        if overlap:
            reasons.append(f"keyword overlap: {', '.join(sorted(overlap)[:6])}")
        if path_score:
            reasons.append("path matched query token")
        if vector_score:
            reasons.append(f"mock embedding similarity {vector_score:.2f}")
        if score > 0:
            retrieved.append(RetrievedChunk(chunk=chunk, score=round(score, 4), reasons=reasons))

    return sorted(retrieved, key=lambda item: item.score, reverse=True)[:top_k]
