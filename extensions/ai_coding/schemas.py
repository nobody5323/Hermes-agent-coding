"""Shared Pydantic schemas for the local AI Coding MVP."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodingTask(BaseModel):
    task_id: str
    user_request: str
    repo_path: str
    task_type: str = "bugfix"
    constraints: list[str] = Field(default_factory=list)
    risk_level: str = "medium"


class RepositoryFile(BaseModel):
    path: str
    file_type: str
    language: str
    size_bytes: int
    line_count: int


class RepositorySummary(BaseModel):
    repo_path: str
    total_files: int
    files: list[RepositoryFile]
    languages: dict[str, int] = Field(default_factory=dict)
    entrypoints: list[str] = Field(default_factory=list)
    dependency_files: list[str] = Field(default_factory=list)
    has_readme: bool = False
    has_tests: bool = False
    test_commands: list[str] = Field(default_factory=list)


class CodeChunk(BaseModel):
    chunk_id: str
    project_id: str
    path: str
    language: str
    file_type: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    content: str


class RetrievedChunk(BaseModel):
    chunk: CodeChunk
    score: float
    reasons: list[str] = Field(default_factory=list)


class ContextPackage(BaseModel):
    task: CodingTask
    repository: RepositorySummary
    retrieved_chunks: list[RetrievedChunk]
    token_budget: int
    token_estimate: int
    markdown: str


class PatchFileChange(BaseModel):
    path: str
    additions: int = 0
    deletions: int = 0


class PatchPreview(BaseModel):
    valid: bool
    files: list[PatchFileChange] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    errors: list[str] = Field(default_factory=list)
    summary: str = ""
    patch_text: str = ""


class PatchApplyResult(BaseModel):
    applied: bool
    files: list[PatchFileChange] = Field(default_factory=list)
    summary: str = ""
    errors: list[str] = Field(default_factory=list)
    git_repo: bool = False
    original_branch: str | None = None
    branch_name: str | None = None
    branch_created: bool = False
    patch_artifact_path: str | None = None
    test_report_path: str | None = None
    pr_summary_path: str | None = None
    commit_sha: str | None = None
    dirty_files: list[str] = Field(default_factory=list)
    rolled_back: bool = False


class GeneratedPatch(BaseModel):
    generated: bool
    patch_text: str = ""
    strategy: str = ""
    target_file: str | None = None
    reason: str = ""
    model: str | None = None
    used_fallback: bool = False
    errors: list[str] = Field(default_factory=list)


class SandboxResult(BaseModel):
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    summary: str = ""
    copied_repo_path: str | None = None
    rejected: bool = False


class CodingTaskResult(BaseModel):
    task: CodingTask
    context_package: ContextPackage
    generated_patch: GeneratedPatch | None = None
    patch_preview: PatchPreview | None = None
    apply_result: PatchApplyResult | None = None
    sandbox_result: SandboxResult | None = None
    final_summary: str
