# Hermes Agent AI Coding Extension Acceptance Report

Date: 2026-05-18

Repository: `nobody5323/Hermes-agent-coding`

Accepted implementation baseline: `7289f4f Add configurable Qdrant RAG services`

## Verdict

Acceptance status: **Passed**

The project has reached the planned acceptance baseline for a Hermes AI Coding Agent prototype. The verified system can load as a Hermes project plugin, scan repositories, build coding context, generate patches with an LLM, validate patches, run local and Docker sandboxes, run bounded repair attempts, use repository-local memory lessons, apply verified changes, create local commits, and produce review artifacts.

## Accepted Scope

- Hermes project-local plugin under `.hermes/plugins/ai-coding/`
- AI Coding skill prompts under `skills/ai-coding/`
- Repository scan, file slice, and code search tools
- Python AST chunking and local retrieval
- Optional Qdrant / OpenAI-compatible embedding / generic reranker services
- Context Package assembly with repository-local memory lessons
- Rule-based demo patch generator
- OpenAI-compatible LLM patch generator
- LLM diff normalization and repair for simplified unified diffs
- Patch preview and `git apply --check` validation
- Local copied-repository pytest sandbox
- Docker pytest sandbox
- Explicit apply flow for real repositories
- Git safety checks, branch creation, patch artifacts, commit support
- PR summary and test report artifact generation
- Bounded repair loop with validation/sandbox feedback
- Repository-local memory lessons in `.ai-coding/memory/lessons.jsonl`

## Verification Summary

### Automated Local Test Suite

Command:

```bash
python -m pytest extensions/ai_coding/tests
```

Result:

```text
35 passed
```

Covered areas:

- Repository scanning, file slicing, and search
- Chunking and context package generation
- Enhanced local retrieval with query expansion and failure feedback
- Qdrant / embedding / reranker adapter behavior with mocked services
- LLM patch generation with mock client
- LLM simplified-diff repair
- Rule-based demo patch generation
- Patch validation and apply behavior
- Git dirty-worktree guard, branch/artifact/commit flow
- CLI execution paths
- Hermes plugin registration and handlers
- Local sandbox policy and workflow smoke tests
- Memory lesson read/write and repair loop retries

### Server / Hermes Validation

The following were validated interactively on the server:

- Hermes Agent starts successfully with DeepSeek.
- Project plugin loads when Hermes starts from `/opt/Hermes-agent-coding` with `HERMES_ENABLE_PROJECT_PLUGINS=true`.
- `ai_coding_run_minimum_loop` and `ai_coding_run_task_loop` execute through Hermes.
- LLM patch generation succeeds with DeepSeek when `AI_CODING_LLM_API_KEY` / `DEEPSEEK_API_KEY` is available in the Hermes process environment.
- Patch preview validates the generated patch.
- Local pytest sandbox passes.
- Docker sandbox passes.
- Preview-only mode respects `Do not apply`.
- `apply=true` writes the verified patch to the target repository.
- `commit=true` creates a local commit and review artifacts.
- `repair_attempts` is honored and stops after first success.
- Memory lessons are loaded and written.

Representative successful server result:

```text
Patch generator: generated=True, strategy=llm
Patch preview: 1 file(s), +1/-1, valid=True
Sandbox: exit=0, command succeeded
Repair iterations: 1
Memory lessons used: 3
```

## Configuration

### Required For Hermes Plugin Use

```bash
cd /opt/hermes-agent
source .venv/bin/activate

cd /opt/Hermes-agent-coding
export HERMES_ENABLE_PROJECT_PLUGINS=true
```

### Required For LLM Patch Generation

The plugin LLM client reads environment variables from the Hermes process environment:

```bash
export AI_CODING_LLM_API_KEY="your-key"
export AI_CODING_LLM_BASE_URL="https://api.deepseek.com"
export AI_CODING_LLM_MODEL="deepseek-v4-pro"
```

`DEEPSEEK_API_KEY` and `OPENAI_API_KEY` are also supported fallback key names.

### Optional Production RAG

Default retrieval is local and zero-dependency. Users may enable Qdrant and external models:

```bash
export AI_CODING_RAG_BACKEND=qdrant
export AI_CODING_QDRANT_URL="http://localhost:6333"
export AI_CODING_QDRANT_COLLECTION="ai_coding_chunks"
export AI_CODING_EMBEDDING_BASE_URL="https://api.openai.com/v1"
export AI_CODING_EMBEDDING_API_KEY="your-embedding-key"
export AI_CODING_EMBEDDING_MODEL="text-embedding-3-small"
export AI_CODING_EMBEDDING_DIMENSIONS=1536
```

Optional reranker:

```bash
export AI_CODING_RERANKER_URL="https://api.jina.ai/v1/rerank"
export AI_CODING_RERANKER_API_KEY="your-reranker-key"
export AI_CODING_RERANKER_MODEL="jina-reranker-v2-base-multilingual"
```

If Qdrant, embedding, or reranker configuration is missing or unavailable, the system falls back to local retrieval so the agent loop can continue.

## Accepted Commands

Preview-only real task:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/repo', task='fix the failing test', patch_generator='llm', repair_attempts=2. Do not apply."
```

Apply and commit after sandbox success:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/repo', task='fix the failing test', patch_generator='llm', repair_attempts=2, apply=true, commit=true, commit_message='Fix failing test'."
```

Docker sandbox:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/repo', task='fix the failing test', patch_generator='llm', sandbox='docker'. Do not apply."
```

## Safety Guarantees

- No real repository write occurs unless `apply=true` or `commit=true`.
- Sandbox verification must pass before apply.
- Git dirty worktrees are rejected by default.
- Git repositories get an `ai-coding/<task-id>` branch by default before apply.
- Patch artifacts are saved under `.ai-coding/runs/<task-id>/`.
- Commit mode can include `change.diff`, `test_report.md`, and `pr_summary.md`.
- Memory writes are explicit via `write_memory=true` / `--write-memory`.
- External RAG service failures fall back to local retrieval.

## Known Boundaries

- GitHub PR creation through the GitHub API is not implemented; the project generates local PR summary artifacts instead.
- Qdrant indexing currently occurs opportunistically during retrieval when enabled, unless disabled by `AI_CODING_QDRANT_INDEX_ON_RETRIEVE=false`.
- External embedding and reranker endpoints are user-provided and must follow OpenAI-compatible embeddings and generic rerank JSON shapes.
- The rule-based patch generator remains intentionally narrow and only supports the demo empty-password bug.
- The project is an accepted prototype baseline, not a fully managed multi-tenant production service.

## Final Decision

The Hermes Agent AI Coding extension is accepted as an end-to-end working prototype and deployment baseline.

Recommended next milestone: test on multiple real repositories, collect failure cases, then harden Qdrant indexing, PR publishing, and provider configuration reuse.
