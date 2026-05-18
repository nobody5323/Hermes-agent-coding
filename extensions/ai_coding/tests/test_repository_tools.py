from pathlib import Path

from extensions.ai_coding.tools.repository import read_file_slice, scan_repository, search_code
from extensions.ai_coding.rag.retriever import expand_query, retrieve_code_context


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


def test_scan_repository_detects_python_project():
    summary = scan_repository(FIXTURE)
    assert summary.total_files >= 5
    assert summary.languages["python"] >= 4
    assert summary.has_readme is True
    assert summary.has_tests is True
    assert "python -m pytest" in summary.test_commands


def test_read_file_slice_stays_inside_repo():
    text = read_file_slice(FIXTURE, "src/user_service.py", 1, 4)
    assert "USERS" in text


def test_search_code_returns_context():
    results = search_code(FIXTURE, "empty password")
    assert results
    assert results[0]["path"] == "src/user_service.py"


def test_enhanced_retriever_uses_query_expansion_and_failure_feedback():
    expanded = expand_query("login failed")
    assert "auth" in expanded
    results = retrieve_code_context(
        FIXTURE,
        "failing assertion",
        feedback="tests/test_user_service.py::test_login_empty_password_returns_false failed",
        top_k=5,
    )
    assert any(item.chunk.path == "tests/test_user_service.py" for item in results)
    assert any("failure feedback matched path" in item.reasons for item in results)
