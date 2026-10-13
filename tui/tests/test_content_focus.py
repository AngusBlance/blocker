from blocker_tui.app import SECTIONS, BlockerApp, Content, Sidebar


async def test_default_focus_is_sidebar():
    app = BlockerApp()
    async with app.run_test():
        assert app.focus_pane == "sidebar"


async def test_l_moves_focus_to_content():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")
        assert app.focus_pane == "content"


async def test_h_moves_focus_back_to_sidebar():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")
        await pilot.press("h")
        assert app.focus_pane == "sidebar"


async def test_content_updates_when_cursor_moves_down():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        content = app.query_one(Content)
        assert content.section == SECTIONS[1]


async def test_content_updates_when_cursor_moves_up():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        await pilot.press("j")
        await pilot.press("k")
        content = app.query_one(Content)
        assert content.section == SECTIONS[1]


async def test_focused_pane_gets_css_class():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("l")
        content = app.query_one(Content)
        sidebar = app.query_one(Sidebar)
        assert content.has_class("focused-pane")
        assert not sidebar.has_class("focused-pane")


async def test_sidebar_has_focused_class_by_default():
    app = BlockerApp()
    async with app.run_test():
        sidebar = app.query_one(Sidebar)
        assert sidebar.has_class("focused-pane")
