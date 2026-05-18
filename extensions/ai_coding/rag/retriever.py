"""Keyword, mock-embedding, and lightweight reranking retrieval."""

from __future__ import annotations

from pathlib import Path

from ..config import get_config
from ..schemas import CodeChunk, RetrievedChunk
from ..tools.repository import scan_repository
from .chunker import chunk_file
from .embeddings import MockEmbedding, cosine_similarity, tokenize


QUERY_SYNONYMS = {
    "login": ["auth", "authentication", "password", "user"],
    "auth": ["login", "authentication", "password", "user"],
    "password": ["login", "auth", "credential"],
    "pytest": ["test", "assert", "failed"],
    "failed": ["failure", "error", "assert", "traceback"],
    "exception": ["error", "raise", "traceback"],
    "empty": ["blank", "none", "missing"],
}


def expand_query(query: str, *, feedback: str = "", lessons: list[str] | None = None) -> str:
    parts = [query, feedback, " ".join(lessons or [])]
    tokens = tokenize(" ".join(parts))
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(QUERY_SYNONYMS.get(token, []))
    return " ".join(dict.fromkeys(expanded))


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
    feedback: str = "",
    lessons: list[str] | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or get_config().default_top_k
    chunks = index_repository_chunks(repo_path, project_id=project_id)
    expanded_query = expand_query(query, feedback=feedback, lessons=lessons)
    query_tokens = set(tokenize(expanded_query))
    embedder = MockEmbedding()
    query_vector = embedder.embed(expanded_query)
    retrieved: list[RetrievedChunk] = []

    for chunk in chunks:
        content_text = chunk.content + " " + chunk.path + " " + (chunk.symbol_name or "")
        content_tokens = set(tokenize(content_text))
        overlap = query_tokens & content_tokens
        keyword_score = len(overlap) / max(1, len(query_tokens))
        vector_score = cosine_similarity(query_vector, embedder.embed(content_text))
        path_score = 0.2 if any(token in chunk.path.lower() for token in query_tokens) else 0.0
        test_bonus = 0.1 if chunk.file_type == "test" and {"test", "pytest", "failed", "assert"} & query_tokens else 0.0
        symbol_bonus = 0.08 if chunk.symbol_name and chunk.symbol_name.lower() in query_tokens else 0.0
        error_bonus = 0.12 if feedback and any(token in chunk.path.lower() for token in tokenize(feedback)) else 0.0
        score = keyword_score * 0.6 + vector_score * 0.22 + path_score + test_bonus + symbol_bonus + error_bonus
        reasons: list[str] = []
        if overlap:
            reasons.append(f"keyword overlap: {', '.join(sorted(overlap)[:6])}")
        if path_score:
            reasons.append("path matched query token")
        if vector_score:
            reasons.append(f"mock embedding similarity {vector_score:.2f}")
        if symbol_bonus:
            reasons.append("symbol matched query")
        if error_bonus:
            reasons.append("failure feedback matched path")
        if score > 0:
            retrieved.append(RetrievedChunk(chunk=chunk, score=round(score, 4), reasons=reasons))

    ranked = sorted(retrieved, key=lambda item: item.score, reverse=True)
    if not ranked:
        return []

    selected = ranked[:top_k]
    selected_paths = {item.chunk.path for item in selected}
    sibling_bonus: list[RetrievedChunk] = []
    for item in ranked[top_k:]:
        path = item.chunk.path
        if path in selected_paths:
            continue
        stem = Path(path).stem.removeprefix("test_")
        if any(stem and stem in Path(existing).stem for existing in selected_paths):
            sibling_bonus.append(
                item.model_copy(
                    update={
                        "score": round(item.score + 0.05, 4),
                        "reasons": [*item.reasons, "sibling source/test file for selected context"],
                    }
                )
            )
    combined = sorted([*selected, *sibling_bonus[: max(0, top_k - len(selected))]], key=lambda item: item.score, reverse=True)
    return combined[:top_k]
