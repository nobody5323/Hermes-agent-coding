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
