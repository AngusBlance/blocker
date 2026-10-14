from blocker_tui.app import BlockerApp, Content, site_groups


async def test_l_from_sidebar_just_focuses_content(monkeypatch):
    block_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all",
        lambda self, urls: block_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")  # sidebar -> sites
        await pilot.press("l")  # first l: focus content only
        assert app.focus_pane == "content"
        assert block_calls == []


async def test_toggle_notifies_extension_sync_server(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all", lambda self, urls: None
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )
    notify_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.BlockerApp._notify_sync", lambda self: notify_calls.append(1)
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("l")
        assert len(notify_calls) == 1


async def test_l_on_focused_sites_content_blocks_unblocked_group(monkeypatch):
    block_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all",
        lambda self, urls: block_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")  # focus content, on sites
        await pilot.press("l")  # second l: toggle
        assert len(block_calls) == 1


async def test_l_on_focused_sites_content_unblocks_blocked_group(monkeypatch):
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
        await pilot.press("l")  # opens the unlock modal instead of unblocking directly
        assert len(unblock_calls) == 0
        await pilot.press("0", "0", "0", "0", "enter")
        assert len(unblock_calls) == 1
        assert unblock_calls[0] == [d.url for d in site_groups()[0][1]]


async def test_enter_behaves_same_as_l_for_toggling(monkeypatch):
    block_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all",
        lambda self, urls: block_calls.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("enter")
        assert len(block_calls) == 1


async def test_toggle_targets_every_domain_in_the_group_under_cursor(monkeypatch):
    toggled = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all",
        lambda self, urls: toggled.append(urls),
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")  # sites, focus content
        await pilot.press("j", "j")  # move cursor to third group (Crunchyroll)
        await pilot.press("l")  # toggle it
        _name, expected_members = site_groups()[2]
        expected_urls = [d.url for d in expected_members]
        assert toggled == [expected_urls]


async def test_toggle_does_not_reset_cursor_position(monkeypatch):
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all", lambda self, urls: None
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l", "j", "j")
        content = app.query_one(Content)
        assert content.site_index == 2
        await pilot.press("l")
        assert content.site_index == 2


async def test_toggle_is_noop_outside_sites_section(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all", lambda self, urls: calls.append(urls)
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.unblock_all",
        lambda self, urls: calls.append(urls),
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")  # focus content while on dashboard
        await pilot.press("l")  # would toggle if this were sites
        assert calls == []
