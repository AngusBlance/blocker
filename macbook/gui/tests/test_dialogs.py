import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from blocker_gui import dialogs
from blocker_gui.app import create_app

# Imported at collection time, before conftest swaps it out for every test.
REAL_ENSURE_ADMIN = dialogs.ensure_admin


def make_unlock(qtbot, password="abc123"):
    create_app([])
    dialog = dialogs.UnlockDialog("YouTube", password)
    qtbot.addWidget(dialog)
    return dialog


def test_unlock_button_waits_for_the_full_length(qtbot):
    dialog = make_unlock(qtbot)
    qtbot.keyClicks(dialog.input, "abc12")
    assert not dialog.unlock_button.isEnabled()
    assert dialog.counter.text() == "5 / 6"
    qtbot.keyClicks(dialog.input, "3")
    assert dialog.unlock_button.isEnabled()


def test_right_password_accepts(qtbot):
    dialog = make_unlock(qtbot)
    qtbot.keyClicks(dialog.input, "abc123")
    qtbot.mouseClick(dialog.unlock_button, Qt.LeftButton)
    assert dialog.result() == dialogs.QDialog.Accepted


def test_wrong_password_says_so_and_stays_open(qtbot):
    dialog = make_unlock(qtbot)
    dialog.show()
    qtbot.keyClicks(dialog.input, "abc999")
    qtbot.mouseClick(dialog.unlock_button, Qt.LeftButton)
    assert dialog.isVisible()
    assert dialog.counter.text() == "that doesn't match."


def test_paste_is_ignored(qtbot):
    dialog = make_unlock(qtbot)
    QApplication.clipboard().setText("abc123")
    # The platform's own paste shortcut: Cmd+V on macOS, Ctrl+V elsewhere.
    qtbot.keySequence(dialog.input, QKeySequence(QKeySequence.Paste))
    assert dialog.input.text() == ""


def test_sudo_password_is_fed_on_stdin_to_validate(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs.get("input")))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(dialogs.subprocess, "run", fake_run)
    assert dialogs.sudo_with_password("hunter2")
    assert calls == [(["sudo", "-S", "-v", "-p", ""], "hunter2\n")]


def test_ensure_admin_skips_the_prompt_when_sudo_is_cached(monkeypatch):
    monkeypatch.setattr(dialogs, "sudo_is_cached", lambda: True)
    monkeypatch.setattr(
        dialogs.AdminDialog, "exec", lambda self: (_ for _ in ()).throw(AssertionError)
    )
    assert REAL_ENSURE_ADMIN()
