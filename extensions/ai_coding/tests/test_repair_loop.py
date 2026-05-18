from pathlib import Path

from extensions.ai_coding import workflow
from extensions.ai_coding.schemas import GeneratedPatch


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


VALID_PATCH = """diff --git a/src/user_service.py b/src/user_service.py
index a50f075..b621bb5 100644
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -5,5 +5,5 @@ USERS = {
 
 def login(username: str, password: str) -> bool:
     if password == "":
-        raise ValueError("empty password")
+        return False
     return USERS.get(username) == password
"""


def test_repair_loop_retries_after_invalid_generated_patch(monkeypatch):
    calls = []

    def fake_generator(task, context, *, strategy, client=None):
        del task, context, strategy, client
        calls.append("call")
        if len(calls) == 1:
            return GeneratedPatch(generated=True, patch_text="not a diff", strategy="fake")
        return GeneratedPatch(generated=True, patch_text=VALID_PATCH, strategy="fake")

    monkeypatch.setattr(workflow, "generate_patch_for_task_with_strategy", fake_generator)

    result = workflow.run_coding_task_loop(
        FIXTURE,
        "fix empty password login bug and return False",
        patch_generator="llm",
        max_repair_attempts=1,
    )

    assert len(calls) == 2
    assert len(result.repair_iterations) == 2
    assert result.repair_iterations[0].patch_valid is False
    assert "Previous failure" in result.repair_iterations[1].query
    assert result.patch_preview is not None
    assert result.patch_preview.valid is True
    assert result.sandbox_result is not None
    assert result.sandbox_result.exit_code == 0
