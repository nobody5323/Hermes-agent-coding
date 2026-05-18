# Hermes Integration Demo

This document records the server-side validation path for the Hermes Agent AI Coding extension.

## Verified Result

The following real integration path has been verified:

```text
Hermes Agent + DeepSeek
-> project-local Hermes plugin
-> ai_coding_run_minimum_loop
-> repository scan
-> Python AST chunking
-> keyword + mock embedding retrieval
-> Context Package
-> Patch Preview
-> copied-repo pytest sandbox
-> structured result returned to Hermes
```

Final smoke result:

```text
Task d30f060cea10: bugfix
Repository files scanned: 6
Context chunks selected: 5
Patch preview: 1 file(s), +1/-1, valid=True
Sandbox: exit=0, command succeeded
```

Hermes also confirmed the patch behavior:

```text
replaces raise ValueError("empty password") with return False in src/user_service.py
pytest passed: 3/3 tests green
```

## Server Layout

Recommended layout:

```text
/opt/hermes-agent/          # NousResearch Hermes Agent
/opt/Hermes-agent-coding/   # This AI Coding plugin project
```

Clone both repositories:

```bash
cd /opt
git clone https://github.com/NousResearch/hermes-agent.git
git clone https://github.com/nobody5323/Hermes-agent-coding.git
```

## Install Hermes

Hermes currently requires Python 3.11+.

```bash
cd /opt/hermes-agent
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .
```

If `hermes` is not found, call it by full path:

```bash
/opt/hermes-agent/.venv/bin/hermes --help
```

## Configure DeepSeek

```bash
source /opt/hermes-agent/.venv/bin/activate
export DEEPSEEK_API_KEY="your-key"
hermes model
```

Choose DeepSeek in the model setup. A basic model check:

```bash
hermes chat -q "hello"
```

Expected shape:

```text
Hello! I'm Hermes Agent, running on DeepSeek ...
```

## Enable The Plugin

Hermes project plugins are loaded from `.hermes/plugins` in the active project directory when enabled.

Option A: run Hermes from this repository:

```bash
cd /opt/Hermes-agent-coding
source /opt/hermes-agent/.venv/bin/activate
export HERMES_ENABLE_PROJECT_PLUGINS=true
hermes
```

Option B: symlink this plugin into the Hermes Agent working directory:

```bash
cd /opt/hermes-agent
mkdir -p .hermes/plugins
ln -sfn /opt/Hermes-agent-coding/.hermes/plugins/ai-coding \
  /opt/hermes-agent/.hermes/plugins/ai-coding

export HERMES_ENABLE_PROJECT_PLUGINS=true
```

Use the symlink path if you normally start Hermes from `/opt/hermes-agent`.

## Verify The Plugin Scan Tool

```bash
cd /opt/hermes-agent
source .venv/bin/activate
export HERMES_ENABLE_PROJECT_PLUGINS=true

hermes chat -q "Use ai_coding_scan_repository to scan /opt/Hermes-agent-coding."
```

Expected clean scan after removing unrelated local source trees:

```text
Total: 57 files
Python: 31 files
Markdown: 16 files
.hermes/plugins/ai-coding/ plugin.yaml + __init__.py
```

Hermes should mention the registered tools:

```text
ai_coding_scan_repository
ai_coding_read_file_slice
ai_coding_search_code
ai_coding_retrieve_code_context
ai_coding_build_context_package
ai_coding_preview_patch
ai_coding_validate_patch
ai_coding_apply_patch
ai_coding_read_lessons
ai_coding_write_lesson
ai_coding_run_pytest_sandbox
ai_coding_run_pytest_docker_sandbox
ai_coding_run_minimum_loop
ai_coding_run_task_loop
```

If the scan unexpectedly includes a large `Python-3.9.0/` tree or other unrelated directories, move them outside `/opt/Hermes-agent-coding` and scan again.

## Verify The Full Minimum Loop

The patch fixture lives at:

```text
/opt/Hermes-agent-coding/examples/bugfix_empty_password.diff
```

Run through Hermes:

```bash
PATCH="$(cat /opt/Hermes-agent-coding/examples/bugfix_empty_password.diff)"

hermes chat -q "Use ai_coding_run_minimum_loop on repo /opt/Hermes-agent-coding/extensions/ai_coding/tests/fixtures/demo_python_repo. The task is 'fix empty password login bug'. Use this patch text: $PATCH"
```

Expected output:

```text
Repository files scanned: 6
Context chunks selected: 5
Patch preview: 1 file(s), +1/-1, valid=True
Sandbox: exit=0, command succeeded
```

This confirms:

```text
Hermes -> Plugin -> AI Coding workflow -> Patch validation -> pytest sandbox
```

## Verify Without Hermes

