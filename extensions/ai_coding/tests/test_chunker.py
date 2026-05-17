from pathlib import Path

from extensions.ai_coding.rag.chunker import chunk_file


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


def test_python_chunker_uses_symbols():
    chunks = chunk_file(FIXTURE / "src" / "user_service.py", repo_path=FIXTURE, project_id="demo")
    names = {chunk.symbol_name for chunk in chunks}
    assert "login" in names
    assert all(chunk.path == "src/user_service.py" for chunk in chunks)
