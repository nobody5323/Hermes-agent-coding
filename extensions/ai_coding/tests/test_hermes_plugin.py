import importlib.util
import json
from pathlib import Path


PLUGIN_PATH = Path(".hermes/plugins/ai-coding/__init__.py")
FIXTURE_REPO = "extensions/ai_coding/tests/fixtures/demo_python_repo"
PATCH_FILE = "examples/bugfix_empty_password.diff"


class FakeHermesContext:
    def __init__(self):
        self.tools = {}
        self.skills = {}

    def register_tool(self, *, name, toolset, schema, handler, description):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
        }

    def register_skill(self, name, path):
        self.skills[name] = path


def load_plugin():
    spec = importlib.util.spec_from_file_location("ai_coding_hermes_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_hermes_plugin_registers_tools_and_skill():
    plugin = load_plugin()
    ctx = FakeHermesContext()
    plugin.register(ctx)
    assert "ai_coding_scan_repository" in ctx.tools
    assert "ai_coding_apply_patch" in ctx.tools
    assert "ai_coding_run_minimum_loop" in ctx.tools
    assert "ai_coding_run_task_loop" in ctx.tools
    assert all(tool["toolset"] == "ai_coding" for tool in ctx.tools.values())
    assert "ai-coding" in ctx.skills


def test_hermes_plugin_handler_returns_json_success():
    plugin = load_plugin()
    ctx = FakeHermesContext()
    plugin.register(ctx)
    result = ctx.tools["ai_coding_scan_repository"]["handler"]({"repo_path": FIXTURE_REPO})
    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["data"]["total_files"] >= 6


def test_hermes_plugin_minimum_loop_handler():
    plugin = load_plugin()
    ctx = FakeHermesContext()
    plugin.register(ctx)
    patch_text = Path(PATCH_FILE).read_text(encoding="utf-8")
    result = ctx.tools["ai_coding_run_minimum_loop"]["handler"](
        {
            "repo_path": FIXTURE_REPO,
            "task": "fix empty password login bug",
            "patch_text": patch_text,
        }
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["data"]["sandbox_result"]["exit_code"] == 0


def test_hermes_plugin_minimum_loop_handler_generates_patch():
    plugin = load_plugin()
    ctx = FakeHermesContext()
    plugin.register(ctx)
    result = ctx.tools["ai_coding_run_minimum_loop"]["handler"](
        {
            "repo_path": FIXTURE_REPO,
            "task": "fix empty password login bug and return False",
            "patch_generator": "rule",
        }
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["data"]["generated_patch"]["generated"] is True
    assert payload["data"]["sandbox_result"]["exit_code"] == 0
