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


def test_save_keeps_entries_it_cant_read(tmp_path):
    path = tmp_path / "schedules.json"
    odd = {"id": "future", "plan": {"type": "monthly"}}
    path.write_text(json.dumps([WORK.to_json(), odd]))
    store.save([WORK, EVENING], password_ok=False, now=NOW, path=path)
    assert json.loads(path.read_text())[-1] == odd
    assert store.load(path) == [WORK, EVENING]


@pytest.mark.parametrize("content", [b"{not json", b'{"a": 1}', b"\xff\xfe"])
def test_a_damaged_file_is_never_saved_over(tmp_path, content):
    path = tmp_path / "schedules.json"
    path.write_bytes(content)
    with pytest.raises(store.DamagedError):
        store.load(path)
    with pytest.raises(store.DamagedError):
        store.save([WORK], password_ok=True, now=NOW, path=path)
    assert path.read_bytes() == content


def test_update_applies_the_change_to_what_is_stored_at_the_time(tmp_path):
    path = tmp_path / "schedules.json"
    store.save([WORK], password_ok=False, now=NOW, path=path)
    store.update(lambda stored: [*stored, EVENING], False, NOW, path)
    assert store.load(path) == [WORK, EVENING]


def test_duplicate_ids_are_refused(tmp_path):
    with pytest.raises(sch.ScheduleError):
        store.save([EVENING, EVENING], True, NOW, tmp_path / "s.json")


def test_a_failed_write_leaves_no_temp_file(tmp_path, monkeypatch):
    def boom(*a):
        raise OSError("disk full")

    monkeypatch.setattr(store.os, "replace", boom)
    with pytest.raises(OSError):
        store.write_text("[]", tmp_path / "s.json")
    assert list(tmp_path.iterdir()) == []


def test_end_early_on_a_missing_or_corrupt_file_writes_nothing(tmp_path):
    missing = tmp_path / "missing.json"
    assert store.end_early("work", True, NOW, missing) == sch.NOT_RUNNING
    assert not missing.exists()
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json")
    assert store.end_early("work", True, NOW, corrupt) == sch.NOT_RUNNING
    assert corrupt.read_text() == "{not json"
