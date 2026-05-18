import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from extensions.ai_coding.context_engineering import build_context_package
from extensions.ai_coding.memory import load_lessons, retrieve_lessons, write_lesson
from extensions.ai_coding.rag.retriever import retrieve_code_context
from extensions.ai_coding.schemas import CodingTask
from extensions.ai_coding.tools.repository import scan_repository


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"


@contextmanager
def workspace_temp_repo():
    temp_root = Path(".tmp-tests")
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memory-", dir=temp_root) as temp_dir:
        repo = Path(temp_dir) / "repo"
        shutil.copytree(FIXTURE, repo, ignore=shutil.ignore_patterns("__pycache__"))
        yield repo


def test_repository_lessons_can_be_written_retrieved_and_injected_into_context():
    with workspace_temp_repo() as repo:
        lesson = write_lesson(
            repo,
            task="fix empty password login bug",
            summary="Empty password login should return False instead of raising.",
        )

        assert load_lessons(repo) == [lesson]
        retrieved_lessons = retrieve_lessons(repo, "login password bug")
        assert retrieved_lessons

        task = CodingTask(task_id="t1", user_request="fix login password bug", repo_path=str(repo))
        context = build_context_package(
            task,
            scan_repository(repo),
            retrieve_code_context(repo, task.user_request),
            lessons=retrieved_lessons,
        )
        assert "Empty password login should return False" in context.markdown
