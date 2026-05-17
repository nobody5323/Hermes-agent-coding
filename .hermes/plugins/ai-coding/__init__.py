"""Hermes project-local plugin for the AI Coding MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from extensions.ai_coding.context_engineering import build_context_package
from extensions.ai_coding.rag.retriever import retrieve_code_context
from extensions.ai_coding.schemas import CodingTask
from extensions.ai_coding.tools.patch import apply_patch_to_repo, preview_patch, validate_patch_against_repo
from extensions.ai_coding.tools.repository import read_file_slice, scan_repository, search_code
from extensions.ai_coding.tools.sandbox import run_pytest_docker_sandbox, run_pytest_sandbox
from extensions.ai_coding.workflow import run_coding_task_loop


TOOLSET = "ai_coding"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _json_response(data: Any) -> str:
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list):
        data = [item.model_dump() if hasattr(item, "model_dump") else item for item in data]
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)


def _json_error(error: Exception) -> str:
    return json.dumps({"success": False, "error": str(error)}, ensure_ascii=False)


def _handler(func: Callable[[dict[str, Any]], Any]) -> Callable[..., str]:
    def wrapped(params: dict[str, Any], **kwargs: Any) -> str:
        del kwargs
        try:
            return _json_response(func(params))
        except Exception as exc:
            return _json_error(exc)

    return wrapped


def _schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _run_task_loop(params: dict[str, Any]) -> Any:
    return run_coding_task_loop(
        params["repo_path"],
        params["task"],
        patch_text=params.get("patch_text"),
        project_id=params.get("project_id", "demo"),
        sandbox_backend=params.get("sandbox", "local"),
        patch_generator=params.get("patch_generator", "auto"),
        apply_to_repo=params.get("apply", False) or params.get("commit", False),
        create_branch=params.get("create_branch", True),
        branch_name=params.get("branch_name"),
        allow_dirty=params.get("allow_dirty", False),
        save_artifacts=params.get("save_artifacts", True),
        artifact_dir=params.get("artifact_dir"),
        commit=params.get("commit", False),
        commit_message=params.get("commit_message"),
        write_review=params.get("write_review", True),
    )


LOOP_SCHEMA = _schema(
    "ai_coding_run_task_loop",
    "Run the AI Coding task loop on any repository.",
    {
        "repo_path": {"type": "string"},
        "task": {"type": "string"},
        "patch_text": {"type": "string"},
        "project_id": {"type": "string", "default": "demo"},
        "sandbox": {"type": "string", "enum": ["local", "docker"], "default": "local"},
        "patch_generator": {"type": "string", "enum": ["auto", "llm", "rule"], "default": "auto"},
        "apply": {"type": "boolean", "default": False},
        "create_branch": {"type": "boolean", "default": True},
        "branch_name": {"type": "string"},
        "allow_dirty": {"type": "boolean", "default": False},
        "save_artifacts": {"type": "boolean", "default": True},
        "artifact_dir": {"type": "string"},
        "commit": {"type": "boolean", "default": False},
        "commit_message": {"type": "string"},
        "write_review": {"type": "boolean", "default": True},
    },
    ["repo_path", "task"],
)


TOOLS: list[tuple[str, str, dict[str, Any], Callable[[dict[str, Any]], Any]]] = [
    (
        "ai_coding_scan_repository",
        "Scan a repository and return a structured summary.",
        _schema(
            "ai_coding_scan_repository",
            "Scan a repository and return a structured summary.",
            {"repo_path": {"type": "string", "description": "Repository root path"}},
            ["repo_path"],
        ),
        lambda params: scan_repository(params["repo_path"]),
    ),
    (
        "ai_coding_read_file_slice",
        "Read a safe line slice from a repository file.",
        _schema(
            "ai_coding_read_file_slice",
            "Read a safe line slice from a repository file.",
            {
                "repo_path": {"type": "string"},
                "relative_path": {"type": "string"},
                "start_line": {"type": "integer", "default": 1},
                "end_line": {"type": "integer"},
            },
            ["repo_path", "relative_path"],
        ),
        lambda params: {
            "content": read_file_slice(
                params["repo_path"],
                params["relative_path"],
                params.get("start_line", 1),
                params.get("end_line"),
            )
        },
    ),
    (
        "ai_coding_search_code",
        "Search repository code by keyword or regex.",
        _schema(
            "ai_coding_search_code",
            "Search repository code by keyword or regex.",
            {
                "repo_path": {"type": "string"},
                "query": {"type": "string"},
                "regex": {"type": "boolean", "default": False},
                "max_results": {"type": "integer", "default": 50},
            },
            ["repo_path", "query"],
        ),
        lambda params: search_code(
            params["repo_path"],
            params["query"],
            regex=params.get("regex", False),
            max_results=params.get("max_results", 50),
        ),
    ),
    (
        "ai_coding_retrieve_code_context",
        "Retrieve relevant code chunks with keyword plus mock embedding scoring.",
        _schema(
            "ai_coding_retrieve_code_context",
            "Retrieve relevant code chunks with keyword plus mock embedding scoring.",
            {
                "repo_path": {"type": "string"},
                "query": {"type": "string"},
                "project_id": {"type": "string", "default": "demo"},
                "top_k": {"type": "integer"},
            },
            ["repo_path", "query"],
        ),
        lambda params: retrieve_code_context(
            params["repo_path"],
            params["query"],
            project_id=params.get("project_id", "demo"),
            top_k=params.get("top_k"),
        ),
    ),
    (
        "ai_coding_build_context_package",
        "Build a context package from a repository and user request.",
        _schema(
            "ai_coding_build_context_package",
            "Build a context package from a repository and user request.",
            {
                "repo_path": {"type": "string"},
                "task": {"type": "string"},
                "project_id": {"type": "string", "default": "demo"},
                "top_k": {"type": "integer", "default": 5},
                "token_budget": {"type": "integer"},
            },
            ["repo_path", "task"],
        ),
        lambda params: build_context_package(
            CodingTask(
                task_id="plugin-preview",
                user_request=params["task"],
                repo_path=params["repo_path"],
                task_type="bugfix",
            ),
            scan_repository(params["repo_path"]),
            retrieve_code_context(
                params["repo_path"],
                params["task"],
                project_id=params.get("project_id", "demo"),
                top_k=params.get("top_k", 5),
            ),
            token_budget=params.get("token_budget"),
        ),
    ),
    (
        "ai_coding_preview_patch",
        "Preview a unified diff patch.",
        _schema(
            "ai_coding_preview_patch",
            "Preview a unified diff patch.",
            {"patch_text": {"type": "string"}},
            ["patch_text"],
        ),
        lambda params: preview_patch(params["patch_text"]),
    ),
    (
        "ai_coding_validate_patch",
        "Validate a unified diff patch against a repository.",
        _schema(
            "ai_coding_validate_patch",
            "Validate a unified diff patch against a repository.",
            {"repo_path": {"type": "string"}, "patch_text": {"type": "string"}},
            ["repo_path", "patch_text"],
        ),
        lambda params: validate_patch_against_repo(params["repo_path"], params["patch_text"]),
    ),
    (
        "ai_coding_apply_patch",
        "Apply a validated unified diff patch to the real repository.",
        _schema(
            "ai_coding_apply_patch",
            "Apply a validated unified diff patch to the real repository.",
            {"repo_path": {"type": "string"}, "patch_text": {"type": "string"}},
            ["repo_path", "patch_text"],
        ),
        lambda params: apply_patch_to_repo(params["repo_path"], params["patch_text"]),
    ),
    (
        "ai_coding_run_pytest_sandbox",
        "Run pytest in a copied local repository sandbox.",
        _schema(
            "ai_coding_run_pytest_sandbox",
            "Run pytest in a copied local repository sandbox.",
            {"repo_path": {"type": "string"}, "patch_text": {"type": "string"}},
            ["repo_path"],
        ),
        lambda params: run_pytest_sandbox(params["repo_path"], params.get("patch_text")),
    ),
    (
        "ai_coding_run_pytest_docker_sandbox",
        "Run pytest in Docker after applying an optional patch.",
        _schema(
            "ai_coding_run_pytest_docker_sandbox",
            "Run pytest in Docker after applying an optional patch.",
            {
                "repo_path": {"type": "string"},
                "patch_text": {"type": "string", "description": "Optional. If omitted, the MVP generator may create a demo patch."},
                "image": {"type": "string"},
            },
            ["repo_path"],
        ),
        lambda params: run_pytest_docker_sandbox(
            params["repo_path"],
            params.get("patch_text"),
            image=params.get("image"),
        ),
    ),
    (
        "ai_coding_run_minimum_loop",
        "Run the full MVP bug-fix loop.",
        LOOP_SCHEMA | {"name": "ai_coding_run_minimum_loop", "description": "Run the full MVP bug-fix loop."},
        _run_task_loop,
    ),
    (
        "ai_coding_run_task_loop",
        "Run the AI Coding task loop on any repository.",
        LOOP_SCHEMA,
        _run_task_loop,
    ),
]


def register(ctx: Any) -> None:
    for name, description, schema, handler in TOOLS:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema,
            handler=_handler(handler),
            description=description,
        )

    skill_path = _repo_root() / "skills" / "ai-coding"
    if hasattr(ctx, "register_skill") and skill_path.exists():
        ctx.register_skill("ai-coding", str(skill_path))
