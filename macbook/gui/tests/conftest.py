import pytest

from blocklib.core import HostsBlocker

BASE_HOSTS = "127.0.0.1 localhost\n::1 localhost\n"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Keeps every test off the real /etc/hosts, sudo, password file and sync
    daemon. Returns the temporary hosts file the app should be pointed at."""
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE_HOSTS)
    monkeypatch.setattr(
        HostsBlocker,
        "_commit",
        lambda self, content: self.hosts_path.write_text(content),
    )
    monkeypatch.setattr("blocker_gui.app.sudo_needs_password", lambda: False)
    monkeypatch.setattr("blocker_gui.app.notify_external_daemon", lambda: None)

    password_path = tmp_path / "password.txt"
    monkeypatch.setattr("blocker_gui.app.is_password_set", password_path.exists)
    monkeypatch.setattr(
        "blocker_gui.app.setup_password",
        lambda: password_path.write_text("pw") and "pw",
    )
    monkeypatch.setattr(
        "blocker_gui.app.get_password", lambda: password_path.read_text()
    )
    return hosts
