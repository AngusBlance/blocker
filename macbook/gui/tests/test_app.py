from textual.widgets import Button, ContentSwitcher, Input, Static

from blocker_gui.app import GuiApp, UnlockModal
from blocklib.core import HostsBlocker


def site_button(app, name):
    return next(b for b in app.query("#site-list Button") if b.name == name)


async def test_opens_on_the_dashboard_showing_not_blocked(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test():
        assert app.query_one(ContentSwitcher).current == "dashboard"
        assert "not blocked" in str(app.query_one("#status", Static).render())


async def test_clicking_sites_in_the_nav_switches_section(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#nav-sites")
        assert app.query_one(ContentSwitcher).current == "sites"
        assert [b.name for b in app.query("#site-list Button")] == [
            "Netflix",
            "YouTube",
            "Crunchyroll",
        ]


async def test_clicking_a_site_blocks_all_its_domains(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#nav-sites")
        site_button(app, "Netflix").press()
        await pilot.pause()
        assert HostsBlocker(isolated).blocked_urls == {"netflix.com", "www.netflix.com"}
        assert str(site_button(app, "Netflix").label).startswith("(x)")


async def test_block_all_button_blocks_every_site(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#block-all")
        assert len(HostsBlocker(isolated).blocked_urls) == 9
        assert "BLOCKED" in str(app.query_one("#status", Static).render())


async def test_unblocking_asks_for_the_password_and_wrong_one_keeps_it_blocked(
    isolated,
):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#nav-sites")
        site_button(app, "Netflix").press()
        await pilot.pause()
        site_button(app, "Netflix").press()
        await pilot.pause()
        assert isinstance(app.screen, UnlockModal)
        app.screen.query_one(Input).value = "wrong"
        await pilot.click("#unlock")
        assert "netflix.com" in HostsBlocker(isolated).blocked_urls


async def test_right_password_unblocks(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#nav-sites")
        site_button(app, "Netflix").press()
        await pilot.pause()
        site_button(app, "Netflix").press()
        await pilot.pause()
        app.screen.query_one(Input).value = "pw"
        await pilot.click("#unlock")
        assert HostsBlocker(isolated).blocked_urls == set()


async def test_keep_it_blocked_cancels(isolated):
    app = GuiApp(hosts_path=isolated)
    async with app.run_test() as pilot:
        await pilot.click("#nav-sites")
        site_button(app, "YouTube").press()
        await pilot.pause()
        site_button(app, "YouTube").press()
        await pilot.pause()
        await pilot.click("#cancel")
        assert not isinstance(app.screen, UnlockModal)
        assert "youtube.com" in HostsBlocker(isolated).blocked_urls
        assert isinstance(app.query_one("#block-all"), Button)
