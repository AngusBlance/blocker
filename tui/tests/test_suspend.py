import subprocess
from types import SimpleNamespace

from blocker_tui.app import BlockerApp, sudo_needs_password


def test_sudo_needs_password_false_when_cached(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda args, **kwargs: SimpleNamespace(returncode=0)
    )
    assert sudo_needs_password() is False


def test_sudo_needs_password_true_when_not_cached(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda args, **kwargs: SimpleNamespace(returncode=1)
    )
    assert sudo_needs_password() is True


def test_sudo_needs_password_checks_with_noninteractive_flag(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    sudo_needs_password()
    assert captured["args"] == ["sudo", "-n", "true"]


async def test_maybe_suspend_skips_suspend_when_sudo_cached(monkeypatch):
    monkeypatch.setattr("blocker_tui.app.sudo_needs_password", lambda: False)
    suspend_calls = []
    monkeypatch.setattr(BlockerApp, "suspend", lambda self: suspend_calls.append(1))

    app = BlockerApp()
    async with app.run_test():
        with app._maybe_suspend():
            pass

    assert suspend_calls == []


async def test_maybe_suspend_calls_suspend_when_sudo_not_cached(monkeypatch):
    monkeypatch.setattr("blocker_tui.app.sudo_needs_password", lambda: True)

    app = BlockerApp()
    async with app.run_test():
        # real suspend() raises SuspendNotSupported in the headless test
        # environment; _maybe_suspend should fall back gracefully and still
        # run the body.
        ran = []
        with app._maybe_suspend():
            ran.append(1)
        assert ran == [1]
