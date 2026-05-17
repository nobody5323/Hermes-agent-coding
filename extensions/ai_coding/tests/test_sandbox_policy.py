from extensions.ai_coding.sandbox.policy import build_docker_limits, is_dangerous_command
from extensions.ai_coding.sandbox.runner import build_docker_run_command, find_docker_cli, run_in_docker


FIXTURE_REPO = "extensions/ai_coding/tests/fixtures/demo_python_repo"


def test_dangerous_command_detection():
    assert is_dangerous_command("rm -rf /") is True
    assert is_dangerous_command("python -m pytest") is False


def test_docker_limits_are_restrictive():
    limits = build_docker_limits()
    assert limits["network"] == "none"
    assert limits["memory"]


def test_build_docker_run_command_uses_isolation_flags():
    command = build_docker_run_command(FIXTURE_REPO, "python -m pytest", image="test-image")
    assert command[1:5] == ["run", "--rm", "--network", "none"]
    assert command[0].endswith("docker") or command[0].endswith("docker.exe")
    assert "--cpus" in command
    assert "--memory" in command
    assert "-v" in command
    assert "test-image" in command
    assert command[-3:] == ["/bin/sh", "-lc", "python -m pytest"]


def test_run_in_docker_reports_missing_cli(monkeypatch):
    monkeypatch.setattr("extensions.ai_coding.sandbox.runner.find_docker_cli", lambda: None)
    result = run_in_docker(FIXTURE_REPO, "python -m pytest")
    assert result.exit_code == 127
    assert result.rejected is True
    assert "docker CLI" in result.summary


def test_find_docker_cli_can_be_absent(monkeypatch):
    monkeypatch.setattr("extensions.ai_coding.sandbox.runner.shutil.which", lambda name: None)
    monkeypatch.setattr("extensions.ai_coding.sandbox.runner.Path.exists", lambda self: False)
    assert find_docker_cli() is None
