USERS = {
    "alice": "secret",
}


def login(username: str, password: str) -> bool:
    if password == "":
        raise ValueError("empty password")
    return USERS.get(username) == password
