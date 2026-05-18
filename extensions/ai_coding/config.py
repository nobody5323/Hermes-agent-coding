"""Configuration for the local AI Coding MVP."""

from __future__ import annotations

import os
from functools import lru_cache
from pydantic import BaseModel, Field


class AiCodingConfig(BaseModel):
    default_token_budget: int = Field(default=4000, ge=500)
    max_iterations: int = Field(default=2, ge=1)
    default_top_k: int = Field(default=5, ge=1)
    ignored_dirs: set[str] = Field(
        default_factory=lambda: {
            ".git",
            ".hg",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "build",
            "dist",
            "node_modules",
            "__pycache__",
        }
    )
    supported_extensions: set[str] = Field(
        default_factory=lambda: {
            ".py",
            ".md",
            ".txt",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".js",
            ".ts",
        }
    )
    sandbox_timeout_seconds: int = Field(default=30, ge=1)
    docker_image: str = "hermes-ai-coding-python:latest"
    docker_workdir: str = "/workspace"
    max_file_bytes: int = Field(default=512_000, ge=1024)
    max_read_lines: int = Field(default=200, ge=1)
    rag_backend: str = "local"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "ai_coding_chunks"
    qdrant_timeout_seconds: int = Field(default=20, ge=1)
    qdrant_index_on_retrieve: bool = True
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = Field(default=1536, ge=1)
    reranker_url: str = ""
    reranker_api_key: str = ""
    reranker_model: str = ""


@lru_cache(maxsize=1)
def get_config() -> AiCodingConfig:
    """Load config from environment with sensible MVP defaults."""

    return AiCodingConfig(
        default_token_budget=int(os.getenv("AI_CODING_TOKEN_BUDGET", "4000")),
        max_iterations=int(os.getenv("AI_CODING_MAX_ITERATIONS", "2")),
        default_top_k=int(os.getenv("AI_CODING_TOP_K", "5")),
        sandbox_timeout_seconds=int(os.getenv("AI_CODING_SANDBOX_TIMEOUT", "30")),
        docker_image=os.getenv("AI_CODING_DOCKER_IMAGE", "hermes-ai-coding-python:latest"),
        rag_backend=os.getenv("AI_CODING_RAG_BACKEND", "local").lower(),
        qdrant_url=os.getenv("AI_CODING_QDRANT_URL", ""),
        qdrant_api_key=os.getenv("AI_CODING_QDRANT_API_KEY", ""),
        qdrant_collection=os.getenv("AI_CODING_QDRANT_COLLECTION", "ai_coding_chunks"),
        qdrant_timeout_seconds=int(os.getenv("AI_CODING_QDRANT_TIMEOUT", "20")),
        qdrant_index_on_retrieve=os.getenv("AI_CODING_QDRANT_INDEX_ON_RETRIEVE", "true").lower() not in {"0", "false", "no"},
        embedding_base_url=os.getenv("AI_CODING_EMBEDDING_BASE_URL", ""),
        embedding_api_key=os.getenv("AI_CODING_EMBEDDING_API_KEY", ""),
        embedding_model=os.getenv("AI_CODING_EMBEDDING_MODEL", ""),
        embedding_dimensions=int(os.getenv("AI_CODING_EMBEDDING_DIMENSIONS", "1536")),
        reranker_url=os.getenv("AI_CODING_RERANKER_URL", ""),
        reranker_api_key=os.getenv("AI_CODING_RERANKER_API_KEY", ""),
        reranker_model=os.getenv("AI_CODING_RERANKER_MODEL", ""),
    )
