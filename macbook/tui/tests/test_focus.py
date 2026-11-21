"""The focus section: start focus with the sites to allow, end it early."""

import json
import sys

import pytest
from textual.content import Content as TextualContent

from blocker_tui import app as app_module
from blocker_tui.app import (
    BlockerApp,
    Content,
    Input,
    UnlockModal,
    dashboard_text,
    sections,
)
from blocker_tui.focus_editor import FocusEditor, match_app
from blocklib import focus as focus_mode
from blocklib.focus import AllowedApp

NOW = 1_760_000_000_000  # 2025-10-09 09:53 UTC

# The focus section is Linux only (the Mac's TUI has none yet), so the
# tests that open it only run there.
linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="focus is Linux only so far"
)

OBSIDIAN = AllowedApp("obsidian_obsidian", "Obsidian")
APPS = [
    AllowedApp("anki-desktop_anki-desktop", "Anki"),
    AllowedApp("discord_discord", "Discord"),
    OBSIDIAN,
    AllowedApp("org.gnome.TextEditor", "Text Editor"),
    AllowedApp("org.gnome.Calculator", "Calculator"),
]


async def open_focus(pilot):
    await pilot.press("j", "j", "j", "l")  # dashboard → sites → schedule → focus


def stored(path):
    return json.loads(path.read_text())


def test_the_focus_section_is_there_on_linux_only():
    assert "focus" in sections("linux")
    assert "focus" not in sections("darwin")
    # The Mac keeps its sections, in the order it had them.
    assert sections("darwin") == [
        "dashboard",
        "sites",
        "schedule",
        "unlock",
        "activity",
        "settings",
    ]


@linux_only
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


@linux_only
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


@linux_only
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


@linux_only
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


@pytest.mark.parametrize(
    "typed, name",
    [
        ("Obsidian", "Obsidian"),
        ("obsi", "Obsidian"),  # the start of its name
        ("  text  ", "Text Editor"),
        ("editor", "Text Editor"),  # a word in it
        ("obsidian_obsidian", "Obsidian"),  # its id
        ("d", "Discord"),  # the only one starting with d, though more hold one
    ],
)
def test_typed_apps_are_matched_by_name(typed, name):
    app, problem = match_app(typed, APPS)
    assert (app.name, problem) == (name, "")


def test_typed_apps_that_fit_none_or_several_say_so():
    assert match_app("", APPS) == (None, "")
    assert match_app("zzz", APPS) == (None, "no app called zzz.")
    # Starts none; is in four.
    assert match_app("i", APPS) == (
        None,
        "which one? Anki, Discord, Obsidian, Text Editor",
    )


@linux_only
async def test_start_focus_with_an_app_and_a_site(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(app_module, "choosable_apps", lambda: (APPS, []))
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s")
        editor = app.screen
        labels = [str(w.render()) for w in editor.query(".label")]
        assert any(label.startswith("always allowed: Chrome") for label in labels)
        await pilot.press("x")  # Google Docs
        await pilot.press("j", "j")  # past "add a site", to "add an app"
        assert editor.focused.id == "new-app"
        await pilot.press("enter", *"obsi", "enter")
        assert [a.name for a in editor.app_choices] == ["Obsidian"]
        assert editor.query_one("#app-0").value is True
        summary = str(editor.query_one("#summary").render())
        assert "apps Obsidian" in summary
        await pilot.press("ctrl+s")
        assert not isinstance(app.screen, FocusEditor)
        saved = stored(isolated_focus)
        assert saved["apps"] == [{"id": "obsidian_obsidian", "name": "Obsidian"}]
        text = str(app.query_one(Content).render())
        assert "Google Docs · apps Obsidian" in text


@linux_only
async def test_a_focus_can_allow_only_apps(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(app_module, "choosable_apps", lambda: (APPS, []))
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "j", "j")
        editor = app.screen
        await pilot.press("enter", *"discord", "enter")
        summary = str(editor.query_one("#summary").render())
        assert "every page in Chrome goes to the focus page" in summary
        await pilot.press("ctrl+s")
        saved = stored(isolated_focus)
        assert saved["domains"] == [] and saved["apps"][0]["name"] == "Discord"
        assert "no sites · apps Discord" in str(app.query_one(Content).render())


@linux_only
async def test_an_unknown_app_says_so_and_adds_nothing(isolated_focus, monkeypatch):
    monkeypatch.setattr(app_module, "choosable_apps", lambda: (APPS, []))
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "j", "j", "enter", *"steam", "enter")
        editor = app.screen
        assert editor.app_choices == []
        assert "no app called steam." in str(editor.query_one("#editor-error").render())


