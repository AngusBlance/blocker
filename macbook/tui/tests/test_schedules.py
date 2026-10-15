"""The schedules section: list, on/off, end early, add, delete."""

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from blocker_tui import schedules as sched_ui
from blocker_tui.app import (
    BlockerApp,
    ConfirmModal,
    Content,
    Input,
    PresetModal,
    UnlockModal,
    dashboard_text,
    sites_text,
)
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
    text = sched_ui.schedules_text([WORK, EVENING, GYM], 0, NOW, True)
    assert "> [on ] Work" in text
    assert "running · until 17:00" in text
    assert "[off] Gym" in text
    assert "helper isn't installed" not in text
    paused = sched_ui.schedules_text(
        [replace(WORK, paused_until=ms(datetime(2026, 10, 15, 17, tzinfo=LONDON)))],
        0,
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


def test_new_schedules_block_every_known_site():
    s = sched_ui.new_schedule(sched_ui.PRESETS[2])
    assert s.name == "bedtime"
    assert s.plan == EveryPlan(frozenset({1, 2, 3, 4, 7}), 1320, 420)
    assert "TikTok" in s.sites and "www.youtube.com" in s.domains


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
        await pilot.press("j", "enter")  # Evening
        assert not isinstance(app.screen, UnlockModal)
        assert saved(stored)["evening"].enabled is False
        await pilot.press("enter")
        assert saved(stored)["evening"].enabled is True


async def test_turning_off_a_running_schedule_needs_the_password(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("enter")  # Work, running
        assert isinstance(app.screen, UnlockModal)
        assert app.screen.title == "WORK IS RUNNING"
        await pilot.press("escape")
        assert saved(stored)["work"].enabled is True

        await pilot.press("enter")
        await type_password(app, pilot)
        assert saved(stored)["work"].enabled is False


async def test_a_wrong_password_changes_nothing(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("enter")
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


async def test_adding_from_a_preset(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("a")
        assert isinstance(app.screen, PresetModal)
        await pilot.press("j", "j", "enter")
        names = [s.name for s in schedule_store.load(stored)]
        assert names == ["Work", "Evening", "Gym", "bedtime"]
        assert "bedtime" in screen_text(app)


async def test_cancelling_the_preset_adds_nothing(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("a", "escape")
        assert len(schedule_store.load(stored)) == 3


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
        assert isinstance(app.screen, UnlockModal)
        await type_password(app, pilot)
        assert list(saved(stored)) == ["evening", "gym"]


async def test_schedule_keys_do_nothing_elsewhere(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("a", "d", "e")
        assert not isinstance(app.screen, (PresetModal, ConfirmModal, UnlockModal))
        assert len(schedule_store.load(stored)) == 3


async def test_cursor_stays_on_the_list(stored):
    app = BlockerApp()
    async with app.run_test() as pilot:
        await open_schedules(pilot)
        await pilot.press("j", "j", "j", "j")
        assert app.query_one(Content).schedule_index == 2
        await pilot.press("k", "k", "k")
        assert app.query_one(Content).schedule_index == 0
