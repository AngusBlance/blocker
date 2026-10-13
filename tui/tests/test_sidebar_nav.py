from blocker_tui.app import SECTIONS, BlockerApp, Sidebar


async def test_initial_selection_is_first_section():
    app = BlockerApp()
    async with app.run_test():
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == 0


async def test_j_moves_selection_down():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == 1


async def test_k_moves_selection_up():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")
        await pilot.press("j")
        await pilot.press("k")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == 1


async def test_cursor_does_not_go_below_zero():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("k")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == 0


async def test_cursor_does_not_exceed_last_section():
    app = BlockerApp()
    async with app.run_test() as pilot:
        for _ in range(len(SECTIONS) + 3):
            await pilot.press("j")
        sidebar = app.query_one(Sidebar)
        assert sidebar.selected_index == len(SECTIONS) - 1


async def test_sidebar_renders_all_section_names():
    app = BlockerApp()
    async with app.run_test():
        sidebar = app.query_one(Sidebar)
        rendered = sidebar.render()
        for name in SECTIONS:
            assert name in rendered
