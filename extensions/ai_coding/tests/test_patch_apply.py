import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

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
