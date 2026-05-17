from pathlib import Path

from extensions.ai_coding.tools.repository import read_file_slice, scan_repository, search_code


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
