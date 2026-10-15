import json
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from blocklib import schedule as sch
from blocklib import schedule_store as store
from blocklib.schedule import EveryPlan, LockedError, Schedule

NOW = datetime(2026, 10, 12, 10, tzinfo=ZoneInfo("Europe/London"))  # Monday
WORK = Schedule(
    id="work",
    name="Work",
    sites=("YouTube",),
    domains=("youtube.com",),
    apps=(),
    plan=EveryPlan(frozenset({1, 2, 3, 4, 5}), 540, 1020),
)
EVENING = replace(WORK, id="evening", plan=EveryPlan(frozenset({1}), 1080, 1380))


def test_missing_file_is_no_schedules(tmp_path):
    assert store.load(tmp_path / "none.json") == []


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "dir" / "schedules.json"
    store.save([WORK, EVENING], password_ok=False, now=NOW, path=path)
    assert store.load(path) == [WORK, EVENING]
    assert path.stat().st_mode & 0o777 == 0o644
    assert not list(path.parent.glob(".schedules-*"))


def test_save_keeps_the_lock_rules(tmp_path):
    path = tmp_path / "schedules.json"
    store.save([WORK, EVENING], password_ok=False, now=NOW, path=path)
    with pytest.raises(LockedError):
        store.save([EVENING], password_ok=False, now=NOW, path=path)
    assert store.load(path) == [WORK, EVENING]  # unchanged
    store.save([EVENING], password_ok=True, now=NOW, path=path)
    assert store.load(path) == [EVENING]


def test_end_early_pauses_and_keeps_other_entries(tmp_path):
    path = tmp_path / "schedules.json"
    odd = {"id": "future", "plan": {"type": "monthly"}}
    path.write_text(json.dumps([odd, WORK.to_json()]))
    assert store.end_early("work", False, NOW, path) == sch.WRONG_PASSWORD
    assert store.end_early("work", True, NOW, path) == sch.PAUSED
    items = json.loads(path.read_text())
    assert items[0] == odd
    assert store.load(path)[0].paused_until is not None
    assert store.end_early("work", True, NOW, path) == sch.NOT_RUNNING
