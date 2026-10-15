"""Schedules on the Mac: blocks that apply at set times.

The same model, JSON and rules as androidlib's Schedule.kt / ScheduleRules.kt
on Android (all three platforms test against shared/schedules.json):

- an "every" plan blocks on chosen ISO weekdays (1 = Monday) from `start` to
  `end` minutes after local midnight; end < start runs overnight and belongs
  to the day it starts on; start == end means all day;
- a "for" plan blocks once, from `startsAt` until `endsAt` (epoch ms);
- `pausedUntil` (epoch ms) is set by ending a schedule early, which pauses
  only the occurrence running then.

Standard library only and Python 3.9 compatible: the root helper that applies
schedules to /etc/hosts runs this file with the system python, from a
root-owned copy.
"""

import json
import os
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional, Set, Tuple, Union

MINUTES_PER_DAY = 24 * 60


class ScheduleError(ValueError):
    """Malformed schedule JSON or an invalid plan."""


class LockedError(Exception):
    """A save would weaken a running schedule without the unlock password."""


@dataclass(frozen=True)
class ForPlan:
    starts_at: int  # epoch ms, inclusive
    ends_at: int  # epoch ms, exclusive

    def __post_init__(self):
        if self.ends_at <= self.starts_at:
            raise ScheduleError("endsAt must be after startsAt")


@dataclass(frozen=True)
class EveryPlan:
    days: frozenset  # ISO weekdays, 1 = Monday
    start: int
    end: int

    def __post_init__(self):
        if not self.days:
            raise ScheduleError("pick at least one day")
        if any(d not in range(1, 8) for d in self.days):
            raise ScheduleError("days are 1 (Mon) to 7 (Sun)")
        if self.start not in range(MINUTES_PER_DAY) or self.end not in range(
            MINUTES_PER_DAY
        ):
            raise ScheduleError("times must be within a day")

    @property
    def all_day(self) -> bool:
        return self.start == self.end

    @property
    def overnight(self) -> bool:
        return self.end < self.start

    def covers(self, now: datetime) -> bool:
        minute = now.hour * 60 + now.minute
        today = now.isoweekday()
        yesterday = 7 if today == 1 else today - 1
        if self.all_day:
            return today in self.days
        if self.start < self.end:
            return today in self.days and self.start <= minute < self.end
        return (today in self.days and minute >= self.start) or (
            yesterday in self.days and minute < self.end
        )

    def occurrence_end(self, now: datetime) -> Optional[datetime]:
        """When the occurrence covering `now` ends, or None if none does."""
        if not self.covers(now):
            return None
        today = now.date()
        minute = now.hour * 60 + now.minute
        if self.all_day:
            end_day, end_minute = today + timedelta(days=1), 0
        elif self.start < self.end or minute < self.end:
            end_day, end_minute = today, self.end
        else:  # overnight, evening part
            end_day, end_minute = today + timedelta(days=1), self.end
        end = _local(end_day, end_minute, now)
        if _ms(end) <= _ms(now):  # autumn overlap: the later repeat
            end = _local(end_day, end_minute, now, fold=1)
        return end


Plan = Union[ForPlan, EveryPlan]


@dataclass(frozen=True)
class Block:
    pass


@dataclass(frozen=True)
class Message:
    text: str


@dataclass(frozen=True)
class Redirect:
    package: str


Action = Union[Block, Message, Redirect]


