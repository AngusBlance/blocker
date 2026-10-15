from blocker_tui.app import (
    BlockerApp,
    Content,
    site_groups,
    sites_text,
    sites_with_status,
)

BASE = "127.0.0.1 localhost\n::1 localhost\n"
WITH_NETFLIX_PARTIALLY_BLOCKED = (
    BASE
    + "# BLOCKER-BEGIN\n"
    + "127.0.0.1 netflix.com\n"
    + "::1 netflix.com\n"
    + "# BLOCKER-END\n"
)
WITH_NETFLIX_FULLY_BLOCKED = (
    BASE
    + "# BLOCKER-BEGIN\n"
    + "127.0.0.1 netflix.com\n"
    + "::1 netflix.com\n"
    + "127.0.0.1 www.netflix.com\n"
    + "::1 www.netflix.com\n"
    + "# BLOCKER-END\n"
)


def test_sites_with_status_marks_blocked_domains(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(WITH_NETFLIX_FULLY_BLOCKED)
    domains = sites_with_status(hosts)
    blocked_urls = {d.url for d in domains if d.is_blocked}
    assert blocked_urls == {"netflix.com", "www.netflix.com"}


def test_sites_with_status_all_unblocked_when_no_block(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    domains = sites_with_status(hosts)
    assert all(not d.is_blocked for d in domains)


def test_site_groups_groups_domains_by_service_name(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    groups = dict(site_groups(hosts))
    assert set(groups.keys()) == {
        "Netflix",
        "YouTube",
        "Crunchyroll",
        "Instagram",
        "TikTok",
        "Facebook",
    }
    assert {d.url for d in groups["Netflix"]} == {"netflix.com", "www.netflix.com"}
    assert {d.url for d in groups["Crunchyroll"]} == {
        "crunchyroll.com",
        "www.crunchyroll.com",
    }


def test_sites_text_shows_fully_blocked_group(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(WITH_NETFLIX_FULLY_BLOCKED)
    text = sites_text(0, hosts)
    assert "(x) Netflix" in text
    assert "( ) YouTube" in text
    assert "( ) Crunchyroll" in text


def test_sites_text_shows_partially_blocked_group(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(WITH_NETFLIX_PARTIALLY_BLOCKED)
    text = sites_text(0, hosts)
    assert "(~) Netflix" in text


def test_sites_text_marks_cursor_position(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    text = sites_text(1, hosts)
    selected_lines = [line for line in text.splitlines() if line.startswith(">")]
    assert len(selected_lines) == 1


async def test_sites_section_shows_known_service_names():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        content = app.query_one(Content)
        assert content.section == "sites"
        rendered = content.render()
        assert "Netflix" in rendered
        assert "YouTube" in rendered
        assert "Crunchyroll" in rendered


def test_block_state_survives_closing_and_reopening_the_app(tmp_path):
    """
    No JSON cache, no DNS query - state is read live from the hosts file
    every time, so there's nothing to "restore" on reopen. This simulates:
    block a site, close the app, open a brand new instance.
    """
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)

    from blocklib.core import HostsBlocker

    content = hosts.read_text()
    for url in ("netflix.com", "www.netflix.com"):
        content = HostsBlocker._insert_domain(content, url)
    hosts.write_text(content)

    text = sites_text(0, hosts)
    assert "(x) Netflix" in text
    domains = sites_with_status(hosts)
    assert all(d.is_blocked for d in domains if d.name == "Netflix")
