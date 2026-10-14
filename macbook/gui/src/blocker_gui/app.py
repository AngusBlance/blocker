"""Point-and-click front end for blocklib: the same blocker as the TUI, but
driven by buttons instead of hjkl, so it's used like any other app."""

import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, ContentSwitcher, Footer, Header, Input, Static

from blocklib.core import HOSTS_FILE, HostsBlocker
from blocklib.domain import known_domains
from blocklib.password import get_password, is_password_set, setup_password
from blocklib.ws_server import notify_external_daemon

SECTIONS = ["dashboard", "sites"]


def site_groups(hosts_path: Path) -> list:
    """[(name, urls, all_blocked)] per site, in the order blocklib lists them."""
    blocked = HostsBlocker(hosts_path).blocked_urls
    groups: dict = {}
    for d in known_domains():
        groups.setdefault(d.name, []).append(d.url)
    return [
        (name, urls, all(u in blocked for u in urls)) for name, urls in groups.items()
    ]


def sudo_needs_password() -> bool:
    result = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    return result.returncode != 0


class UnlockModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, site: str, password: str) -> None:
        super().__init__()
        self.site = site
        self.password = password

    def compose(self) -> ComposeResult:
        with Vertical(id="unlock-dialog"):
            yield Static(f"UNLOCK {self.site.upper()}", classes="title")
            yield Static("type the password below to unlock:", classes="muted")
            yield Static(self.password, id="password")
            yield Input(placeholder="type the password here", id="unlock-input")
            with Horizontal(classes="buttons"):
                yield Button("unlock", variant="warning", id="unlock")
                yield Button("keep it blocked", id="cancel")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "unlock":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        self.dismiss(self.query_one(Input).value == self.password)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GuiApp(App):
    TITLE = "blocker"

    CSS = """
    #nav {
        width: 22;
        height: 1fr;
        padding: 1;
        border: solid $border-blurred;
    }
    #nav Button {
        width: 100%;
        margin-bottom: 1;
    }
    #nav Button.active {
        color: $accent;
        text-style: bold;
        border-left: outer $accent;
    }
    ContentSwitcher {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
    }
    .title {
        text-style: bold;
        margin-bottom: 1;
    }
    .muted {
        color: $text-muted;
    }
    #status {
        margin-bottom: 1;
    }
    #site-list Button {
        width: 100%;
        margin-bottom: 1;
        content-align: left middle;
        text-align: left;
    }
    #site-list Button.blocked {
        color: $accent;
    }
    UnlockModal {
        align: center middle;
    }
    #unlock-dialog {
        width: 70;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #password {
        background: $panel;
        padding: 1;
        margin: 1 0;
    }
    #unlock-dialog Input:focus {
        border: tall $accent;
    }
    #unlock-dialog .buttons {
        height: auto;
        margin-top: 1;
    }
    #unlock-dialog .buttons Button {
        margin-right: 2;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, hosts_path: Path = HOSTS_FILE) -> None:
        super().__init__()
        self.hosts_path = hosts_path

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="nav"):
                for name in SECTIONS:
                    yield Button(name, id=f"nav-{name}")
            with ContentSwitcher(initial="dashboard"):
                with Vertical(id="dashboard"):
                    yield Static("STATUS", classes="title")
                    yield Static(id="status")
                    yield Button("block all sites", variant="warning", id="block-all")
                with VerticalScroll(id="sites"):
                    yield Static("BLOCKED SITES", classes="title")
                    yield Static(id="sites-summary", classes="muted")
                    yield Vertical(id="site-list")
                    yield Static(
                        "click a site to block it. unblocking needs the password.",
                        classes="muted",
                    )
        yield Footer()

    def on_mount(self) -> None:
        if not is_password_set():
            setup_password()
        self.show_section("dashboard")

    def show_section(self, name: str) -> None:
        self.query_one(ContentSwitcher).current = name
        for section in SECTIONS:
            self.query_one(f"#nav-{section}").set_class(section == name, "active")
        self.refresh_views()

    def refresh_views(self) -> None:
        groups = site_groups(self.hosts_path)
        blocked = [name for name, _, is_blocked in groups if is_blocked]
        state = "BLOCKED" if HostsBlocker(self.hosts_path).is_active else "not blocked"
        self.query_one("#status", Static).update(
            f"state   {state}\nsites   {len(groups)} sites, {len(blocked)} blocked"
        )
        self.query_one("#sites-summary", Static).update(
            f"{len(groups)} sites, {len(blocked)} blocked"
        )
        site_list = self.query_one("#site-list")
        site_list.remove_children()
        site_list.mount_all(
            Button(
                f"{'(x)' if is_blocked else '( )'} {name}",
                name=name,
                classes="site blocked" if is_blocked else "site",
            )
            for name, _, is_blocked in groups
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        if button.id and button.id.startswith("nav-"):
            self.show_section(button.id.removeprefix("nav-"))
        elif button.id == "block-all":
            urls = [d.url for d in known_domains()]
            self._change(lambda b: b.block_all(urls), "Blocked all sites")
        elif button.has_class("site"):
            self._toggle_site(button.name)

    def _toggle_site(self, name: str) -> None:
        for site, urls, is_blocked in site_groups(self.hosts_path):
            if site != name:
                continue
            if not is_blocked:
                self._change(lambda b: b.block_all(urls), f"Blocked {name}")
            elif not is_password_set():
                self._change(lambda b: b.unblock_all(urls), f"Unlocked {name}")
            else:
                self._ask_password(name, urls)
            return

    def _ask_password(self, name: str, urls: list) -> None:
        def handle(correct) -> None:
            if correct is None:
                return
            if not correct:
                self.notify("Incorrect password", severity="error")
                return
            self._change(lambda b: b.unblock_all(urls), f"Unlocked {name}")

        self.push_screen(UnlockModal(name, get_password()), handle)

    def _change(self, action, message: str) -> None:
        """Runs a blocklib change, which may need the sudo password."""
        try:
            with self._maybe_suspend():
                action(HostsBlocker(self.hosts_path))
        except (subprocess.CalledProcessError, OSError) as e:
            self.notify(f"Failed: {e}", severity="error", timeout=6)
        else:
            self.notify(message)
            # Let the Chrome extension pick up the change via the sync daemon.
            threading.Thread(target=notify_external_daemon, daemon=True).start()
        self.refresh_views()

    @contextmanager
    def _maybe_suspend(self):
        # sudo asks for its password in the terminal, so step out of the way.
        if not sudo_needs_password():
            yield
            return
        try:
            with self.suspend():
                yield
        except SuspendNotSupported:
            yield


def main() -> None:
    GuiApp().run()


if __name__ == "__main__":
    main()
