from pathlib import Path

from extensions.ai_coding.config import get_config
from extensions.ai_coding.rag import retriever
from extensions.ai_coding.rag.services import OpenAIEmbeddingClient, QdrantVectorStore, RerankerClient
from extensions.ai_coding.schemas import RetrievedChunk


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


class FakeEmbedder:
    def embed_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeQdrantStore:
    chunks = []

    def ensure_collection(self):
        return None

    def upsert_chunks(self, chunks, vectors):
        self.chunks = chunks
        assert len(chunks) == len(vectors)

    def search(self, query_vector, *, limit):
        del query_vector, limit
        return [
            RetrievedChunk(chunk=chunk, score=0.8, reasons=["qdrant vector search"])
            for chunk in self.chunks
            if chunk.path == "src/user_service.py"
        ]


class FakeReranker:
    def rerank(self, query, chunks, *, top_k):
        del query
        return [
            item.model_copy(update={"score": 0.99, "reasons": [*item.reasons, "external reranker"]})
            for item in chunks[:top_k]
        ]


def test_qdrant_retrieval_path_uses_configured_services(monkeypatch):
    monkeypatch.setenv("AI_CODING_RAG_BACKEND", "qdrant")
    monkeypatch.setenv("AI_CODING_QDRANT_URL", "http://qdrant.local:6333")
    monkeypatch.setenv("AI_CODING_EMBEDDING_BASE_URL", "http://embed.local/v1")
    monkeypatch.setenv("AI_CODING_EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("AI_CODING_EMBEDDING_MODEL", "text-embedding-test")
    monkeypatch.setenv("AI_CODING_EMBEDDING_DIMENSIONS", "3")
    monkeypatch.setenv("AI_CODING_RERANKER_URL", "http://rerank.local/rerank")
    monkeypatch.setenv("AI_CODING_RERANKER_MODEL", "rerank-test")
    get_config.cache_clear()
    monkeypatch.setattr(retriever.OpenAIEmbeddingClient, "from_config", classmethod(lambda cls, config: FakeEmbedder()))
    monkeypatch.setattr(retriever.QdrantVectorStore, "from_config", classmethod(lambda cls, config: FakeQdrantStore()))
    monkeypatch.setattr(retriever.RerankerClient, "from_config", classmethod(lambda cls, config: FakeReranker()))

    results = retriever.retrieve_code_context(FIXTURE, "login password", top_k=3)

    assert results
    assert results[0].chunk.path == "src/user_service.py"
    assert results[0].score == 0.99
    assert "external reranker" in results[0].reasons
    get_config.cache_clear()


def test_service_factories_require_user_configuration(monkeypatch):
    for name in [
        "AI_CODING_QDRANT_URL",
        "AI_CODING_EMBEDDING_BASE_URL",
        "AI_CODING_EMBEDDING_API_KEY",
        "AI_CODING_EMBEDDING_MODEL",
        "AI_CODING_RERANKER_URL",
        "AI_CODING_RERANKER_MODEL",
    ]:
        monkeypatch.delenv(name, raising=False)
    get_config.cache_clear()
    config = get_config()

    assert OpenAIEmbeddingClient.from_config(config) is None
    assert QdrantVectorStore.from_config(config) is None
    assert RerankerClient.from_config(config) is None
    get_config.cache_clear()
