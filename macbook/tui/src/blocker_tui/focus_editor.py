"""Starting focus mode: tick the sites to allow (presets like Google Docs, or
type any site), add the apps to allow (Linux), pick how long, start. Moved
around like the schedule editor (h/j/k/l, enter to type in an "add" box,
enter to add)."""

from typing import Callable, List, Optional, Sequence, Set, Tuple

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.suggester import SuggestFromList
from textual.widgets import Button, Checkbox, Input, Static

from blocker_tui.schedule_editor import KEYS_MOVING, Field, GridForm
from blocklib import focus as focus_mode
from blocklib.domain import known_domains
from blocklib.focus import AllowedApp, Focus

LENGTHS = [("25m", 25), ("50m", 50), ("1h", 60), ("2h", 120)]
SITES_PER_ROW = 3
APPS_PER_ROW = 3
# Told to whoever picks apps: what focus never closes (see linux_apps.py).
ALWAYS_ALLOWED_TEXT = (
    "always allowed: Chrome (where only the sites above open), Block, and "
    "your terminal and what runs in it. other browsers close. apps that "
    "start at login come ticked: untick one to close it too."
)


def no_markup(text: str) -> str:
    """`text` shown as it is: Textual reads "[...]" as styling (an app
    called "Tool [Beta]" would lose its "[Beta]"), and its own escape()
    only escapes the brackets that look like its tags."""
    return text.replace("[", "\\[")


def build(
    sites: List[str],
    minutes: int,
    now_ms: int,
    apps: Sequence[AllowedApp] = (),
) -> "tuple[Optional[Focus], str]":
    """The focus these choices describe, or (None, what's wrong)."""
    if not sites and not apps:
        return None, "pick at least one site or app."
    return (
        Focus(
            now_ms + minutes * 60_000,
            tuple(sites),
            focus_mode.domains_for(sites),
            tuple(apps),
        ),
        "",
    )


def match_app(
    text: str, apps: Sequence[AllowedApp]
) -> Tuple[Optional[AllowedApp], str]:
    """The app someone typed: its name, the start of its name or a word in
    it, if only one fits. Else (None, what's wrong)."""
    typed = text.strip().lower()
    if not typed:
        return None, ""
    for fits in (
        lambda a: typed in (a.name.lower(), a.id.lower()),
        lambda a: a.name.lower().startswith(typed),
        lambda a: typed in a.name.lower(),
    ):
        found = [a for a in apps if fits(a)]
        if len(found) == 1:
            return found[0], ""
        if found:
            return None, f"which one? {_names(found)}"
    return None, f"no app called {text.strip()}."


