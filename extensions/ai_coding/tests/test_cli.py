import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from extensions.ai_coding.cli import main


FIXTURE_REPO = "extensions/ai_coding/tests/fixtures/demo_python_repo"
PATCH_FILE = "examples/bugfix_empty_password.diff"
FIXTURE_PATH = Path(FIXTURE_REPO)


@contextmanager
def workspace_temp_repo():
    temp_root = Path(".tmp-tests")
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cli-", dir=temp_root) as temp_dir:
        repo = Path(temp_dir) / "repo"
        shutil.copytree(FIXTURE_PATH, repo, ignore=shutil.ignore_patterns("__pycache__"))
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


def test_cli_run_local_sandbox(capsys):
    exit_code = main(
        [
            "run",
            "--repo",
            FIXTURE_REPO,
            "--task",
            "fix empty password login bug",
            "--patch",
            PATCH_FILE,
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Patch preview: 1 file(s), +1/-1, valid=True" in output
    assert "Sandbox: exit=0" in output


def test_cli_run_json_output(capsys):
    exit_code = main(
        [
            "run",
            "--repo",
            FIXTURE_REPO,
            "--task",
            "fix empty password login bug",
            "--patch",
            PATCH_FILE,
            "--json",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"final_summary"' in output
    assert '"sandbox_result"' in output


def test_cli_run_auto_patch(capsys):
    exit_code = main(
        [
            "run",
            "--repo",
            FIXTURE_REPO,
            "--task",
            "fix empty password login bug and return False",
            "--auto-patch",
            "--patch-generator",
            "rule",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Patch generator: generated=True" in output
    assert "Sandbox: exit=0" in output


def test_cli_requires_patch_or_auto_patch(capsys):
    exit_code = main(
        [
            "run",
            "--repo",
            FIXTURE_REPO,
            "--task",
            "fix empty password login bug",
        ]
    )
    error = capsys.readouterr().err
    assert exit_code == 2
    assert "--auto-patch" in error


def test_cli_llm_generator_without_key_fails_cleanly(capsys, monkeypatch):
    monkeypatch.delenv("AI_CODING_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    exit_code = main(
        [
            "run",
            "--repo",
            FIXTURE_REPO,
            "--task",
            "fix empty password login bug",
            "--auto-patch",
            "--patch-generator",
            "llm",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 2
    assert "Patch generator errors:" in output


def test_cli_apply_modifies_repo_after_sandbox_passes(capsys):
    with workspace_temp_repo() as repo:
        exit_code = main(
            [
                "run",
                "--repo",
                str(repo),
                "--task",
                "fix empty password login bug",
                "--patch",
                PATCH_FILE,
                "--apply",
            ]
        )
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Apply: applied=True" in output
        assert "return False" in (repo / "src" / "user_service.py").read_text(encoding="utf-8")


def test_cli_commit_writes_review_artifacts_and_commit(capsys):
    with workspace_temp_git_repo() as repo:
        exit_code = main(
            [
                "run",
                "--repo",
                str(repo),
                "--task",
                "fix empty password login bug",
                "--patch",
                PATCH_FILE,
                "--commit",
                "--branch-name",
                "ai-coding/cli-commit",
                "--commit-message",
                "Fix empty password login",
            ]
        )
        output = capsys.readouterr().out
        assert exit_code == 0
        assert "Branch: ai-coding/cli-commit, created=True" in output
        assert "Commit:" in output
        assert (repo / ".ai-coding" / "runs").exists()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True)
        assert status.stdout == ""
