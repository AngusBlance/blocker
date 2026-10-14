import os

# Headless: tests must run without a display (CI, ssh).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from blocklib.core import HostsBlocker  # noqa: E402

BASE_HOSTS = "127.0.0.1 localhost\n::1 localhost\n"
PASSWORD = "unlock-password-for-tests"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Keeps every test off the real /etc/hosts, sudo, password file and sync
    daemon. Returns the temporary hosts file to point the window at."""
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE_HOSTS)
    monkeypatch.setattr(
        HostsBlocker,
        "_commit",
        lambda self, content: self.hosts_path.write_text(content),
    )
    monkeypatch.setattr("blocker_gui.dialogs.ensure_admin", lambda parent=None: True)
    monkeypatch.setattr("blocker_gui.app.notify_external_daemon", lambda: None)
    monkeypatch.setattr("blocker_gui.app.sync_daemon_running", lambda: False)
    monkeypatch.setattr("blocker_gui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_gui.app.setup_password", lambda: PASSWORD)
    monkeypatch.setattr("blocker_gui.app.get_password", lambda: PASSWORD)
    return hosts


@pytest.fixture
def window(qtbot, isolated):
    from blocker_gui.app import BlockerWindow, create_app

    create_app([])
    w = BlockerWindow(hosts_path=isolated)
    qtbot.addWidget(w)
    w.show()
    return w
