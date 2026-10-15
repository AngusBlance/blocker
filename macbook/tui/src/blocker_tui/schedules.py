"""The TUI's schedules section: how schedules read on screen, and the
presets new ones start from. Mirrors the Android app's wording
(schedule_format.dart). On the Mac a schedule always blocks: messages and
redirects are Android-only."""

import secrets
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional

from blocklib import schedule_store
from blocklib.schedule import EveryPlan, ForPlan, Schedule, local_now, next_up

# Patched by tests; looked up at call time.
SCHEDULES_PATH: Path = schedule_store.SCHEDULES_FILE


def now() -> datetime:
    return local_now()


class Preset(NamedTuple):
    label: str
    days: frozenset
    start: int
    end: int

    @property
    def plan(self) -> EveryPlan:
        return EveryPlan(self.days, self.start, self.end)


PRESETS = [
    Preset("work 9–5", frozenset({1, 2, 3, 4, 5}), 9 * 60, 17 * 60),
    Preset("evenings", frozenset(range(1, 8)), 18 * 60, 23 * 60),
    Preset("bedtime", frozenset({1, 2, 3, 4, 7}), 22 * 60, 7 * 60),
]

_DAY_LETTERS = "MTWTFSS"
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_days(days) -> str:
    if len(days) == 7:
        return "every day"
    if set(days) == {1, 2, 3, 4, 5}:
        return "weekdays"
    if set(days) == {6, 7}:
        return "weekends"
    return " ".join(_DAY_LETTERS[d - 1] for d in sorted(days))


def format_minute(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def format_plan(plan) -> str:
    if isinstance(plan, ForPlan):
        return "one-off block"
    if plan.all_day:
        times = "all day"
    else:
        times = f"{format_minute(plan.start)}–{format_minute(plan.end)}"
        if plan.overnight:
            times += " next day"
    return f"{format_days(plan.days)} · {times}"


def format_until(t: datetime, current: datetime) -> str:
    """ "17:00", "midnight", "tomorrow 07:00", "Fri 09:00", "next Mon 09:00"."""
    t = t.astimezone(current.tzinfo) if current.tzinfo else t
    days = (t.date() - current.date()).days
    clock = format_minute(t.hour * 60 + t.minute)
    if days <= 0:
        return clock
    if days == 1:
        return "midnight" if clock == "00:00" else f"tomorrow {clock}"
    prefix = "next " if days >= 7 else ""
    return f"{prefix}{_DAY_NAMES[t.weekday()]} {clock}"


def _from_ms(ms: int, current: datetime) -> datetime:
    return datetime.fromtimestamp(ms / 1000, current.tzinfo)


def status(s: Schedule, current: datetime) -> str:
    if not s.enabled:
        return "off"
    until = s.active_until(current)
    if until is not None:
        return f"running · until {format_until(_from_ms(until, current), current)}"
    if s.paused_until is not None and current.timestamp() * 1000 < s.paused_until:
        return "ended early · back next time"
    return "on"


def shown(schedules: List[Schedule], current: datetime) -> List[Schedule]:
    """Recurring schedules, plus one-offs while they run (finished ones are
    history)."""
    return [
        s for s in schedules if isinstance(s.plan, EveryPlan) or s.is_active(current)
    ]


def schedules_text(
    schedules: List[Schedule],
    selected_id: str,
    current: datetime,
    helper_installed: bool,
    error: Optional[str] = None,
) -> str:
    rows = shown(schedules, current)
    lines = ["SCHEDULES"]
    if error:
        lines += [
            f"  ! {error}",
            "    fix or delete the file; nothing is saved over it.",
        ]
    if not helper_installed:
        lines += [
            "  ! the schedule helper isn't installed, so schedules won't block.",
            "    run `block install` once to set it up.",
        ]
    lines.append("")
    if not rows and not error:
        lines.append("  no schedules yet. a schedule blocks sites at set times,")
        lines.append("  like weekdays 9–5 or every night. (a) adds one.")
    width = max((len(s.name) for s in rows), default=0)
    for s in rows:
        cursor = ">" if s.id == selected_id else " "
        # One-off blocks just run out, so they have no switch.
        if isinstance(s.plan, ForPlan):
            switch = "     "
        else:
            switch = "[on ]" if s.enabled else "[off]"
        lines.append(f"{cursor} {switch} {s.name:<{width}}  {format_plan(s.plan)}")
        lines.append(f"        {status(s, current)}")
    lines += [
        "",
        "  (a) add   (enter) edit   (t) on/off   (e) end early   (d) delete",
    ]
    return "\n".join(lines)


def dashboard_lines(schedules: List[Schedule], current: datetime) -> List[str]:
    running = [s for s in schedules if s.is_active(current)]
    lines = []
    if running:
        for s in running:
            until = _from_ms(s.active_until(current), current)
            lines.append(
                f"  schedule        {s.name} until {format_until(until, current)}"
            )
    else:
        lines.append("  schedule        none running")
    nxt = next_up(schedules, current)
    if nxt is not None:
        s, at = nxt
        lines.append(f"  next            {s.name} from {format_until(at, current)}")
    return lines


def new_id() -> str:
    return f"schedule-{secrets.token_hex(6)}"


def row_ids(schedules: List[Schedule], current: datetime) -> List[str]:
    return [s.id for s in shown(schedules, current)]


def moved(ids: List[str], selected_id: str, delta: int) -> str:
    """The id `delta` rows from `selected_id` (clamped), or the first row's
    if it isn't shown."""
    if not ids:
        return ""
    if selected_id not in ids:
        return ids[0]
    i = min(max(ids.index(selected_id) + delta, 0), len(ids) - 1)
    return ids[i]