@dataclass(frozen=True)
class Schedule:
    id: str
    name: str
    sites: Tuple[str, ...]
    domains: Tuple[str, ...]
    apps: Tuple[str, ...]
    plan: Plan
    action: Action = field(default_factory=Block)
    enabled: bool = True
    paused_until: Optional[int] = None  # epoch ms

    def is_active(self, now: datetime) -> bool:
        now = _aware(now)
        if not self.enabled:
            return False
        if self.paused_until is not None and _ms(now) < self.paused_until:
            return False
        if isinstance(self.plan, ForPlan):
            return self.plan.starts_at <= _ms(now) < self.plan.ends_at
        return self.plan.covers(now)

    def active_until(self, now: datetime) -> Optional[int]:
        """When the occurrence running now ends (epoch ms), or None."""
        now = _aware(now)
        if not self.is_active(now):
            return None
        if isinstance(self.plan, ForPlan):
            return self.plan.ends_at
        end = self.plan.occurrence_end(now)
        assert end is not None  # is_active means covers
        return _ms(end)

    def paused_for_current_occurrence(self, now: datetime) -> Optional["Schedule"]:
        until = self.active_until(now)
        return None if until is None else replace(self, paused_until=until)

    def next_start(self, now: datetime) -> Optional[datetime]:
        """When this next starts after `now` (and isn't paused then)."""
        now = _aware(now)
        if not self.enabled:
            return None

        def usable(t: datetime) -> bool:
            return _ms(t) > _ms(now) and (
                self.paused_until is None or _ms(t) >= self.paused_until
            )

        # A pause can end partway through an occurrence if the schedule was
        # edited after being ended early; it blocks again from then.
        resumes = None
        if self.paused_until is not None:
            t = datetime.fromtimestamp(self.paused_until / 1000, now.tzinfo)
            if _ms(t) > _ms(now) and replace(self, paused_until=None).is_active(t):
                resumes = t
        scheduled = None
        if isinstance(self.plan, ForPlan):
            start = datetime.fromtimestamp(self.plan.starts_at / 1000, now.tzinfo)
            scheduled = start if usable(start) else None
        else:
            for offset in range(15):
                day = now.date() + timedelta(days=offset)
                if day.isoweekday() in self.plan.days:
                    start = _local(day, self.plan.start, now)
                    if usable(start):
                        scheduled = start
                        break
        found = [t for t in (resumes, scheduled) if t is not None]
        return min(found, key=_ms) if found else None

    def to_json(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "sites": list(self.sites),
            "domains": list(self.domains),
            "apps": list(self.apps),
            "plan": _plan_json(self.plan),
            "action": _action_json(self.action),
            "enabled": self.enabled,
        }
        if self.paused_until is not None:
            data["pausedUntil"] = self.paused_until
        return data

    @classmethod
    def from_json(cls, data: object) -> "Schedule":
        """Strict: anything malformed is a ScheduleError."""
        if not isinstance(data, dict):
            raise ScheduleError(f"schedule should be an object, got {data!r}")
        return cls(
            id=_get(data, "id", str),
            name=_get(data, "name", str),
            sites=_strings(data, "sites"),
            domains=_strings(data, "domains"),
            apps=_strings(data, "apps"),
            plan=_plan_from(_get(data, "plan", dict)),
            action=_action_from(_get(data, "action", dict)),
            enabled=_get(data, "enabled", bool) if "enabled" in data else True,
            paused_until=_get_ms(data, "pausedUntil")
            if "pausedUntil" in data
            else None,
        )


# Lists


def list_to_json(schedules: List[Schedule]) -> str:
    return json.dumps([s.to_json() for s in schedules])


def list_from_json(text: str) -> List[Schedule]:
    """Strict: malformed JSON or duplicate ids is a ScheduleError."""
    try:
        data = _loads(text)
    except (ValueError, RecursionError) as e:
        raise ScheduleError(f"malformed schedule list: {e!r}") from e
    if not isinstance(data, list):
        raise ScheduleError("schedule list should be a JSON array")
    schedules = [Schedule.from_json(item) for item in data]
    ids = [s.id for s in schedules]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ScheduleError(f"duplicate schedule ids: {sorted(duplicates)}")
    return schedules


def list_from_json_skipping_bad(text: Optional[str]) -> List[Schedule]:
    """For the root helper: one corrupt schedule is skipped, not allowed to
    take every other schedule down with it."""
    if not text or not text.strip():
        return []
    try:
        data = _loads(text)
    except (ValueError, RecursionError):
        return []
    if not isinstance(data, list):
        return []
    schedules = []
    for item in data:
        try:
            schedules.append(Schedule.from_json(item))
        except ScheduleError:
            continue
    return schedules


# Rules (ScheduleRules.kt)


