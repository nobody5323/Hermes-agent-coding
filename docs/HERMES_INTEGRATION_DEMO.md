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
ai_coding_run_pytest_sandbox
ai_coding_run_pytest_docker_sandbox
ai_coding_run_minimum_loop
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
