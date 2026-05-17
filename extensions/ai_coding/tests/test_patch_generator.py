from pathlib import Path

from extensions.ai_coding.context_engineering import build_context_package
from extensions.ai_coding.patch_generator import generate_llm_patch_for_task, generate_patch_for_task_with_strategy
from extensions.ai_coding.rag.retriever import retrieve_code_context
from extensions.ai_coding.schemas import CodingTask
from extensions.ai_coding.tools.patch import validate_patch_against_repo
from extensions.ai_coding.tools.repository import scan_repository


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


def test_generate_empty_password_patch():
    task = CodingTask(
        task_id="t1",
        user_request="fix empty password login bug and return False",
        repo_path=str(FIXTURE),
    )
    summary = scan_repository(FIXTURE)
    retrieved = retrieve_code_context(FIXTURE, task.user_request, project_id="demo")
    context = build_context_package(task, summary, retrieved)
    generated = generate_patch_for_task_with_strategy(task, context, strategy="rule")
    assert generated.generated is True
    assert generated.strategy == "rule_based_empty_password"
    assert "return False" in generated.patch_text
    preview = validate_patch_against_repo(FIXTURE, generated.patch_text)
    assert preview.valid is True


class FakeLLMClient:
    class Config:
        model = "fake-model"

    config = Config()

    def complete(self, messages):
        assert messages[0]["role"] == "system"
        return """```diff
diff --git a/src/user_service.py b/src/user_service.py
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -5,5 +5,5 @@ USERS = {
 
 def login(username: str, password: str) -> bool:
     if password == "":
-        raise ValueError("empty password")
+        return False
     return USERS.get(username) == password
```
"""


class SimplifiedDiffLLMClient:
    class Config:
        model = "fake-model"

    config = Config()

    def complete(self, messages):
        assert "Full file context with line numbers" in messages[1]["content"]
        return """
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -3,7 +3,7 @@
 
 def login(username: str, password: str) -> bool:
     if password == "":
-        raise ValueError("empty password")
+        return False
     return USERS.get(username) == password
"""


def test_generate_llm_patch_with_mock_client():
    task = CodingTask(
        task_id="t1",
        user_request="fix empty password login bug and return False",
        repo_path=str(FIXTURE),
    )
    summary = scan_repository(FIXTURE)
    retrieved = retrieve_code_context(FIXTURE, task.user_request, project_id="demo")
    context = build_context_package(task, summary, retrieved)
    generated = generate_llm_patch_for_task(task, context, client=FakeLLMClient())
    assert generated.generated is True
    assert generated.strategy == "llm"
    assert generated.model == "fake-model"
    preview = validate_patch_against_repo(FIXTURE, generated.patch_text)
    assert preview.valid is True


def test_generate_llm_patch_repairs_simplified_diff_with_wrong_hunk_numbers():
    task = CodingTask(
        task_id="t1",
        user_request="fix empty password login bug and return False",
        repo_path=str(FIXTURE),
    )
    summary = scan_repository(FIXTURE)
    retrieved = retrieve_code_context(FIXTURE, task.user_request, project_id="demo")
    context = build_context_package(task, summary, retrieved)
    generated = generate_llm_patch_for_task(task, context, client=SimplifiedDiffLLMClient())
    assert generated.generated is True
    assert generated.strategy == "llm"
    assert generated.patch_text.startswith("diff --git a/src/user_service.py b/src/user_service.py")
    assert "@@ -5,5 +5,5 @@" in generated.patch_text
    preview = validate_patch_against_repo(FIXTURE, generated.patch_text)
    assert preview.valid is True
