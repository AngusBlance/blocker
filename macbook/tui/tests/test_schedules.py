"""The schedules section: list, on/off, end early, add, delete."""

import json
import os
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from textual.widgets import Checkbox

from blocker_tui import schedules as sched_ui
from blocker_tui.app import (
    BlockerApp,
    ConfirmModal,
    Content,
    Input,
    UnlockModal,
    dashboard_text,
    sites_text,
)
from blocker_tui.schedule_editor import ScheduleEditor, parse_time
from blocklib import schedule_store
from blocklib.schedule import EveryPlan, ForPlan, Schedule, list_to_json

LONDON = ZoneInfo("Europe/London")
NOW = datetime(2026, 10, 15, 13, 30, tzinfo=LONDON)  # a Thursday


def every(id, days, start, end, enabled=True):
    return Schedule(
        id=id,
        name=id.title(),
        sites=("YouTube",),
        domains=("youtube.com",),
        apps=(),
        plan=EveryPlan(frozenset(days), start, end),
        enabled=enabled,
    )


WORK = every("work", {1, 2, 3, 4, 5}, 540, 1020)  # running now
EVENING = every("evening", range(1, 8), 1080, 1380)  # later today
GYM = every("gym", {6}, 480, 540, enabled=False)


@pytest.fixture
def stored(isolated_schedules, monkeypatch):
    monkeypatch.setattr(sched_ui, "now", lambda: NOW)
    schedule_store.write_text(list_to_json([WORK, EVENING, GYM]), isolated_schedules)
    return isolated_schedules


def ms(t: datetime) -> int:
    return int(t.timestamp() * 1000)


def saved(path):
    return {s.id: s for s in schedule_store.load(path)}


def screen_text(app) -> str:
    return str(app.query_one(Content).render())


async def open_schedules(pilot):
    await pilot.press("j", "j", "l")  # dashboard → sites → schedule, focus it


async def type_password(app, pilot):
    app.screen.query_one(Input).value = "test-password"
    await pilot.press("enter")


# Text


def test_formatting_matches_android():
    assert sched_ui.format_plan(WORK.plan) == "weekdays · 09:00–17:00"
    assert sched_ui.format_plan(EveryPlan(frozenset({6, 7}), 0, 0)) == (
        "weekends · all day"
    )
    assert sched_ui.format_plan(EveryPlan(frozenset({1, 3}), 1320, 420)) == (
        "M W · 22:00–07:00 next day"
    )
    assert sched_ui.format_until(datetime(2026, 10, 16, tzinfo=LONDON), NOW) == (
        "midnight"
    )
    assert sched_ui.format_until(datetime(2026, 10, 16, 7, tzinfo=LONDON), NOW) == (
        "tomorrow 07:00"
    )
    assert sched_ui.format_until(datetime(2026, 10, 19, 9, tzinfo=LONDON), NOW) == (
        "Mon 09:00"
    )
    assert sched_ui.format_until(datetime(2026, 10, 22, 9, tzinfo=LONDON), NOW) == (
        "next Thu 09:00"
    )


def test_list_shows_each_schedule_with_its_state(stored):
    text = sched_ui.schedules_text([WORK, EVENING, GYM], "work", NOW, True)
    assert "> [on ] Work" in text
    assert "running · until 17:00" in text
    assert "[off] Gym" in text
    assert "helper isn't installed" not in text
    paused = sched_ui.schedules_text(
        [replace(WORK, paused_until=ms(datetime(2026, 10, 15, 17, tzinfo=LONDON)))],
        "work",
        NOW,
        False,
    )
    assert "ended early · back next time" in paused
    assert "block install" in paused


def test_finished_one_offs_are_hidden():
    start = ms(datetime(2026, 10, 15, 9, tzinfo=LONDON))
    done = Schedule("done", "Block now", (), ("x.com",), (), ForPlan(start, start + 1))
    assert sched_ui.shown([done, WORK], NOW) == [WORK]


