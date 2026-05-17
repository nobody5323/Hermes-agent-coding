"""Run the local AI Coding MVP loop against the demo repository."""

from __future__ import annotations

from pathlib import Path

from extensions.ai_coding.workflow import run_minimum_bugfix_loop


DEMO_REPO = Path("extensions/ai_coding/tests/fixtures/demo_python_repo")

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


def main() -> None:
    result = run_minimum_bugfix_loop(
        DEMO_REPO,
        "Fix user_service login: empty password should return False instead of raising.",
        patch_text=PATCH,
        project_id="demo",
    )
    print(result.final_summary)


if __name__ == "__main__":
    main()
