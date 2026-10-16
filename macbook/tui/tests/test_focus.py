"""The focus section: start focus with the sites to allow, end it early."""

import json

from blocker_tui import app as app_module
from blocker_tui.app import BlockerApp, Content, Input, UnlockModal, dashboard_text
from blocker_tui.focus_editor import FocusEditor
from blocklib import focus as focus_mode

NOW = 1_760_000_000_000  # 2025-10-09 09:53 UTC


async def open_focus(pilot):
    await pilot.press("j", "j", "j", "l")  # dashboard → sites → schedule → focus


def stored(path):
    return json.loads(path.read_text())


async def test_start_focus_with_a_preset_and_a_typed_site(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        assert "(s) start focus" in str(app.query_one(Content).render())
        await pilot.press("s")
        editor = app.screen
        assert isinstance(editor, FocusEditor)
        assert editor.focused.id == "site-0"  # Google Docs
        await pilot.press("x")
        await pilot.press("j")  # the "add a site" box
        assert editor.focused.id == "new-site"
        await pilot.press("enter", *"https://en.wikipedia.org/wiki/Exam", "enter")
        assert "en.wikipedia.org" in editor.site_names
        await pilot.press("j", "h", "h", "h")  # lengths row, to 25m
        assert editor.focused.id == "length-25"
        await pilot.press("enter", "ctrl+s")
        assert not isinstance(app.screen, FocusEditor)

        saved = stored(isolated_focus)
        assert saved["endsAt"] == NOW + 25 * 60_000
        assert saved["sites"] == ["Google Docs", "en.wikipedia.org"]
        assert saved["domains"] == [
            "docs.google.com",
            "accounts.google.com",
            "en.wikipedia.org",
        ]
        text = str(app.query_one(Content).render())
        assert "on until" in text and "25m left" in text
        assert "Google Docs, en.wikipedia.org" in text


async def test_it_wont_start_without_a_site(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "ctrl+s")
        assert isinstance(app.screen, FocusEditor)
        assert not isolated_focus.exists()
        await pilot.press("j", "enter", *"not a site", "enter")
        error = str(app.screen.query_one("#editor-error").render())
        assert "isn't a site" in error


async def test_a_blocked_site_is_flagged_because_it_stays_blocked(
    isolated_focus, monkeypatch
):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(
        app_module.HostsBlocker,
        "all_blocked_urls",
        property(lambda self: {"www.udemy.com"}),
    )
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "l", "x")  # Udemy
        summary = str(app.screen.query_one("#summary").render())
        assert "udemy.com is blocked, so it stays blocked." in summary


async def test_ending_focus_early_needs_the_password(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    focus_mode.save_start(
        focus_mode.Focus(NOW + 3_600_000, ("Udemy",), ("udemy.com",)),
        isolated_focus,
        NOW,
    )
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        await pilot.press("s")  # already on: no editor
        assert not isinstance(app.screen, FocusEditor)
        await pilot.press("e")
        assert isinstance(app.screen, UnlockModal)
        await pilot.press("escape")
        assert isolated_focus.exists()
        await pilot.press("e")
        app.screen.query_one(Input).value = "test-password"
        await pilot.press("enter")
        assert not isolated_focus.exists()
        assert "(s) start focus" in str(app.query_one(Content).render())


def test_dashboard_says_focus(isolated_focus, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    assert "FOCUS" not in dashboard_text(hosts)
    focus_mode.save_start(
        focus_mode.Focus(NOW + 3_600_000, ("Udemy",), ("udemy.com",)),
        isolated_focus,
        NOW,
    )
    text = dashboard_text(hosts)
    assert "state           FOCUS" in text and "allows Udemy" in text
