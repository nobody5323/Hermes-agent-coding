import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from extensions.ai_coding.schemas import SandboxResult
from extensions.ai_coding.tools.patch import apply_patch_to_repo


FIXTURE = Path(__file__).parent / "fixtures" / "demo_python_repo"
PATCH_FILE = Path("examples/bugfix_empty_password.diff")


@contextmanager
def workspace_temp_repo():
    temp_root = Path(".tmp-tests")
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apply-", dir=temp_root) as temp_dir:
        repo = Path(temp_dir) / "repo"
        shutil.copytree(FIXTURE, repo, ignore=shutil.ignore_patterns("__pycache__"))
        yield repo


@contextmanager
def workspace_temp_git_repo():
    with workspace_temp_repo() as repo:
        subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "ai-coding@example.test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "AI Coding Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, text=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, text=True, capture_output=True)
        yield repo


def test_apply_patch_to_repo_modifies_real_worktree():
    with workspace_temp_repo() as repo:
        patch_text = PATCH_FILE.read_text(encoding="utf-8")

        result = apply_patch_to_repo(repo, patch_text)

        assert result.applied is True
        assert result.summary == "applied patch: 1 file(s), +1/-1"
        assert [item.path for item in result.files] == ["src/user_service.py"]
        assert "return False" in (repo / "src" / "user_service.py").read_text(encoding="utf-8")


def test_apply_patch_to_repo_rejects_invalid_patch():
    with workspace_temp_repo() as repo:
        result = apply_patch_to_repo(repo, "not a diff")

        assert result.applied is False
        assert "validation failed" in result.summary
        assert "raise ValueError" in (repo / "src" / "user_service.py").read_text(encoding="utf-8")


def test_apply_patch_to_repo_rejects_dirty_git_worktree():
    with workspace_temp_git_repo() as repo:
        (repo / "README.md").write_text("dirty\n", encoding="utf-8")
        patch_text = PATCH_FILE.read_text(encoding="utf-8")

        result = apply_patch_to_repo(repo, patch_text, create_branch=True, task_id="dirty-test")

        assert result.applied is False
        assert result.git_repo is True
        assert result.dirty_files
        assert "dirty" in result.summary
        assert "raise ValueError" in (repo / "src" / "user_service.py").read_text(encoding="utf-8")


def test_apply_patch_to_repo_creates_branch_artifacts_and_commit():
    with workspace_temp_git_repo() as repo:
        patch_text = PATCH_FILE.read_text(encoding="utf-8")
        sandbox = SandboxResult(command="python -m pytest", exit_code=0, summary="command succeeded")

        result = apply_patch_to_repo(
            repo,
            patch_text,
            task_id="commit-test",
            task="fix empty password login bug and return False",
            create_branch=True,
            branch_name="ai-coding/commit-test",
            save_artifacts=True,
            sandbox_result=sandbox,
            commit=True,
            commit_message="Fix empty password login",
            write_review=True,
        )

        assert result.applied is True
        assert result.branch_created is True
        assert result.branch_name == "ai-coding/commit-test"
        assert result.commit_sha
        assert result.patch_artifact_path == ".ai-coding/runs/commit-test/change.diff"
        assert result.pr_summary_path == ".ai-coding/runs/commit-test/pr_summary.md"
        assert result.test_report_path == ".ai-coding/runs/commit-test/test_report.md"
        assert "return False" in (repo / "src" / "user_service.py").read_text(encoding="utf-8")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True)
        assert status.stdout == ""