The standalone CLI remains useful for debugging:

```bash
cd /opt/Hermes-agent-coding
source /opt/hermes-agent/.venv/bin/activate

python -m pytest extensions/ai_coding/tests
python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug" \
  --patch examples/bugfix_empty_password.diff
```

Expected:

```text
Sandbox: exit=0, command succeeded
```

## Automatic Patch Generator Demo

The MVP includes a conservative rule-based Patch Generator for the empty-password bugfix demo. This allows the minimum loop to run without manually passing `examples/bugfix_empty_password.diff`.

The current implementation also includes an OpenAI-compatible LLM Patch Generator. In `auto` mode the system tries LLM generation first when credentials exist, then falls back to the rule generator if no key is configured or the LLM call fails.

LLM configuration:

```bash
export DEEPSEEK_API_KEY="your-key"
# optional overrides
export AI_CODING_LLM_BASE_URL="https://api.deepseek.com"
export AI_CODING_LLM_MODEL="deepseek-v4-pro"
```

The LLM Patch Generator sends line-numbered file context and normalizes returned patches into git-style diffs. If the model returns a simplified unified diff with matching real file context, the generator rebuilds a valid `diff --git` patch before validation.

By default the minimum loop does not modify the real repository. It applies the patch only inside the sandbox copy. To apply after validation and sandbox success, use `--apply` in the CLI or pass `apply=true` to `ai_coding_run_minimum_loop`.

For real repositories, use `ai_coding_run_task_loop`. It supports arbitrary repo paths and tasks when the LLM patch generator is configured. In git repositories, `apply=true` checks for a clean worktree before writing and creates an `ai-coding/<task-id>` branch by default. `commit=true` writes patch, test report, and PR summary artifacts under `.ai-coding/runs/<task-id>/`, then creates a local commit.

The remaining production modules are also available:

- Enhanced Context/RAG: query expansion, failure-feedback retrieval, source/test sibling reranking, and lessons injected into the context package.
- Multi-round repair loop: pass `repair_attempts=2` to retry generation with patch validation or sandbox failure feedback.
- Memory/Lessons: existing `.ai-coding/memory/lessons.jsonl` entries are read by default; pass `write_memory=true` to record a successful verified run.

CLI:

```bash
cd /opt/Hermes-agent-coding
source /opt/hermes-agent/.venv/bin/activate

python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug and return False" \
  --auto-patch \
  --patch-generator auto
```

Expected:

```text
Patch preview: 1 file(s), +1/-1, valid=True
Patch generator: generated=True, strategy=rule_based_empty_password
Sandbox: exit=0, command succeeded
```

Hermes plugin:

```bash
hermes chat -q "Use ai_coding_run_minimum_loop on repo /opt/Hermes-agent-coding/extensions/ai_coding/tests/fixtures/demo_python_repo. The task is 'fix empty password login bug and return False'. Do not provide patch text; use the automatic patch generator if available."
```

Apply a verified patch to the real repository:

```bash
hermes chat -q "Call ai_coding_run_minimum_loop with repo_path='/opt/Hermes-agent-coding/extensions/ai_coding/tests/fixtures/demo_python_repo', task='fix empty password login bug and return False', patch_generator='llm', apply=true. Do not provide patch_text."
```

Run a real repository task in preview-only mode:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/your/repo', task='fix the failing login validation test', patch_generator='llm'. Do not apply."
```

Run with branch, apply, commit, PR summary, and test report:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/your/repo', task='fix the failing login validation test', patch_generator='llm', apply=true, commit=true, commit_message='Fix login validation'."
```

Run with repair and memory:

```bash
hermes chat -q "Call ai_coding_run_task_loop with repo_path='/path/to/your/repo', task='fix the failing login validation test', patch_generator='llm', repair_attempts=2, write_memory=true. Do not apply."
```

Expected:

```text
Patch generator: generated=True
Sandbox: exit=0, command succeeded
```

The deterministic rule generator is intentionally narrow and only exists for the demo bug. Real repository tasks should use `patch_generator=llm`.

To require LLM generation rather than fallback:

```bash
python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug and return False" \
  --auto-patch \
  --patch-generator llm
```

To force the deterministic demo rule:

```bash
python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug and return False" \
  --auto-patch \
  --patch-generator rule
```

## Docker Backend Check

The MVP uses the local copied-repo sandbox by default. To test Docker:

```bash
docker info

python -m extensions.ai_coding.cli run \
  --repo extensions/ai_coding/tests/fixtures/demo_python_repo \
  --task "fix empty password login bug" \
  --patch examples/bugfix_empty_password.diff \
  --sandbox docker
```

If Docker is not installed or the daemon is stopped, the tool returns a structured `SandboxResult` instead of crashing.
