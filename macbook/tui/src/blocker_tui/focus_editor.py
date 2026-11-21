"""Starting focus mode: tick the sites to allow (presets like Google Docs, or
type any site), pick how long, start. Moved around like the schedule
editor (h/j/k/l, enter to type in the "add a site" box, enter to add)."""

from typing import Callable, List, Optional, Set

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Static

from blocker_tui.schedule_editor import KEYS_MOVING, Field, GridForm
from blocklib import focus as focus_mode
from blocklib.focus import Focus

LENGTHS = [("25m", 25), ("50m", 50), ("1h", 60), ("2h", 120)]
SITES_PER_ROW = 3


def build(sites: List[str], minutes: int, now_ms: int) -> "tuple[Optional[Focus], str]":
    """The focus these choices describe, or (None, what's wrong)."""
    if not sites:
        return None, "pick at least one site."
    return (
        Focus(now_ms + minutes * 60_000, tuple(sites), focus_mode.domains_for(sites)),
        "",
    )


class FocusEditor(GridForm):
    """Dismisses with the started Focus, or None."""

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("ctrl+s", "start", "Start"),
    ]

    def __init__(
        self,
        on_start: Callable[[Focus, Callable[[], None]], None],
        blocked: Set[str] = frozenset(),
        now_ms: Callable[[], int] = focus_mode.now_ms,
    ) -> None:
        """on_start(focus, close) starts it and calls close() once it has.
        `blocked` is what's blocked now, to warn that it stays blocked."""
        super().__init__()
        self.on_start = on_start
        self.blocked = blocked
        self.now_ms = now_ms
        self.site_names: List[str] = list(focus_mode.PRESETS)
        self.picked: Set[str] = set()
        self.minutes = 50

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="editor-dialog", can_focus=False):
            yield Static("FOCUS", classes="title")
            yield Static(
                "only the sites you allow can be open in Chrome until it ends.",
                classes="label",
            )
            yield Static("allow", classes="label")
            yield Vertical(*self._site_rows(), id="site-rows")
            yield Static("add a site", classes="label")
            yield Field(
                placeholder="enter, type e.g. wikipedia.org, enter",
                id="new-site",
                compact=True,
                select_on_focus=False,
            )
            yield Static("for", classes="label")
            with Horizontal(classes="row"):
                for label, minutes in LENGTHS:
                    yield Button(label, id=f"length-{minutes}", compact=True)
            yield Static("", id="summary")
            yield Static("", id="editor-error")
            with Horizontal(classes="row"):
                yield Button("start", variant="primary", id="start", compact=True)
                yield Button("cancel", id="cancel", compact=True)
            yield Static(KEYS_MOVING, id="editor-keys")

    def _site_rows(self) -> List[Horizontal]:
        rows = []
        for start in range(0, len(self.site_names), SITES_PER_ROW):
            boxes = [
                Checkbox(
                    name,
                    name in self.picked,
                    id=f"site-{i}",
                    classes="site",
                    compact=True,
                )
                for i, name in enumerate(
                    self.site_names[start : start + SITES_PER_ROW], start
                )
            ]
            rows.append(Horizontal(*boxes, classes="row"))
        return rows

    def on_mount(self) -> None:
        self.query_one("#site-0").focus()
        self._update()

    def _rows(self) -> List[List[str]]:
        n = len(self.site_names)
        return [
            *[
                [f"site-{i}" for i in range(start, min(start + SITES_PER_ROW, n))]
                for start in range(0, n, SITES_PER_ROW)
            ],
            ["new-site"],
            [f"length-{minutes}" for _, minutes in LENGTHS],
            ["start", "cancel"],
        ]

    def _sites(self) -> List[str]:
        return [s for s in self.site_names if s in self.picked]

    def _update(self) -> None:
        for _, minutes in LENGTHS:
            button = self.query_one(f"#length-{minutes}", Button)
            button.variant = "success" if minutes == self.minutes else "default"
        focus, problem = build(self._sites(), self.minutes, self.now_ms())
        summary = ""
        if focus is not None:
            summary = f"allows {', '.join(focus.domains)}"
            # Blocks stack: a blocked site stays blocked during focus.
            clash = sorted(
                d
                for d in focus.domains
                if any(b == d or b.endswith(f".{d}") for b in self.blocked)
            )
            if clash:
                summary += f"\n{', '.join(clash)} is blocked, so it stays blocked."
        self.query_one("#summary", Static).update(summary)
        self.query_one("#editor-error", Static).update(problem)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        name = str(event.checkbox.label)
        if event.value:
            self.picked.add(name)
        else:
            self.picked.discard(name)
        self._update()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "new-site":
            return
        domain = focus_mode.normalize_domain(event.value)
        error = self.query_one("#editor-error", Static)
        if domain is None:
            error.update("that isn't a site; try something like wikipedia.org.")
            return
        if domain not in self.site_names:
            self.site_names.append(domain)
        self.picked.add(domain)
        event.input.value = ""
        rows = self.query_one("#site-rows", Vertical)
        await rows.remove_children()
        await rows.mount(*self._site_rows())
        self._update()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id or ""
        if button == "start":
            self.action_start()
        elif button == "cancel":
            self.dismiss(None)
        elif button.startswith("length-"):
            self.minutes = int(button[len("length-") :])
            self._update()

    def action_start(self) -> None:
        if self._editing():
            self.focused.editing = False
        focus, problem = build(self._sites(), self.minutes, self.now_ms())
        if focus is None:
            self.query_one("#editor-error", Static).update(problem)
            self.notify(problem, severity="warning")
            return
        self.on_start(focus, lambda: self.dismiss(focus))