def _names(apps: Sequence[AllowedApp]) -> str:
    """Up to four names; two apps with one name (a snap and a Flatpak)
    show their ids, which can be typed to pick one."""
    names = [a.name for a in apps]
    shown = [
        f"{a.name} ({a.id})" if names.count(a.name) > 1 else a.name for a in apps[:4]
    ]
    return ", ".join(shown) + (", ..." if len(apps) > 4 else "")


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
        apps: Sequence[AllowedApp] = (),
        ticked: Sequence[AllowedApp] = (),
    ) -> None:
        """on_start(focus, close) starts it and calls close() once it has.
        `blocked` is what's blocked now, to warn that it stays blocked.
        `apps` are the apps that can be allowed; none hides apps. `ticked`
        start out allowed (apps that start at login)."""
        super().__init__()
        self.on_start = on_start
        self.blocked = blocked
        self.now_ms = now_ms
        self.apps = list(apps)
        self.site_names: List[str] = list(focus_mode.PRESETS)
        self.picked: Set[str] = set()
        self.app_choices: List[AllowedApp] = list(ticked)  # added, in order
        self.apps_picked: Set[str] = {a.id for a in ticked}
        self.minutes = 50

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="editor-dialog", can_focus=False):
            yield Static("FOCUS", classes="title")
            yield Static(
                "only the sites you allow can be open in Chrome until it ends"
                + (", and only the apps you allow can run." if self.apps else "."),
                classes="label",
            )
            blocked = self._blocked_names()
            if blocked:
                yield Static(
                    f"blocked now, and they stay blocked: {', '.join(blocked)}",
                    classes="label",
                )
            yield Static("allow sites", classes="label")
            yield Vertical(*self._site_rows(), id="site-rows")
            yield Static("add a site", classes="label")
            yield Field(
                placeholder="enter, type e.g. wikipedia.org, enter",
                id="new-site",
                compact=True,
                select_on_focus=False,
            )
            if self.apps:
                yield Static("allow apps", classes="label")
                yield Vertical(*self._app_rows(), id="app-rows")
                yield Static("add an app", classes="label")
                yield Field(
                    placeholder="enter, type e.g. obsidian, enter",
                    id="new-app",
                    compact=True,
                    select_on_focus=False,
                    suggester=SuggestFromList(
                        [a.name for a in self.apps], case_sensitive=False
                    ),
                )
                yield Static(ALWAYS_ALLOWED_TEXT, classes="label")
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

    def _blocked_names(self) -> List[str]:
        """The usual sites that are blocked right now, by name."""
        names: List[str] = []
        for d in known_domains():
            if d.url in self.blocked and d.name not in names:
                names.append(d.name)
        return names

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

    def _app_rows(self) -> List[Horizontal]:
        rows = []
        for start in range(0, len(self.app_choices), APPS_PER_ROW):
            boxes = [
                Checkbox(
                    no_markup(a.name),
                    a.id in self.apps_picked,
                    id=f"app-{i}",
                    classes="app",
                    compact=True,
                )
                for i, a in enumerate(
                    self.app_choices[start : start + APPS_PER_ROW], start
                )
            ]
            rows.append(Horizontal(*boxes, classes="row"))
        return rows

    def on_mount(self) -> None:
        self.query_one("#site-0").focus()
        self._update()

    def _rows(self) -> List[List[str]]:
        n = len(self.site_names)
        rows = [
            *[
                [f"site-{i}" for i in range(start, min(start + SITES_PER_ROW, n))]
                for start in range(0, n, SITES_PER_ROW)
            ],
            ["new-site"],
        ]
        if self.apps:
            m = len(self.app_choices)
            rows += [
                *[
                    [f"app-{i}" for i in range(start, min(start + APPS_PER_ROW, m))]
                    for start in range(0, m, APPS_PER_ROW)
                ],
                ["new-app"],
            ]
        return [
            *rows,
            [f"length-{minutes}" for _, minutes in LENGTHS],
            ["start", "cancel"],
        ]

    def _sites(self) -> List[str]:
        return [s for s in self.site_names if s in self.picked]

    def _apps(self) -> List[AllowedApp]:
        return [a for a in self.app_choices if a.id in self.apps_picked]

    def _update(self) -> None:
        for _, minutes in LENGTHS:
            button = self.query_one(f"#length-{minutes}", Button)
            button.variant = "success" if minutes == self.minutes else "default"
        focus, problem = build(self._sites(), self.minutes, self.now_ms(), self._apps())
        summary = ""
        if focus is not None:
            allows = [
                *(["sites " + ", ".join(focus.domains)] if focus.domains else []),
                *(
                    ["apps " + ", ".join(a.name for a in focus.apps)]
                    if focus.apps
                    else []
                ),
            ]
            summary = f"allows {'; '.join(allows)}"
            if not focus.domains:
                summary += "\nno sites: every page in Chrome goes to the focus page."
            # Blocks stack: a blocked site stays blocked during focus.
            clash = sorted(
                d
                for d in focus.domains
                if any(b == d or b.endswith(f".{d}") for b in self.blocked)
            )
            if clash:
                summary += f"\n{', '.join(clash)} is blocked, so it stays blocked."
        self.query_one("#summary", Static).update(no_markup(summary))
        self.query_one("#editor-error", Static).update(no_markup(problem))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        box = event.checkbox
        if box.has_class("app"):
            app_id = self.app_choices[int((box.id or "")[len("app-") :])].id
            if event.value:
                self.apps_picked.add(app_id)
            else:
                self.apps_picked.discard(app_id)
        else:
            name = str(box.label)
            if event.value:
                self.picked.add(name)
            else:
                self.picked.discard(name)
        self._update()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-site":
            await self._add_site(event.input)
        elif event.input.id == "new-app":
            await self._add_app(event.input)

    async def _add_site(self, field: Input) -> None:
        domain = focus_mode.normalize_domain(field.value)
        error = self.query_one("#editor-error", Static)
        if domain is None:
            error.update("that isn't a site; try something like wikipedia.org.")
            return
        if domain not in self.site_names:
            self.site_names.append(domain)
        self.picked.add(domain)
        field.value = ""
        rows = self.query_one("#site-rows", Vertical)
        await rows.remove_children()
        await rows.mount(*self._site_rows())
        self._update()

    async def _add_app(self, field: Input) -> None:
        app, problem = match_app(field.value, self.apps)
        if app is None:
            if problem:
                self.query_one("#editor-error", Static).update(no_markup(problem))
            return
        if all(a.id != app.id for a in self.app_choices):
            self.app_choices.append(app)
        self.apps_picked.add(app.id)
        field.value = ""
        rows = self.query_one("#app-rows", Vertical)
        await rows.remove_children()
        await rows.mount(*self._app_rows())
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
        focus, problem = build(self._sites(), self.minutes, self.now_ms(), self._apps())
        if focus is None:
            self.query_one("#editor-error", Static).update(no_markup(problem))
            self.notify(no_markup(problem), severity="warning")
            return
        self.on_start(focus, lambda: self.dismiss(focus))
