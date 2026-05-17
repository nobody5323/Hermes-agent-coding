from pathlib import Path

from extensions.ai_coding.workflow import run_minimum_bugfix_loop


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


PATCH = """diff --git a/src/user_service.py b/src/user_service.py
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


def test_minimum_bugfix_loop_runs_patch_and_pytest():
    result = run_minimum_bugfix_loop(
        FIXTURE,
        "修复 user_service 登录空密码报错，空密码应该返回 False",
        patch_text=PATCH,
        project_id="demo",
    )
    assert result.patch_preview is not None
    assert result.patch_preview.valid is True
    assert result.sandbox_result is not None
    assert result.sandbox_result.exit_code == 0
    assert "src/user_service.py" in result.context_package.markdown


def test_minimum_bugfix_loop_can_generate_patch():
    result = run_minimum_bugfix_loop(
        FIXTURE,
        "fix empty password login bug and return False",
        project_id="demo",
    )
    assert result.generated_patch is not None
    assert result.generated_patch.generated is True
    assert result.patch_preview is not None
    assert result.patch_preview.valid is True
    assert result.sandbox_result is not None
    assert result.sandbox_result.exit_code == 0
