from blocker_tui.app import BlockerApp


async def test_q_quits_the_app():
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert not app.is_running
