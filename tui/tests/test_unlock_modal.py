from blocker_tui.app import BlockerApp, Input, UnlockModal


async def test_on_mount_sets_up_a_password_when_none_exists(monkeypatch):
    calls = []
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: False)
    monkeypatch.setattr("blocker_tui.app.setup_password", lambda: calls.append(1))

    app = BlockerApp()
    async with app.run_test():
        pass

    assert calls == [1]


async def test_on_mount_does_not_recreate_an_existing_password(monkeypatch):
    calls = []
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.setup_password", lambda: calls.append(1))

    app = BlockerApp()
    async with app.run_test():
        pass

    assert calls == []


async def test_blocked_group_opens_modal_showing_the_real_password(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert isinstance(app.screen, UnlockModal)
        assert app.screen.password == "0000"


async def test_wrong_password_does_not_unblock(monkeypatch):
    unblock_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.unblock_all",
        lambda self, urls: unblock_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        await pilot.press("9", "9", "9", "9", "enter")
        assert unblock_calls == []


async def test_escape_cancels_without_unblocking(monkeypatch):
    unblock_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.unblock_all",
        lambda self, urls: unblock_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert isinstance(app.screen, UnlockModal)
        await pilot.press("escape")
        assert not isinstance(app.screen, UnlockModal)
        assert unblock_calls == []


async def test_blocking_an_unblocked_group_never_shows_the_modal(monkeypatch):
    block_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all",
        lambda self, urls: block_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert not isinstance(app.screen, UnlockModal)
        assert len(block_calls) == 1


async def test_no_password_set_fails_open_and_unblocks_directly(monkeypatch):
    unblock_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.unblock_all",
        lambda self, urls: unblock_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: False)

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert not isinstance(app.screen, UnlockModal)
        assert len(unblock_calls) == 1


async def test_modal_input_is_focused_on_mount(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: True
    )
    monkeypatch.setattr("blocker_tui.app.is_password_set", lambda: True)
    monkeypatch.setattr("blocker_tui.app.get_password", lambda: "0000")

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert isinstance(app.focused, Input)
