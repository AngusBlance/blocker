from blocker_tui.app import BlockerApp, Content, dashboard_text, get_status

BASE = "127.0.0.1 localhost\n::1 localhost\n"
WITH_BLOCK = (
    BASE
    + "# BLOCKER-BEGIN\n"
    + "127.0.0.1 netflix.com\n"
    + "::1 netflix.com\n"
    + "# BLOCKER-END\n"
)


def test_get_status_false_when_no_block(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    assert get_status(hosts) is False


def test_get_status_true_when_block_present(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(WITH_BLOCK)
    assert get_status(hosts) is True


def test_dashboard_text_reflects_not_blocked(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    assert "not blocked" in dashboard_text(hosts)


def test_dashboard_text_reflects_blocked(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(WITH_BLOCK)
    assert "BLOCKED" in dashboard_text(hosts)
    assert "not blocked" not in dashboard_text(hosts)


def test_dashboard_text_shows_sync_server_running(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    text = dashboard_text(hosts, sync_running=True)
    assert "extension sync" in text
    assert "ws://" in text
    assert "NOT RUNNING" not in text


def test_dashboard_text_shows_sync_server_not_running_by_default(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    text = dashboard_text(hosts)
    assert "NOT RUNNING" in text


async def test_dashboard_content_renders_a_known_state():
    app = BlockerApp()
    async with app.run_test():
        content = app.query_one(Content)
        rendered = content.render()
        assert "STATUS" in rendered
        assert ("BLOCKED" in rendered) or ("not blocked" in rendered)
        assert "extension sync" in rendered


async def test_dashboard_reflects_real_sync_server_state():
    app = BlockerApp()
    async with app.run_test():
        content = app.query_one(Content)
        rendered = content.render()
        # sync_running can be True even when app._sync_server is None - e.g.
        # the background daemon already owns the port - so that's the
        # actual source of truth for what gets rendered, not _sync_server.
        if content.sync_running:
            assert "ws://" in rendered
        else:
            assert "NOT RUNNING" in rendered