def replace_all(
    stored: List[Schedule], incoming: List[Schedule], password_ok: bool, now: datetime
) -> List[Schedule]:
    """The list to store when saving `incoming`. Without the password a save
    may not weaken anything running now (decision D1): every running schedule
    must still be there, enabled, with the same plan, the same action (or plain
    blocking) and at least the same sites and apps. Pauses only come from
    pause(), so incoming ones are ignored and stored ones kept."""
    ids = [s.id for s in incoming]
    if len(set(ids)) != len(ids):
        raise ScheduleError("duplicate schedule ids")
    by_id = {s.id: s for s in stored}
    incoming = [
        replace(s, paused_until=by_id[s.id].paused_until if s.id in by_id else None)
        for s in incoming
    ]
    if not password_ok:
        next_by_id = {s.id: s for s in incoming}
        for running in (s for s in stored if s.is_active(now)):
            nxt = next_by_id.get(running.id)
            kept = (
                nxt is not None
                and nxt.enabled
                and nxt.plan == running.plan
                and (nxt.action == running.action or nxt.action == Block())
                and set(running.domains) <= set(nxt.domains)
                and set(running.apps) <= set(nxt.apps)
            )
            if not kept:
                raise LockedError(
                    f'"{running.name}" is running; changing it needs the unlock password'
                )
    return incoming


PAUSED, WRONG_PASSWORD, NOT_RUNNING = "paused", "wrong_password", "not_running"


def pause(
    stored: List[Schedule], schedule_id: str, password_ok: bool, now: datetime
) -> Tuple[str, Optional[List[Schedule]]]:
    """Ends schedule `schedule_id` early: pauses just the occurrence running
    now. Returns the result and, if paused, the list to store."""
    if not password_ok:
        return WRONG_PASSWORD, None
    for i, s in enumerate(stored):
        if s.id == schedule_id:
            paused = s.paused_for_current_occurrence(now)
            if paused is None:
                return NOT_RUNNING, None
            return PAUSED, [*stored[:i], paused, *stored[i + 1 :]]
    return NOT_RUNNING, None


def pause_json(
    stored_text: Optional[str], schedule_id: str, password_ok: bool, now: datetime
) -> Tuple[str, Optional[str]]:
    """pause() on the stored JSON text, rewriting only that schedule's entry,
    so entries this version can't read survive (like ScheduleRules.pause)."""
    if not password_ok:
        return WRONG_PASSWORD, None
    try:
        items = _loads(stored_text or "[]")
    except (ValueError, RecursionError):
        return NOT_RUNNING, None
    if not isinstance(items, list):
        return NOT_RUNNING, None
    for i, item in enumerate(items):
        if not isinstance(item, dict) or item.get("id") != schedule_id:
            continue
        try:
            paused = Schedule.from_json(item).paused_for_current_occurrence(now)
        except ScheduleError:
            continue
        if paused is None:
            return NOT_RUNNING, None
        items[i] = paused.to_json()
        return PAUSED, json.dumps(items)
    return NOT_RUNNING, None


def active_domains(schedules: List[Schedule], now: datetime) -> Set[str]:
    """Every domain a running schedule blocks right now."""
    return {d for s in schedules if s.is_active(now) for d in s.domains}


def next_up(
    schedules: List[Schedule], now: datetime
) -> Optional[Tuple[Schedule, datetime]]:
    """The schedule that starts soonest among those not running."""
    candidates = [
        (s, t)
        for s in schedules
        if not s.is_active(now)
        for t in [s.next_start(now)]
        if t is not None
    ]
    return min(candidates, key=lambda c: _ms(c[1])) if candidates else None


# Helpers


def _bounded_int(digits: str) -> int:
    # Python 3.9 has no limit on int parsing; a huge number takes seconds.
    if len(digits) > 20:
        raise ValueError("number too long")
    return int(digits)


def _loads(text: str):
    """json.loads for text a user (or anything running as them) wrote."""
    return json.loads(text, parse_int=_bounded_int)


def _aware(now: datetime) -> datetime:
    return now if now.tzinfo is not None else now.replace(tzinfo=_system_zone())


def _ms(t: datetime) -> int:
    return int(t.timestamp() * 1000)


def local_now() -> datetime:
    """Now, in the system's own time zone (with its DST rules), so wall-clock
    schedule times work out right on days the clocks change."""
    return datetime.now(_system_zone())


