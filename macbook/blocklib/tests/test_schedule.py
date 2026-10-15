"""blocklib.schedule: the same rules androidlib's Kotlin tests check, against
the same shared fixture."""

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from blocklib import schedule as sch
from blocklib.schedule import (
    Block,
    EveryPlan,
    ForPlan,
    LockedError,
    Message,
    Redirect,
    Schedule,
    ScheduleError,
)

FIXTURE = Path(__file__).parents[3] / "shared" / "schedules.json"
LONDON = ZoneInfo("Europe/London")


def at(text: str) -> datetime:
    """2026-10-12 is a Monday."""
    return datetime.fromisoformat(text).replace(tzinfo=LONDON)


def ms(text: str) -> int:
    return int(at(text).timestamp() * 1000)


def every(id, days, start, end, **kw) -> Schedule:
    return Schedule(
        id=id,
        name=id.title(),
        sites=("YouTube",),
        domains=("youtube.com",),
        apps=(),
        plan=EveryPlan(frozenset(days), start, end),
        **kw,
    )


WORK = every("work", {1, 2, 3, 4, 5}, 540, 1020)


# The model


def test_weekday_range_is_active_from_start_up_to_end():
    assert not WORK.is_active(at("2026-10-12T08:59"))
    assert WORK.is_active(at("2026-10-12T09:00"))
    assert WORK.is_active(at("2026-10-12T16:59"))
    assert not WORK.is_active(at("2026-10-12T17:00"))
    assert not WORK.is_active(at("2026-10-17T10:00"))  # Saturday


def test_overnight_range_belongs_to_the_day_it_starts_on():
    night = every("night", {5}, 22 * 60, 7 * 60)  # Friday night
    assert night.is_active(at("2026-10-16T23:00"))
    assert night.is_active(at("2026-10-17T06:59"))  # Saturday morning
    assert not night.is_active(at("2026-10-17T07:00"))
    assert not night.is_active(at("2026-10-18T03:00"))  # not Sunday
    assert not night.is_active(at("2026-10-16T03:00"))  # Thursday's night


def test_start_equal_to_end_means_the_whole_day():
    sat = every("sat", {6}, 0, 0)
    assert sat.is_active(at("2026-10-17T00:00"))
    assert sat.is_active(at("2026-10-17T23:59"))
    assert not sat.is_active(at("2026-10-18T00:00"))


def test_disabled_and_paused_schedules():
    assert not replace(WORK, enabled=False).is_active(at("2026-10-12T10:00"))
    paused = replace(WORK, paused_until=ms("2026-10-12T17:00"))
    assert not paused.is_active(at("2026-10-12T10:00"))
    assert paused.is_active(at("2026-10-13T10:00"))


def test_for_plan_runs_from_starts_at_until_ends_at():
    focus = replace(WORK, plan=ForPlan(ms("2026-10-12T15:00"), ms("2026-10-12T16:00")))
    assert not focus.is_active(at("2026-10-12T14:59"))
    assert focus.is_active(at("2026-10-12T15:00"))
    assert not focus.is_active(at("2026-10-12T16:00"))
    assert focus.active_until(at("2026-10-12T15:30")) == ms("2026-10-12T16:00")


def test_invalid_plans_are_rejected():
    with pytest.raises(ScheduleError):
        EveryPlan(frozenset(), 0, 60)
    with pytest.raises(ScheduleError):
        EveryPlan(frozenset({8}), 0, 60)
    with pytest.raises(ScheduleError):
        EveryPlan(frozenset({1}), 0, 1440)
    with pytest.raises(ScheduleError):
        ForPlan(10, 10)


def test_spring_forward_and_fall_back():
    # 2027-03-28 01:00 GMT the clocks jump to 02:00 BST; 2026-10-25 02:00 BST
    # they go back to 01:00 GMT.
    early = every("early", {7}, 90, 300)  # 01:30–05:00
    jump = at("2027-03-28T02:00")
    assert early.next_start(at("2027-03-27T12:00")) == jump
    assert early.is_active(jump)
    late = every("late", {7}, 60, 120)  # 01:00–02:00, which happens twice
    second = datetime(2026, 10, 25, 1, 30, fold=1, tzinfo=LONDON)
    assert late.is_active(second)
    assert late.active_until(second) > int(second.timestamp() * 1000)


def test_occurrence_ends():
    assert WORK.active_until(at("2026-10-12T10:00")) == ms("2026-10-12T17:00")
    night = every("night", {1}, 22 * 60, 7 * 60)
    assert night.active_until(at("2026-10-12T23:00")) == ms("2026-10-13T07:00")
    assert night.active_until(at("2026-10-13T03:00")) == ms("2026-10-13T07:00")
    sat = every("sat", {6, 7}, 0, 0)
    assert sat.active_until(at("2026-10-17T10:00")) == ms("2026-10-18T00:00")


def test_next_start():
    assert WORK.next_start(at("2026-10-12T08:00")) == at("2026-10-12T09:00")
    assert WORK.next_start(at("2026-10-16T12:00")) == at("2026-10-19T09:00")
    assert replace(WORK, enabled=False).next_start(at("2026-10-12T08:00")) is None
    ended = WORK.paused_for_current_occurrence(at("2026-10-12T10:00"))
    assert ended.next_start(at("2026-10-12T10:00")) == at("2026-10-13T09:00")
    # Ended early, then lengthened to 18:00: back when the pause ends.
    longer = replace(ended, plan=EveryPlan(WORK.plan.days, 540, 1080))
    assert longer.next_start(at("2026-10-12T10:00")) == at("2026-10-12T17:00")


