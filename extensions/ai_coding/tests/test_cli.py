from extensions.ai_coding.cli import main


FIXTURE_REPO = "extensions/ai_coding/tests/fixtures/demo_python_repo"
PATCH_FILE = "examples/bugfix_empty_password.diff"


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
