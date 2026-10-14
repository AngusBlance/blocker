from blocker_tui.app import BlockerApp, perform_block


def test_perform_block_calls_block_all_with_known_domain_urls(monkeypatch, tmp_path):
    captured = {}

    def fake_block_all(self, urls):
        captured["urls"] = urls
        captured["hosts_path"] = self.hosts_path

    monkeypatch.setattr("blocker_tui.app.HostsBlocker.block_all", fake_block_all)
    hosts = tmp_path / "hosts"
    perform_block(hosts)

    assert "netflix.com" in captured["urls"]
    assert "googlevideo.com" in captured["urls"]
    assert captured["hosts_path"] == hosts


async def test_pressing_b_on_sites_content_triggers_block(monkeypatch):
    calls = []
    monkeypatch.setattr("blocker_tui.app.perform_block", lambda: calls.append(1))

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")  # sidebar -> sites, focus content
        await pilot.press("b")
        assert len(calls) == 1


async def test_pressing_b_notifies_extension_sync_server(monkeypatch):
    monkeypatch.setattr("blocker_tui.app.perform_block", lambda: None)
    notify_calls = []
    monkeypatch.setattr(
        "blocker_tui.app.BlockerApp._notify_sync", lambda self: notify_calls.append(1)
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        await pilot.press("b")
        assert len(notify_calls) == 1


async def test_pressing_b_while_sidebar_focused_does_not_block(monkeypatch):
    calls = []
    monkeypatch.setattr("blocker_tui.app.perform_block", lambda: calls.append(1))

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        await pilot.press("b")
        assert len(calls) == 0


async def test_pressing_b_on_dashboard_content_does_not_block(monkeypatch):
    calls = []
    monkeypatch.setattr("blocker_tui.app.perform_block", lambda: calls.append(1))

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")
        await pilot.press("b")
        assert len(calls) == 0
