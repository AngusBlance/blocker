from blocker_tui.app import BlockerApp, Content, Sidebar, site_groups


async def test_jk_moves_sidebar_when_sidebar_focused():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == 1


async def test_jk_does_not_move_sidebar_when_content_focused():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")  # sidebar -> sites
        await pilot.press("l")  # focus content
        sidebar_index_before = app.query_one(Sidebar).selected_index
        await pilot.press("j")
        await pilot.press("j")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == sidebar_index_before


async def test_jk_moves_site_cursor_when_content_focused_on_sites():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")  # sidebar -> sites
        await pilot.press("l")  # focus content
        await pilot.press("j")
        await pilot.press("j")
        content = app.query_one(Content)
        assert content.site_index == 2


async def test_site_cursor_does_not_go_below_zero():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l", "k")
        content = app.query_one(Content)
        assert content.site_index == 0


async def test_site_cursor_does_not_exceed_last_row():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l")
        last = len(site_groups())  # the "Adult sites" row comes after them
        for _ in range(last + 5):
            await pilot.press("j")
        content = app.query_one(Content)
        assert content.site_index == last


async def test_jk_on_non_sites_section_leaves_site_cursor_unused():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")  # focus content while on dashboard
        await pilot.press("j")
        content = app.query_one(Content)
        assert content.section == "dashboard"
        assert content.site_index == 0


async def test_switching_section_resets_site_cursor():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "l", "j", "j")
        content = app.query_one(Content)
        assert content.site_index == 2
        await pilot.press("h", "j")
        assert content.site_index == 0