def _system_zone() -> tzinfo:
    """$TZ if set, else the zone /etc/localtime points at. Only if neither
    works, the current fixed offset (which knows nothing of DST)."""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
    except ImportError:  # pragma: no cover - 3.9+ always has it
        ZoneInfo = None
    names = [os.environ.get("TZ", "").lstrip(":")]
    # /etc/localtime -> /var/db/timezone/zoneinfo/Europe/London
    link = os.path.realpath("/etc/localtime")
    if "zoneinfo/" in link:
        names.append(link.split("zoneinfo/", 1)[1])
    for name in names:
        if name and ZoneInfo is not None:
            try:
                return ZoneInfo(name)
            except Exception:
                continue
    return datetime.now().astimezone().tzinfo or timezone.utc


def _local(day: date, minute: int, like: datetime, fold: int = 0) -> datetime:
    """`day` at `minute` past midnight in `like`'s time zone. A time skipped
    by a spring-forward gap is when the clocks jump (covers() is true from
    then), matching androidlib's Schedule.startOf."""
    tz = like.tzinfo or _system_zone()
    # Transitions fall on whole minutes (true of every zone in tzdb today).
    wall = datetime.combine(day, time(minute // 60, minute % 60, fold=fold))
    t = wall.replace(tzinfo=tz)
    if t.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == wall:
        return t
    # In a gap: the jump lies between the two readings of `wall`; find the
    # first minute whose wall-clock time is at or past it.
    lo = wall.replace(tzinfo=tz, fold=1).astimezone(timezone.utc)
    hi = wall.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    lo, hi = min(lo, hi), max(lo, hi)
    while hi - lo > timedelta(minutes=1):
        mid = lo + (hi - lo) // 2
        mid -= timedelta(seconds=mid.second, microseconds=mid.microsecond)
        if mid <= lo:
            break
        if mid.astimezone(tz).replace(tzinfo=None) >= wall:
            hi = mid
        else:
            lo = mid
    return hi.astimezone(tz)


def _get(data: dict, key: str, kind: type) -> Any:
    value = data.get(key)
    # bool is an int in Python; don't accept True as a time or a number.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ScheduleError(f"{key} should be {kind.__name__}, got {value!r}")
    return value


# 0001-01-01 to 9999-12-31: what datetime can represent.
_MS_RANGE = range(-62135596800000, 253402300800000)


def _get_ms(data: dict, key: str) -> int:
    value = _get(data, key, int)
    if value not in _MS_RANGE:
        raise ScheduleError(f"{key} is out of range: {value}")
    return value


def _strings(data: dict, key: str) -> Tuple[str, ...]:
    values = _get(data, key, list)
    if not all(isinstance(v, str) for v in values):
        raise ScheduleError(f"{key} should hold strings, got {values!r}")
    return tuple(values)


def _plan_json(plan: Plan) -> Dict[str, object]:
    if isinstance(plan, ForPlan):
        return {"type": "for", "startsAt": plan.starts_at, "endsAt": plan.ends_at}
    return {
        "type": "every",
        "days": sorted(plan.days),
        "start": plan.start,
        "end": plan.end,
    }


def _plan_from(data: dict) -> Plan:
    kind = _get(data, "type", str)
    if kind == "for":
        return ForPlan(_get_ms(data, "startsAt"), _get_ms(data, "endsAt"))
    if kind == "every":
        days = _get(data, "days", list)
        if not all(isinstance(d, int) and not isinstance(d, bool) for d in days):
            raise ScheduleError(f"days should be whole numbers, got {days!r}")
        return EveryPlan(
            frozenset(days), _get(data, "start", int), _get(data, "end", int)
        )
    raise ScheduleError(f"unknown plan type {kind}")


def _action_json(action: Action) -> Dict[str, str]:
    if isinstance(action, Message):
        return {"type": "message", "text": action.text}
    if isinstance(action, Redirect):
        return {"type": "redirect", "package": action.package}
    return {"type": "block"}


def _action_from(data: dict) -> Action:
    kind = _get(data, "type", str)
    if kind == "block":
        return Block()
    if kind == "message":
        return Message(_get(data, "text", str))
    if kind == "redirect":
        return Redirect(_get(data, "package", str))
    raise ScheduleError(f"unknown action type {kind}")
