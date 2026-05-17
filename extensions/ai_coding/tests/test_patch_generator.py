from pathlib import Path

from extensions.ai_coding.context_engineering import build_context_package
from extensions.ai_coding.patch_generator import generate_patch_for_task
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
    generated = generate_patch_for_task(task, context)
    assert generated.generated is True
    assert generated.strategy == "rule_based_empty_password"
    assert "return False" in generated.patch_text
    preview = validate_patch_against_repo(FIXTURE, generated.patch_text)
    assert preview.valid is True
