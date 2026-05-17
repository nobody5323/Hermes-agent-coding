# Task Plan: Hermes AI Coding MVP Loop

## Goal
Implement the smallest local AI Coding loop described in `module_implementation.md`: repository scan, Python chunking, keyword/mock retrieval, context package assembly, patch preview, sandbox pytest execution, and one bug-fix demo chain.

## Phases

| Phase | Status | Scope |
| --- | --- | --- |
| 1 | complete | Create planning files and inspect current workspace |
| 2 | complete | Implement `extensions/ai_coding` core modules |
| 3 | complete | Create demo Python repository fixture |
| 4 | complete | Add and run smoke tests for the minimum loop |
| 5 | complete | Summarize usage and next steps |
| 6 | complete | Add Docker CLI sandbox runner |
| 7 | complete | Initialize git repository, connect GitHub remote, commit and push |
| 8 | complete | Add command-line entrypoint for server testing |
| 9 | complete | Add Hermes project-local plugin skeleton |
| 10 | complete | Add deployment and demo documentation |
| 11 | complete | Add rule-based automatic Patch Generator for MVP demo |

## Key Decisions

- Build the MVP as a local Python package under the current workspace first.
- Avoid real LLM, Qdrant, full reranker, sub-agents, and complex long-term memory for this loop.
- Keep patch application read-only by default; sandbox execution uses a copied temporary repository.
- Use Pydantic v2 schemas because the local environment already has Pydantic installed.
- Current machine does not have Docker CLI installed, so Docker runner tests must not require a live daemon.
- Do not commit generated caches or downloaded Docker installers.
- CLI should default to local copied-repo sandbox and optionally support Docker sandbox.
- Hermes project plugins live under `.hermes/plugins/` and require `HERMES_ENABLE_PROJECT_PLUGINS=true`.
- The real Hermes integration has been verified on the server with DeepSeek and `ai_coding_run_minimum_loop`.
- Automatic patch generation starts as a conservative rule-based generator for the demo bugfix, not a general LLM patcher.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `pytest extensions/ai_coding/tests` collected fixture repo tests and could not import fixture modules | First smoke test run | Add test-suite `conftest.py` to ignore `fixtures/*` during extension test collection |
| `NameError: get_config is not defined` in context package builder | Second smoke test run | Restore local `.config import get_config` |
| `git apply` returned `corrupt patch at line 10` | Third smoke test run | Correct the smoke-test hunk header to match fixture file line counts |
| `git apply --check` said patch does not apply at `src/user_service.py:5` | Fourth smoke test run | Adjust hunk start/count to include both blank context lines before `login` |
| Patch still did not apply after expanding hunk | Fifth smoke test run | Compared with `git diff --no-index`; use one blank context line and `@@ -5,5 +5,5 @@ USERS = {` |
| `git apply` still rejected whitespace-sensitive hunk while `--ignore-whitespace` passed | Sixth diagnosis | Use `git apply --ignore-whitespace` for patch validation and sandbox application in MVP |
| `docker` command not found | Docker sandbox check | Implement Docker CLI support with structured unavailable result and unit-test command construction |