def test_next_up_skips_running_schedules():
    evening = every("evening", {1}, 18 * 60, 23 * 60)
    s, t = sch.next_up([WORK, evening], at("2026-10-12T10:00"))
    assert (s.id, t) == ("evening", at("2026-10-12T18:00"))
    assert sch.next_up([], at("2026-10-12T10:00")) is None


def test_active_domains_is_the_union():
    other = replace(every("other", {1}, 0, 0), domains=("netflix.com",))
    assert sch.active_domains([WORK, other], at("2026-10-12T10:00")) == {
        "youtube.com",
        "netflix.com",
    }
    assert sch.active_domains([WORK], at("2026-10-12T18:00")) == set()


# JSON, against the fixture Kotlin and Dart also read


def test_fixture_parses_into_every_plan_and_action_type():
    by_id = {s.id: s for s in sch.list_from_json(FIXTURE.read_text())}
    assert list(by_id) == ["work", "bedtime", "focus", "weekend"]
    assert by_id["work"].paused_until == 1760000000000
    assert by_id["work"].plan == EveryPlan(frozenset({1, 2, 3, 4, 5}), 540, 1020)
    assert by_id["work"].domains == ("youtube.com", "googlevideo.com")
    assert by_id["bedtime"].plan.overnight
    assert by_id["bedtime"].action == Message("go to bed")
    assert by_id["focus"].plan == ForPlan(1760000000000, 1760003600000)
    assert by_id["focus"].action == Redirect("com.amazon.kindle")
    assert by_id["weekend"].plan.all_day
    assert not by_id["weekend"].enabled
    assert by_id["weekend"].action == Block()


def test_writes_exactly_the_fixture_json():
    raw = json.loads(FIXTURE.read_text())
    schedules = sch.list_from_json(FIXTURE.read_text())
    assert json.loads(sch.list_to_json(schedules)) == raw


@pytest.mark.parametrize(
    "change",
    [
        {"plan": {"type": "weekly"}},
        {"action": {"type": "explode"}},
        {"plan": {"type": "every", "days": [1], "start": "540", "end": 1020}},
        {"plan": {"type": "every", "days": [True], "start": 540, "end": 1020}},
        {"enabled": "yes"},
        {"domains": "youtube.com"},
        {"pausedUntil": None},
        {"id": None},
    ],
)
def test_malformed_values_are_rejected(change):
    item = {**json.loads(FIXTURE.read_text())[0], **change}
    with pytest.raises(ScheduleError):
        Schedule.from_json(item)


def test_lists_strict_and_lenient():
    with pytest.raises(ScheduleError):
        sch.list_from_json("{")
    with pytest.raises(ScheduleError):
        sch.list_from_json(json.dumps([WORK.to_json(), WORK.to_json()]))
    # The root helper skips the bad entry and keeps the rest.
    text = json.dumps([{"id": "broken"}, WORK.to_json()])
    assert [s.id for s in sch.list_from_json_skipping_bad(text)] == ["work"]
    assert sch.list_from_json_skipping_bad("not json") == []
    assert sch.list_from_json_skipping_bad(None) == []


# Rules (decision D1)

NOW = at("2026-10-12T10:00")  # WORK is running


def test_anything_can_change_while_nothing_is_running():
    later = at("2026-10-12T20:00")
    assert sch.replace_all([WORK], [], password_ok=False, now=later) == []


@pytest.mark.parametrize(
    "weaken",
    [
        lambda s: [],
        lambda s: [replace(s, enabled=False)],
        lambda s: [replace(s, plan=EveryPlan(frozenset({1}), 540, 600))],
        lambda s: [replace(s, domains=())],
        lambda s: [replace(s, action=Message("ok"))],
    ],
)
def test_without_the_password_a_running_schedule_cannot_be_weakened(weaken):
    with pytest.raises(LockedError):
        sch.replace_all([WORK], weaken(WORK), password_ok=False, now=NOW)
    assert sch.replace_all([WORK], weaken(WORK), password_ok=True, now=NOW) == weaken(
        WORK
    )


def test_strengthening_renaming_and_plain_blocking_need_no_password():
    messaged = replace(WORK, action=Message("get back to work"))
    stronger = replace(WORK, name="Work hours", domains=("youtube.com", "netflix.com"))
    assert sch.replace_all([WORK], [stronger], password_ok=False, now=NOW) == [stronger]
    assert sch.replace_all([messaged], [WORK], password_ok=False, now=NOW) == [WORK]


def test_pauses_cannot_be_set_or_cleared_by_saving():
    paused = replace(WORK, paused_until=ms("2026-10-12T17:00"))
    assert sch.replace_all([paused], [WORK], password_ok=False, now=NOW) == [paused]
    later = at("2026-10-12T20:00")
    saved = sch.replace_all([WORK], [paused], password_ok=False, now=later)
    assert saved == [WORK]


def test_duplicate_ids_are_rejected():
    with pytest.raises(ScheduleError):
        sch.replace_all([], [WORK, WORK], password_ok=True, now=NOW)


def test_pausing_needs_the_password_and_a_running_schedule():
    evening = every("evening", {1}, 18 * 60, 23 * 60)
    assert sch.pause([WORK], "work", False, NOW) == (sch.WRONG_PASSWORD, None)
    assert sch.pause([evening], "evening", True, NOW) == (sch.NOT_RUNNING, None)
    assert sch.pause([WORK], "missing", True, NOW) == (sch.NOT_RUNNING, None)
    result, stored = sch.pause([evening, WORK], "work", True, NOW)
    assert result == sch.PAUSED
    assert stored == [evening, replace(WORK, paused_until=ms("2026-10-12T17:00"))]
    # Already paused, so not running: pausing again does nothing.
    assert sch.pause(stored, "work", True, NOW) == (sch.NOT_RUNNING, None)


def test_local_now_has_a_zone():
    assert sch.local_now().tzinfo is not None
