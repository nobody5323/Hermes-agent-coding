from pathlib import Path

from extensions.ai_coding.context_engineering import build_context_package
from extensions.ai_coding.rag.retriever import retrieve_code_context
from extensions.ai_coding.schemas import CodingTask
from extensions.ai_coding.tools.repository import scan_repository


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


def test_context_package_contains_relevant_chunk():
    task = CodingTask(task_id="t1", user_request="fix empty password login bug", repo_path=str(FIXTURE))
    summary = scan_repository(FIXTURE)
    retrieved = retrieve_code_context(FIXTURE, task.user_request, project_id="demo", top_k=3)
    context = build_context_package(task, summary, retrieved, token_budget=1500)
    assert context.token_estimate <= context.token_budget
    assert "src/user_service.py" in context.markdown
