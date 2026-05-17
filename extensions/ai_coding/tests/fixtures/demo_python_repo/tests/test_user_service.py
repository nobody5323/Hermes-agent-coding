from user_service import login


def test_login_success():
    assert login("alice", "secret") is True


def test_login_wrong_password():
    assert login("alice", "bad") is False


def test_login_empty_password_returns_false():
    assert login("alice", "") is False