@linux_only
async def test_without_apps_to_pick_there_is_no_apps_row(isolated_focus):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        await pilot.press("s")
        assert not app.screen.query("#new-app")


@linux_only
async def test_the_editor_lists_what_is_blocked_now(isolated_focus, monkeypatch):
    monkeypatch.setattr(
        app_module.HostsBlocker,
        "all_blocked_urls",
        property(lambda self: {"youtube.com", "www.youtube.com", "netflix.com"}),
    )
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_focus(pilot)
        await pilot.press("s")
        labels = [str(w.render()) for w in app.screen.query(".label")]
        assert "blocked now, and they stay blocked: Netflix, YouTube" in labels


def test_dashboard_names_allowed_apps(isolated_focus, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    focus_mode.save_start(
        focus_mode.Focus(NOW + 3_600_000, ("Udemy",), ("udemy.com",), (OBSIDIAN,)),
        isolated_focus,
        NOW,
    )
    assert "allows Udemy · apps Obsidian" in dashboard_text(hosts)


def test_two_apps_with_one_name_ask_which_and_their_ids_pick_one():
    snap = AllowedApp("obsidian_obsidian", "Obsidian")
    flatpak = AllowedApp("md.obsidian.Obsidian", "Obsidian")
    apps = [snap, flatpak, AllowedApp("discord_discord", "Discord")]
    assert match_app("obsidian", apps) == (
        None,
        "which one? Obsidian (obsidian_obsidian), Obsidian (md.obsidian.Obsidian)",
    )
    assert match_app("md.obsidian.Obsidian", apps) == (flatpak, "")


@linux_only
async def test_brackets_in_names_and_typing_show_as_they_are(
    isolated_focus, monkeypatch
):
    beta = AllowedApp("tool-beta", "Tool [Beta]")
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(app_module, "choosable_apps", lambda: ([beta], []))
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "j", "j", "enter", *"a [/] b", "enter")
        editor = app.screen
        error = str(editor.query_one("#editor-error").render())
        assert "no app called a [/] b." in error
        editor.query_one("#new-app").value = ""
        await pilot.press("enter", *"tool", "enter")
        assert "Tool [Beta]" in str(editor.query_one("#app-0").render())
        assert "apps Tool [Beta]" in str(editor.query_one("#summary").render())
        await pilot.press("ctrl+s")
        # render() gives markup; what's on screen is it parsed.
        shown = TextualContent.from_markup(app.query_one(Content).render()).plain
        assert "apps Tool [Beta]" in shown


@linux_only
async def test_apps_that_start_at_login_come_ticked_and_can_be_unticked(
    isolated_focus, monkeypatch
):
    tablet = AllowedApp("xppentablet", "xppentablet")
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(
        app_module, "choosable_apps", lambda: ([*APPS, tablet], [tablet])
    )
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s")
        editor = app.screen
        box = editor.query_one("#app-0")
        assert box.value is True and "xppentablet" in str(box.render())
        await pilot.press("x")  # Google Docs
        await pilot.press("ctrl+s")
        assert stored(isolated_focus)["apps"] == [
            {"id": "xppentablet", "name": "xppentablet"}
        ]


@linux_only
async def test_an_unticked_login_app_isnt_allowed(isolated_focus, monkeypatch):
    tablet = AllowedApp("xppentablet", "xppentablet")
    monkeypatch.setattr(app_module, "focus_now", lambda: NOW)
    monkeypatch.setattr(app_module, "choosable_apps", lambda: ([tablet], [tablet]))
    app = BlockerApp()
    async with app.run_test(size=(110, 60)) as pilot:
        await open_focus(pilot)
        await pilot.press("s", "x")  # Google Docs
        editor = app.screen
        editor.query_one("#app-0").value = False
        await pilot.pause()
        await pilot.press("ctrl+s")
        assert stored(isolated_focus)["apps"] == []