def test_dashboard_shows_whats_running_and_next(stored, tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    text = dashboard_text(hosts)
    assert "Work until 17:00" in text
    assert "next            Evening from 18:00" in text


def test_sites_view_marks_sites_a_schedule_blocks(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(
        "# BLOCKER-SCHEDULE-BEGIN\n127.0.0.1 youtube.com\n# BLOCKER-SCHEDULE-END\n"
    )
    text = sites_text(0, hosts)
    assert "YouTube · blocked by a schedule" in text
    assert "Netflix · blocked" not in text


# Pilot


async def test_section_lists_schedules(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        text = screen_text(app)
        assert "SCHEDULES" in text
        assert "Work" in text and "Evening" in text and "Gym" in text


async def test_turning_off_a_schedule_that_isnt_running_needs_no_password(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "t")  # Evening
        assert not isinstance(app.screen, UnlockModal)
        assert saved(stored)["evening"].enabled is False
        await pilot.press("t")
        assert saved(stored)["evening"].enabled is True


async def test_turning_off_a_running_schedule_needs_the_password(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("t")  # Work, running
        assert isinstance(app.screen, UnlockModal)
        assert app.screen.title == "WORK IS RUNNING"
        await pilot.press("escape")
        assert saved(stored)["work"].enabled is True

        await pilot.press("t")
        await type_password(app, pilot)
        assert saved(stored)["work"].enabled is False


async def test_a_wrong_password_changes_nothing(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("t")
        app.screen.query_one(Input).value = "nope"
        await pilot.press("enter")
        assert saved(stored)["work"].enabled is True


async def test_ending_early_pauses_only_this_occurrence(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("e")
        assert isinstance(app.screen, UnlockModal)
        await type_password(app, pilot)
        work = saved(stored)["work"]
        assert work.enabled
        assert work.paused_until == ms(datetime(2026, 10, 15, 17, tzinfo=LONDON))
        assert "ended early" in screen_text(app)


async def test_ending_one_that_isnt_running_just_says_so(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "e")
        assert not isinstance(app.screen, UnlockModal)


async def fill_editor(
    app, pilot, name=None, days=None, start=None, end=None, all_day=None, sites=None
):
    """Sets the editor's fields the way typing and ticking would."""
    editor = app.screen
    assert isinstance(editor, ScheduleEditor)
    if name is not None:
        editor.query_one("#schedule-name", Input).value = name
    if days is not None:
        for d in range(1, 8):
            editor.query_one(f"#day-{d}", Checkbox).value = d in days
    if start is not None:
        editor.query_one("#time-from", Input).value = start
    if end is not None:
        editor.query_one("#time-to", Input).value = end
    if all_day is not None:
        editor.query_one("#all-day", Checkbox).value = all_day
    if sites is not None:
        for i, site in enumerate(editor.site_names):
            editor.query_one(f"#site-{i}", Checkbox).value = site in sites
    await pilot.pause()


async def test_adding_a_schedule_with_its_own_days_times_and_sites(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("a")
        await fill_editor(
            app,
            pilot,
            name="Homework",
            days={1, 3},
            start="16:30",
            end="18:00",
            sites=["YouTube", "TikTok"],
        )
        assert str(app.screen.query_one("#summary").render()) == "M W · 16:30–18:00"
        await pilot.click("#save")
        added = schedule_store.load(stored)[-1]
        assert added.name == "Homework"
        assert added.plan == EveryPlan(frozenset({1, 3}), 990, 1080)
        assert added.sites == ("YouTube", "TikTok")
        assert "youtube.com" in added.domains and "tiktok.com" in added.domains
        assert "netflix.com" not in added.domains
        assert app.query_one(Content).schedule_id == added.id
        assert "Homework" in screen_text(app)


async def test_the_editor_explains_what_is_missing_and_wont_save(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("a")
        editor = app.screen

        def problem():
            return str(editor.query_one("#editor-error").render())

        await fill_editor(app, pilot, name="x", sites=[])
        assert problem() == "pick at least one site."
        await fill_editor(app, pilot, sites=["Netflix"], days=set())
        assert problem() == "pick at least one day."
        await fill_editor(app, pilot, days={1}, start="9:00", end="09:00")
        assert problem() == "from and to can't be the same time."
        await fill_editor(app, pilot, end="25:00")
        assert problem() == "to should be a time like 17:00."
        await pilot.press("ctrl+s")
        assert isinstance(app.screen, ScheduleEditor)  # still open
        await fill_editor(app, pilot, all_day=True)  # times don't matter now
        assert problem() == ""
        await pilot.press("ctrl+s")
        added = schedule_store.load(stored)[-1]
        assert added.plan == EveryPlan(frozenset({1}), 0, 0)


async def test_presets_and_day_shortcuts_fill_the_form(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("a")
        await pilot.click("#preset-2")  # bedtime
        editor = app.screen
        assert editor.query_one("#schedule-name", Input).value == "bedtime"
        assert editor._days() == {1, 2, 3, 4, 7}
        assert editor.query_one("#time-from", Input).value == "22:00"
        assert editor.query_one("#time-to", Input).value == "07:00"
        await pilot.click("#days-weekends")
        assert editor._days() == {6, 7}
        await pilot.click("#days-every-day")
        assert editor._days() == set(range(1, 8))
        await fill_editor(app, pilot, sites=["Facebook"])
        await pilot.press("ctrl+s")
        added = schedule_store.load(stored)[-1]
        assert added.plan == EveryPlan(frozenset(range(1, 8)), 1320, 420)
        assert added.sites == ("Facebook",)


async def test_editing_keeps_the_schedule_and_changes_its_fields(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "enter")  # Evening
        editor = app.screen
        assert isinstance(editor, ScheduleEditor)
        assert editor.query_one("#schedule-name", Input).value == "Evening"
        assert editor.query_one("#time-from", Input).value == "18:00"
        await fill_editor(app, pilot, end="22:30", sites=["YouTube", "Netflix"])
        await pilot.press("ctrl+s")
        evening = saved(stored)["evening"]
        assert evening.plan.end == 1350
        assert evening.sites == ("Netflix", "YouTube")  # in display order
        assert list(saved(stored)) == ["work", "evening", "gym"]


async def test_shrinking_a_running_schedule_in_the_editor_needs_the_password(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("enter")  # Work, running
        await fill_editor(app, pilot, days={1, 2})  # drops today, Thursday
        await pilot.press("ctrl+s")
        assert isinstance(app.screen, UnlockModal)
        assert app.screen.title == "WORK IS RUNNING"
        await pilot.press("escape")
        assert saved(stored)["work"].plan.days == frozenset({1, 2, 3, 4, 5})


async def test_renaming_a_running_schedule_needs_no_password(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("enter")
        await fill_editor(app, pilot, name="Work hours")
        await pilot.press("ctrl+s")
        assert not isinstance(app.screen, UnlockModal)
        assert saved(stored)["work"].name == "Work hours"


async def test_cancelling_the_editor_changes_nothing(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("a", "escape")
        assert len(schedule_store.load(stored)) == 3
        await pilot.press("enter")
        await fill_editor(app, pilot, name="changed")
        await pilot.click("#cancel")
        assert saved(stored)["work"].name == "Work"


@pytest.mark.parametrize(
    "text, minutes",
    [
        ("9:00", 540),
        ("09:00", 540),
        ("0900", 540),
        ("23:59", 1439),
        ("24:00", None),
        ("9", None),
        ("ab", None),
    ],
)
def test_time_parsing(text, minutes):
    assert parse_time(text) == minutes


async def test_deleting_one_that_isnt_running_asks_to_confirm(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "d")
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("n")
        assert "evening" in saved(stored)
        await pilot.press("d", "y")
        assert list(saved(stored)) == ["work", "gym"]


async def test_deleting_a_running_schedule_needs_the_password(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("d")
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("y")
        assert isinstance(app.screen, UnlockModal)
        assert app.screen.title == "WORK IS RUNNING"
        await type_password(app, pilot)
        assert list(saved(stored)) == ["evening", "gym"]


async def test_schedule_keys_do_nothing_elsewhere(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("a", "d", "e", "t")
        assert not isinstance(app.screen, (ScheduleEditor, ConfirmModal, UnlockModal))
        assert len(schedule_store.load(stored)) == 3


async def test_cursor_stays_on_the_list(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "j", "j", "j")
        assert app.query_one(Content).schedule_id == "gym"
        await pilot.press("k", "k", "k")
        assert app.query_one(Content).schedule_id == "work"


# Review follow-ups


def one_off(id, start, end):
    return Schedule(
        id, "Block now", ("Netflix",), ("netflix.com",), (), ForPlan(ms(start), ms(end))
    )


BLOCK = one_off(
    "block",
    datetime(2026, 10, 15, 13, tzinfo=LONDON),
    datetime(2026, 10, 15, 14, tzinfo=LONDON),
)
AFTER_BLOCK = datetime(2026, 10, 15, 14, 1, tzinfo=LONDON)


def with_clock(monkeypatch, path, schedules):
    clock = [NOW]
    monkeypatch.setattr(sched_ui, "now", lambda: clock[0])
    schedule_store.write_text(list_to_json(schedules), path)
    return clock


async def test_keys_act_on_the_highlighted_schedule_after_rows_drop_off(
    isolated_schedules, monkeypatch
):
    clock = with_clock(monkeypatch, isolated_schedules, [BLOCK, EVENING, GYM])
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j")  # Evening
        clock[0] = AFTER_BLOCK  # the one-off above it finishes
        await pilot.press("t")
        assert saved(isolated_schedules)["evening"].enabled is False
        assert saved(isolated_schedules)["gym"].enabled is False  # untouched


async def test_the_cursor_moves_on_when_its_row_drops_off(
    isolated_schedules, monkeypatch
):
    clock = with_clock(monkeypatch, isolated_schedules, [EVENING, BLOCK])
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j")  # the one-off
        clock[0] = AFTER_BLOCK
        await pilot.press("e")  # it's gone: says so, asks nothing
        assert not isinstance(app.screen, UnlockModal)
        assert app.query_one(Content).schedule_id == "evening"
        app._tick()
        assert "> [on ] Evening" in screen_text(app)


async def test_a_one_off_has_no_switch_and_ends_early_with_its_own_wording(
    isolated_schedules, monkeypatch
):
    with_clock(monkeypatch, isolated_schedules, [BLOCK])
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        assert "[on ]" not in screen_text(app)
        await pilot.press("t")
        assert saved(isolated_schedules)["block"].enabled is True
        await pilot.press("enter")  # not editable either
        assert not isinstance(app.screen, ScheduleEditor)
        await pilot.press("e")
        assert app.screen.reason == "this ends the block now."
        await type_password(app, pilot)
        assert sched_ui.shown(schedule_store.load(isolated_schedules), NOW) == []


async def test_a_schedule_that_ends_while_typing_the_password_is_left_alone(
    stored, monkeypatch
):
    clock = [NOW]
    monkeypatch.setattr(sched_ui, "now", lambda: clock[0])
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("e")
        assert "comes back as scheduled" in app.screen.reason
        clock[0] = datetime(2026, 10, 15, 17, 1, tzinfo=LONDON)
        await type_password(app, pilot)
        assert saved(stored)["work"].paused_until is None


@pytest.mark.parametrize("content", [b"\xff\xfe not utf-8", b"{not json", b'{"a": 1}'])
async def test_a_damaged_file_is_shown_and_never_saved_over(
    isolated_schedules, monkeypatch, content
):
    monkeypatch.setattr(sched_ui, "now", lambda: NOW)
    isolated_schedules.write_bytes(content)
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        assert "nothing is saved over it" in screen_text(app)
        await pilot.press("a")
        await fill_editor(app, pilot, name="x", sites=["YouTube"])
        await pilot.press("ctrl+s")
        assert isolated_schedules.read_bytes() == content
        await pilot.press("h", "k", "k")  # the dashboard still works
        assert "none running" in screen_text(app)


async def test_entries_it_cant_read_survive_a_change(isolated_schedules, monkeypatch):
    monkeypatch.setattr(sched_ui, "now", lambda: NOW)
    odd = {"id": "future", "plan": {"type": "monthly"}}
    isolated_schedules.write_text(json.dumps([EVENING.to_json(), odd]))
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("t")
        assert json.loads(isolated_schedules.read_text())[1] == odd
        assert saved(isolated_schedules)["evening"].enabled is False


async def test_delete_uses_the_list_as_it_is_when_confirmed(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "d")  # Evening
        # Meanwhile another window adds one.
        others = [*schedule_store.load(stored), replace(GYM, id="new")]
        schedule_store.save(others, True, NOW, stored)
        await pilot.press("y")
        assert list(saved(stored)) == ["work", "gym", "new"]


async def test_deleting_the_last_row_moves_the_cursor(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "j", "d", "y")  # Gym
        assert app.query_one(Content).schedule_id == "work"


def test_dashboard_with_nothing_running_or_next(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_ui, "now", lambda: NOW)
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    text = dashboard_text(hosts)
    assert "none running" in text and "next" not in text


async def test_the_tick_tells_the_extension_when_hosts_changes(
    stored, monkeypatch, tmp_path
):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n")
    monkeypatch.setattr("blocker_tui.app.HOSTS_FILE", hosts)

    class FakeServer:
        def __init__(self):
            self.notified = 0

        def notify_change(self):
            self.notified += 1

        def stop(self):
            pass

    app = BlockerApp()
    async with app.run_test():
        server = FakeServer()
        app._sync_server = server
        app._tick()
        assert server.notified == 0
        hosts.write_text("127.0.0.1 localhost\n127.0.0.1 x.com\n")
        os.utime(hosts, ns=(0, 1))
        app._tick()
        assert server.notified == 1


async def test_tab_and_enter_move_from_the_name_to_the_days(stored):
    app = BlockerApp()
    async with app.run_test(size=(110, 50)) as pilot:
        await open_schedules(pilot)
        await pilot.press("enter")  # edit Work; the name box has focus
        editor = app.screen
        assert editor.focused.id == "schedule-name"
        await pilot.press("enter")  # moves on, doesn't save
        assert isinstance(app.screen, ScheduleEditor)
        assert editor.focused.id == "day-1"
        await pilot.press("tab", "tab", "tab", "tab", "tab")
        assert editor.focused.id == "day-6"
        await pilot.press("space")  # tick Saturday
        assert 6 in editor._days()
        await pilot.press("shift+tab")
        assert editor.focused.id == "day-5"
        await pilot.press("ctrl+s")  # Work is running: a new plan needs the password
        assert isinstance(app.screen, UnlockModal)
        await type_password(app, pilot)
        assert saved(stored)["work"].plan.days == frozenset({1, 2, 3, 4, 5, 6})
