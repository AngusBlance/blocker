"""The schedule editor: pick the days, the from–to times and the sites a
schedule blocks. The same fields and checks as the Android editor
(schedule_editor.dart). h/j/k/l (or arrows) move around the form, x or space
ticks a box, enter presses a button (in a text box it moves on, like tab),
ctrl+s saves, esc cancels."""

import re
from dataclasses import replace
from typing import Callable, Dict, List, Optional, Tuple

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Static

from blocker_tui import schedules as sched_ui
from blocklib.domain import known_domains
from blocklib.schedule import Block, EveryPlan, Schedule, ScheduleError

DAY_LETTERS = "MTWTFSS"
DAY_SHORTCUTS = {
    "weekdays": {1, 2, 3, 4, 5},
    "every-day": set(range(1, 8)),
    "weekends": {6, 7},
}
_TIME = re.compile(r"([0-9]{1,2}):?([0-9]{2})")


def site_domains() -> Dict[str, List[str]]:
    """Each known site and the domains that block it, in display order."""
    groups: Dict[str, List[str]] = {}
    for d in known_domains():
        groups.setdefault(d.name, []).append(d.url)
    return groups


def parse_time(text: str) -> Optional[int]:
    """Minutes after midnight for "9:00", "09:00" or "0900"; None if it
    isn't a time."""
    match = _TIME.fullmatch(text.strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def build(
    initial: Optional[Schedule],
    new_id: str,
    name: str,
    days: set,
    start_text: str,
    end_text: str,
    all_day: bool,
    sites: List[str],
) -> Tuple[Optional[Schedule], str]:
    """The schedule these fields describe, or (None, what's wrong). Checks in
    the same order, with the same wording, as the Android editor."""
    start, end = (0, 0) if all_day else (parse_time(start_text), parse_time(end_text))
    if start is None:
        return None, "from should be a time like 09:00."
    if end is None:
        return None, "to should be a time like 17:00."
    if not all_day and start == end:
        return None, "from and to can't be the same time."
    if not days:
        return None, "pick at least one day."
    groups = site_domains()
    picked = [s for s in groups if s in sites]
    if not picked:
        return None, "pick at least one site."
    if not name.strip():
        return None, "give it a name."
    try:
        plan = EveryPlan(frozenset(days), start, end)
    except ScheduleError as e:
        return None, f"{e}."
    # Sites this version doesn't know (say, from a newer one) are kept with
    # their domains, as on Android: the editor can't show them, so it mustn't
    # silently drop them.
    unknown = [n for n in (initial.sites if initial else ()) if n not in groups]
    known_urls = {u for urls in groups.values() for u in urls}
    kept = [d for d in (initial.domains if initial else ()) if d not in known_urls]
    fields = dict(
        name=name.strip(),
        sites=(*picked, *unknown),
        domains=(*(u for s in picked for u in groups[s]), *(kept if unknown else ())),
        plan=plan,
    )
    if initial is not None:
        return replace(initial, **fields), ""
    return Schedule(id=new_id, apps=(), action=Block(), **fields), ""


class ScheduleEditor(ModalScreen):
    """Dismisses with the finished Schedule, or None if cancelled."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        initial: Optional[Schedule] = None,
        new_id: Callable[[], str] = lambda: sched_ui.new_id(),
        on_save: Optional[Callable[[Schedule, Callable[[], None]], None]] = None,
    ) -> None:
        """on_save(schedule, close) stores the schedule and calls close() once
        it's stored; until then the editor stays open (e.g. while a password
        is asked for), so a cancelled save loses nothing. Without on_save the
        editor just dismisses with the schedule."""
        super().__init__()
        self.initial = initial
        self.on_save = on_save
        self._want_col = 0
        self.new_id = new_id()
        self.site_names = list(site_domains())

    def compose(self) -> ComposeResult:
        s = self.initial
        plan = (
            s.plan
            if s is not None
            else EveryPlan(frozenset({1, 2, 3, 4, 5}), 540, 1020)
        )
        days = plan.days if isinstance(plan, EveryPlan) else frozenset()
        all_day = isinstance(plan, EveryPlan) and plan.all_day
        with VerticalScroll(id="editor-dialog", can_focus=False):
            yield Static("EDIT SCHEDULE" if s else "NEW SCHEDULE", classes="title")
            if s is None:
                yield Static("start from", classes="label")
                with Horizontal(classes="row"):
                    for i, p in enumerate(sched_ui.PRESETS):
                        yield Button(p.label, id=f"preset-{i}", compact=True)
            yield Static("name", classes="label")
            yield Input(
                s.name if s else "",
                placeholder="e.g. work",
                id="schedule-name",
                compact=True,
                select_on_focus=False,  # a stray key mustn't replace the name
            )
            yield Static("days", classes="label")
            with Horizontal(classes="row"):
                for d in range(1, 8):
                    yield Checkbox(
                        DAY_LETTERS[d - 1], d in days, id=f"day-{d}", compact=True
                    )
            with Horizontal(classes="row"):
                for key in DAY_SHORTCUTS:
                    yield Button(key.replace("-", " "), id=f"days-{key}", compact=True)
            yield Static("time", classes="label")
            with Horizontal(classes="row"):
                yield Static("from ", classes="inline")
                yield Input(
                    sched_ui.format_minute(plan.start if not all_day else 540),
                    id="time-from",
                    classes="time",
                    compact=True,
                )
                yield Static(" to ", classes="inline")
                yield Input(
                    sched_ui.format_minute(plan.end if not all_day else 1020),
                    id="time-to",
                    classes="time",
                    compact=True,
                )
                yield Checkbox("all day", all_day, id="all-day", compact=True)
            yield Static("", id="summary")
            yield Static("sites", classes="label")
            picked = set(s.sites) if s else set()
            for i, name in enumerate(self.site_names):
                yield Checkbox(name, name in picked, id=f"site-{i}", compact=True)
            yield Static("", id="editor-error")
            with Horizontal(classes="row"):
                yield Button("save", variant="primary", id="save", compact=True)
                yield Button("cancel", id="cancel", compact=True)
            yield Static(
                "h j k l move · x ticks · enter presses · ctrl+s saves · esc cancels",
                id="editor-keys",
            )

    def on_mount(self) -> None:
        # A new schedule starts with typing its name; an existing one on the
        # days, ready to move around with h/j/k/l.
        first = "#schedule-name" if self.initial is None else "#day-1"
        self.query_one(first).focus()
        self._update()

    # Reading the form

    def _days(self) -> set:
        return {d for d in range(1, 8) if self.query_one(f"#day-{d}", Checkbox).value}

    def _sites(self) -> List[str]:
        return [
            name
            for i, name in enumerate(self.site_names)
            if self.query_one(f"#site-{i}", Checkbox).value
        ]

    def _result(self) -> Tuple[Optional[Schedule], str]:
        return build(
            self.initial,
            self.new_id,
            self.query_one("#schedule-name", Input).value,
            self._days(),
            self.query_one("#time-from", Input).value,
            self.query_one("#time-to", Input).value,
            self.query_one("#all-day", Checkbox).value,
            self._sites(),
        )

    def _update(self) -> None:
        """Summary line ("weekdays · 09:00–17:00") and what's missing."""
        all_day = self.query_one("#all-day", Checkbox).value
        for field in ("#time-from", "#time-to"):
            self.query_one(field, Input).disabled = all_day
        schedule, problem = self._result()
        summary = ""
        if schedule is not None:
            summary = sched_ui.format_plan(schedule.plan)
        else:
            days = self._days()
            start = parse_time(self.query_one("#time-from", Input).value)
            end = parse_time(self.query_one("#time-to", Input).value)
            if days and (
                all_day or (start is not None and end is not None and start != end)
            ):
                plan = (
                    EveryPlan(frozenset(days), 0, 0)
                    if all_day
                    else EveryPlan(frozenset(days), start, end)
                )
                summary = sched_ui.format_plan(plan)
        self.query_one("#summary", Static).update(summary)
        self.query_one("#editor-error", Static).update(problem)

    # Moving around: vim keys (and arrows) on a grid of the form's rows.
    # In a text box letters type, so only the up and down arrows move.

    _MOVES = {
        "h": (0, -1),
        "left": (0, -1),
        "l": (0, 1),
        "right": (0, 1),
        "j": (1, 0),
        "down": (1, 0),
        "k": (-1, 0),
        "up": (-1, 0),
    }

    def _grid(self) -> List[List[Widget]]:
        rows: List[List[str]] = []
        if self.initial is None:
            rows.append([f"preset-{i}" for i in range(len(sched_ui.PRESETS))])
        rows += [
            ["schedule-name"],
            [f"day-{d}" for d in range(1, 8)],
            [f"days-{key}" for key in DAY_SHORTCUTS],
            ["time-from", "time-to", "all-day"],
            *[[f"site-{i}"] for i in range(len(self.site_names))],
            ["save", "cancel"],
        ]
        grid = []
        for row in rows:
            widgets = [self.query_one(f"#{i}") for i in row]
            widgets = [w for w in widgets if not w.disabled]
            if widgets:
                grid.append(widgets)
        return grid

    def _move(self, rows: int, cols: int) -> None:
        grid = self._grid()
        here = next(
            (
                (r, c)
                for r, row in enumerate(grid)
                for c, w in enumerate(row)
                if w is self.focused
            ),
            None,
        )
        if here is None:
            target = grid[0][0]
        else:
            r, c = here
            if rows:
                # Like vim: up and down aim for the column you were last in.
                r = min(max(r + rows, 0), len(grid) - 1)
                c = min(self._want_col, len(grid[r]) - 1)
            else:
                c = min(max(c + cols, 0), len(grid[r]) - 1)
                self._want_col = c
            target = grid[r][c]
        target.focus()
        target.scroll_visible()

    def on_key(self, event: events.Key) -> None:
        typing = isinstance(self.focused, Input)
        if typing and event.key not in ("up", "down"):
            return
        if event.key in self._MOVES:
            self._move(*self._MOVES[event.key])
        elif event.key == "x" and isinstance(self.focused, Checkbox):
            self.focused.toggle()
        else:
            return
        event.stop()
        event.prevent_default()

    # Events

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._update()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter in a text box moves on, like tab; ctrl+s saves.
        self.focus_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id or ""
        if button == "save":
            self.action_save()
        elif button == "cancel":
            self.action_cancel()
        elif button.startswith("days-"):
            self._set_days(DAY_SHORTCUTS[button[len("days-") :]])
        elif button.startswith("preset-"):
            self._apply_preset(sched_ui.PRESETS[int(button[len("preset-") :])])

    def _set_days(self, days: set) -> None:
        for d in range(1, 8):
            self.query_one(f"#day-{d}", Checkbox).value = d in days

    def _apply_preset(self, preset: sched_ui.Preset) -> None:
        self._set_days(set(preset.days))
        self.query_one("#all-day", Checkbox).value = False
        self.query_one("#time-from", Input).value = sched_ui.format_minute(preset.start)
        self.query_one("#time-to", Input).value = sched_ui.format_minute(preset.end)
        # Fill the name in, or swap it if it's still another preset's name.
        name = self.query_one("#schedule-name", Input)
        if not name.value.strip() or name.value.strip() in {
            p.label for p in sched_ui.PRESETS
        }:
            name.value = preset.label

    def action_save(self) -> None:
        schedule, problem = self._result()
        if schedule is None:
            error = self.query_one("#editor-error", Static)
            error.update(problem)
            error.scroll_visible()
            self.notify(problem, severity="warning")  # seen even if scrolled off
            return
        if self.on_save is None:
            self.dismiss(schedule)
        else:
            self.on_save(schedule, lambda: self.dismiss(schedule))

    def action_cancel(self) -> None:
        self.dismiss(None)
