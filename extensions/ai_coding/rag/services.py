"""Optional production RAG services: embeddings, Qdrant, and reranking."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from ..config import AiCodingConfig
from ..schemas import CodeChunk, RetrievedChunk


class RagServiceError(RuntimeError):
    pass


def _post_json(url: str, payload: dict[str, Any], *, api_key: str = "", timeout: int = 20) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["api-key"] = api_key
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RagServiceError(f"HTTP {exc.code} from {url}: {body}") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RagServiceError(f"request failed for {url}: {exc}") from exc


def _put_json(url: str, payload: dict[str, Any], *, api_key: str = "", timeout: int = 20) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RagServiceError(f"HTTP {exc.code} from {url}: {body}") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RagServiceError(f"request failed for {url}: {exc}") from exc


@dataclass(frozen=True)
class OpenAIEmbeddingClient:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 20

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/embeddings"

    @classmethod
    def from_config(cls, config: AiCodingConfig) -> "OpenAIEmbeddingClient | None":
        if not (config.embedding_base_url and config.embedding_api_key and config.embedding_model):
            return None
        return cls(
            base_url=config.embedding_base_url,
            api_key=config.embedding_api_key,
            model=config.embedding_model,
            timeout_seconds=config.qdrant_timeout_seconds,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = _post_json(
            self.embeddings_url,
            {"model": self.model, "input": texts},
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )
        try:
            ordered = sorted(data["data"], key=lambda item: item.get("index", 0))
            return [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise RagServiceError(f"unexpected embedding response: {str(data)[:500]}") from exc


@dataclass(frozen=True)
class QdrantVectorStore:
    url: str
    api_key: str
    collection: str
    dimensions: int
    timeout_seconds: int = 20

    @classmethod
    def from_config(cls, config: AiCodingConfig) -> "QdrantVectorStore | None":
        if not config.qdrant_url:
            return None
        return cls(
            url=config.qdrant_url.rstrip("/"),
            api_key=config.qdrant_api_key,
            collection=config.qdrant_collection,
            dimensions=config.embedding_dimensions,
            timeout_seconds=config.qdrant_timeout_seconds,
        )

    def ensure_collection(self) -> None:
        _put_json(
            f"{self.url}/collections/{self.collection}",
            {"vectors": {"size": self.dimensions, "distance": "Cosine"}},
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    def upsert_chunks(self, chunks: list[CodeChunk], vectors: list[list[float]]) -> None:
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                    "vector": vector,
                    "payload": chunk.model_dump(),
                }
            )
        if not points:
            return
        _put_json(
            f"{self.url}/collections/{self.collection}/points",
            {"points": points},
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    def search(self, query_vector: list[float], *, limit: int) -> list[RetrievedChunk]:
        payload = {"vector": query_vector, "limit": limit, "with_payload": True}
        try:
            data = _post_json(
                f"{self.url}/collections/{self.collection}/points/search",
                payload,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
            hits = data.get("result", [])
        except RagServiceError:
            data = _post_json(
                f"{self.url}/collections/{self.collection}/points/query",
                {"query": query_vector, "limit": limit, "with_payload": True},
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
            result = data.get("result", {})
            hits = result.get("points", result if isinstance(result, list) else [])

        retrieved: list[RetrievedChunk] = []
        for hit in hits:
            payload = hit.get("payload") or {}
            try:
                chunk = CodeChunk.model_validate(payload)
            except ValueError:
                continue
            score = float(hit.get("score", 0.0))
            retrieved.append(RetrievedChunk(chunk=chunk, score=round(score, 4), reasons=["qdrant vector search"]))
        return retrieved


@dataclass(frozen=True)
class RerankerClient:
    url: str
    api_key: str
    model: str
    timeout_seconds: int = 20

    @classmethod
    def from_config(cls, config: AiCodingConfig) -> "RerankerClient | None":
        if not (config.reranker_url and config.reranker_model):
            return None
        return cls(
            url=config.reranker_url,
            api_key=config.reranker_api_key,
            model=config.reranker_model,
            timeout_seconds=config.qdrant_timeout_seconds,
        )

    def rerank(self, query: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        documents = [item.chunk.content for item in chunks]
        data = _post_json(
            self.url,
            {"model": self.model, "query": query, "documents": documents, "top_n": min(top_k, len(chunks))},
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )
        results = data.get("results", [])
        reranked: list[RetrievedChunk] = []
        for result in results:
            index = result.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(chunks):
                continue
            score = float(result.get("relevance_score", result.get("score", chunks[index].score)))
            reranked.append(
                chunks[index].model_copy(
                    update={
                        "score": round(score, 4),
                        "reasons": [*chunks[index].reasons, "external reranker"],
                    }
                )
            )
        return reranked[:top_k] or chunks[:top_k]
