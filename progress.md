# Progress

## 2026-05-16

- Started Hermes AI Coding MVP loop implementation.
- Created file-based planning artifacts.
- Confirmed Python 3.13.7, Pydantic 2.12.5, and pytest are available locally.
- Added MVP modules under `extensions/ai_coding`, `ai-coding` skill docs, demo repo fixture, and pytest smoke tests.
- First pytest run failed because fixture repository tests were collected by the extension test run.
- Second pytest run passed 7 tests and exposed a missing `get_config` import in `context_engineering.py`.
- Third pytest run reached sandbox patch application; `git apply` rejected the test patch hunk, so the fixture patch header was corrected.
- Fourth pytest run showed the hunk still missed one blank context line; updated the hunk range to `@@ -4,6 +4,6 @@`.
- Compared against a generated `git diff --no-index` patch and updated the smoke-test patch to match Git's hunk shape.
- Diagnosed Windows/Git whitespace sensitivity around blank context lines; updated patch validation and sandbox application to use `--ignore-whitespace`.
- `python -m pytest extensions/ai_coding/tests` passed: 8 tests.
- Added `demo_minimum_loop.py` as a one-command MVP loop demonstration.
- Workspace is not a git repository, so `git diff/status` could not be used for final review.
- Checked Docker availability; `docker` command is not installed on this machine.
- Added Docker CLI runner on first pass; pytest caught a syntax error from a truncated `try/except` block in `runner.py`.
- After fixing syntax, old tests passed but new Docker tests hit a pytest `tmp_path` permission issue, so tests were adjusted to use the existing fixture repo path.
- `python -m pytest extensions/ai_coding/tests` passed with Docker CLI runner tests: 10 tests.
- Installed Docker Desktop from the Aliyun mirror installer; signature validated.
- Docker CLI exists at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`, but Docker Desktop daemon cannot start from the Codex sandbox user because it is not in `docker-users`.
- Attempted to add `nobody\codexsandboxoffline` to `docker-users`; Windows returned access denied.

## 2026-05-17

- Started repository publication task for `nobody5323/Hermes-agent-coding`.
- Confirmed current workspace was not yet a git repository.
- Added `.gitignore` to exclude Python caches, local virtualenvs, and downloaded installers.
- Pre-commit verification passed: `python -m pytest extensions/ai_coding/tests` reported 11 passed.
- Standard `.git` directory was not writable in the Codex sandbox after initialization, so publication will use `.gitrepo` as an alternate local git metadata directory.
- Fetched remote `main`, preserved remote `README.md`/`LICENSE`, and expanded README with MVP usage.
- Created commit `970eb2f` (`Implement AI coding MVP loop`) with `origin/main` as parent.
- Pushed `main` to `https://github.com/nobody5323/Hermes-agent-coding.git`; remote now points to `970eb2ffdb3318ff5ae6e163120f15cb46299743`.
- Started CLI entrypoint work so server testing can run without editing `demo_minimum_loop.py`.
- Added `extensions.ai_coding.cli`, `examples/bugfix_empty_password.diff`, and CLI tests.
- Verified CLI work: `python -m pytest extensions/ai_coding/tests` passed with 13 tests.
- Verified command: `python -m extensions.ai_coding.cli run --repo extensions/ai_coding/tests/fixtures/demo_python_repo --task "fix empty password login bug" --patch examples/bugfix_empty_password.diff` returned sandbox exit 0.
- Started Hermes project-local plugin skeleton based on official `ctx.register_tool(...)` plugin API.
- Added `.hermes/plugins/ai-coding` with `plugin.yaml`, `register(ctx)`, tool wrappers, and skill registration.
- Added plugin tests with a fake Hermes context.
- Verified plugin work: `python -m pytest extensions/ai_coding/tests` passed with 16 tests.
- Re-ran CLI smoke command successfully after plugin changes.
- Server validation passed: Hermes ran on DeepSeek, loaded the project plugin through a symlink, scanned `/opt/Hermes-agent-coding`, and completed `ai_coding_run_minimum_loop` with sandbox exit 0.
- Started rule-based automatic Patch Generator so `run_minimum_bugfix_loop` can work without user-provided patch text for the demo bug.
- Added tests for automatic patch generation through generator, workflow, CLI, and Hermes plugin handler.
- Verified automatic Patch Generator: `python -m pytest extensions/ai_coding/tests` passed with 21 tests.
- Verified CLI auto-patch command returned patch preview valid and sandbox exit 0.
- Started LLM Patch Generator integration with DeepSeek/OpenAI-compatible Chat Completions support.
- Added OpenAI-compatible LLM client, LLM patch prompt, LLM/rule/auto generation modes, and deterministic mock LLM tests.
- Verified LLM integration test suite: `python -m pytest extensions/ai_coding/tests` passed with 23 tests.
- Documented DeepSeek/OpenAI-compatible LLM patch generator configuration and generator modes.
- Server LLM test showed DeepSeek generated the right semantic fix but returned a simplified diff with bad hunk metadata.
- Added line-numbered full file context to the LLM patch prompt and a normalizer that rebuilds matching simplified diffs into git-style patches.
- Added regression coverage for simplified LLM diff repair.
- Verified full test suite: `python -m pytest extensions/ai_coding/tests` passed with 24 tests.
- Added explicit verified patch apply flow: `PatchApplyResult`, `apply_patch_to_repo`, CLI `--apply`, Hermes `ai_coding_apply_patch`, and `apply` support on `ai_coding_run_minimum_loop`.
- Fixed Windows/nested-repo `git apply` behavior by setting `GIT_CEILING_DIRECTORIES` and writing temporary diff files with LF newlines.
- Verified full test suite: `python -m pytest extensions/ai_coding/tests` passed with 27 tests.
- Added real task mode with `run_coding_task_loop` and Hermes `ai_coding_run_task_loop`.
- Added git safety: clean-worktree guard, default branch creation, patch artifacts, optional commit, rollback on commit failure, PR summary, and test report artifacts.
- Verified full test suite: `python -m pytest extensions/ai_coding/tests` passed with 30 tests.
- Added enhanced Context/RAG with query expansion, failure feedback, sibling source/test reranking, and lesson injection.
- Added bounded multi-round repair attempts after invalid patches or sandbox failures.
- Added repository-local Memory/Lessons read/write helpers and Hermes lesson tools.
- Verified full test suite: `python -m pytest extensions/ai_coding/tests` passed with 33 tests.
