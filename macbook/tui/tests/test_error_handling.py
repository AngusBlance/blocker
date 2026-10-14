import subprocess

from blocker_tui.app import BlockerApp


async def test_block_failure_notifies_error_and_does_not_crash(monkeypatch):
    def boom(self, urls):
        raise subprocess.CalledProcessError(1, ["sudo", "cp"])

    monkeypatch.setattr("blocker_tui.app.HostsBlocker.block_all", boom)
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )
    notifications = []
    monkeypatch.setattr(
        "blocker_tui.app.BlockerApp.notify",
        lambda self, message, **kwargs: notifications.append(
            (message, kwargs.get("severity"))
        ),
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")  # would block; the call raises
        assert any(sev == "error" for _msg, sev in notifications)


async def test_successful_block_notifies_information(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all", lambda self, urls: None
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )
    notifications = []
    monkeypatch.setattr(
        "blocker_tui.app.BlockerApp.notify",
        lambda self, message, **kwargs: notifications.append(
            (message, kwargs.get("severity"))
        ),
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert any("Blocked" in msg for msg, _sev in notifications)


async def test_wrong_password_notifies_error(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.unblock_all", lambda self, urls: None
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")
    notifications = []
    monkeypatch.setattr(
        "blocker_tui.app.BlockerApp.notify",
        lambda self, message, **kwargs: notifications.append(
            (message, kwargs.get("severity"))
        ),
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        await pilot.press("9", "9", "9", "9", "enter")
        assert ("Incorrect password", "error") in notifications
