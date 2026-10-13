import pytest


@pytest.fixture(autouse=True)
def isolated_password(tmp_path, monkeypatch):
    """Keeps every test off the real ~/.blocker/password.txt. BlockerApp's
    on_mount() calls setup_password() whenever none exists - without this,
    simply running the test suite on a fresh machine would create a real
    password file as a side effect. Tests that care about specific password
    behavior monkeypatch these themselves, which overrides this fixture."""
    password_path = tmp_path / "password.txt"

    def fake_is_password_set():
        return password_path.exists()

    def fake_setup_password():
        password_path.write_text("test-password")
        return "test-password"

    def fake_get_password():
        return password_path.read_text().strip()

    monkeypatch.setattr("blocker_tui.app.is_password_set", fake_is_password_set)
    monkeypatch.setattr("blocker_tui.app.setup_password", fake_setup_password)
    monkeypatch.setattr("blocker_tui.app.get_password", fake_get_password)
