import errno
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static

from blocklib.core import HOSTS_FILE, HostsBlocker
from blocklib.domain import known_domains
from blocklib.password import get_password, is_password_set, setup_password
from blocklib.ws_server import DEFAULT_WS_PORT, SyncServer, notify_external_daemon

SECTIONS = ["dashboard", "sites", "schedule", "unlock", "activity", "settings"]

SECTION_CONTENT = {
    "dashboard": "dashboard view (placeholder)",
    "sites": "sites view (placeholder)",
    "schedule": "schedule view (placeholder)",
    "unlock": "unlock view (placeholder)",
    "activity": "activity view (placeholder)",
    "settings": "settings view (placeholder)",
}


def get_status(hosts_path: Path = HOSTS_FILE) -> bool:
    return HostsBlocker(hosts_path).is_active


def dashboard_text(hosts_path: Path = HOSTS_FILE, sync_running: bool = False) -> str:
    state = "BLOCKED" if get_status(hosts_path) else "not blocked"
    sync_state = f"ws://127.0.0.1:{DEFAULT_WS_PORT}" if sync_running else "NOT RUNNING"
    return f"STATUS\n  state           {state}\n  extension sync  {sync_state}"


def sites_with_status(hosts_path: Path = HOSTS_FILE) -> list:
    blocked = HostsBlocker(hosts_path).blocked_urls
    domains = known_domains()
    for d in domains:
        d.is_blocked = d.url in blocked
    return domains


def site_groups(hosts_path: Path = HOSTS_FILE) -> list:
    """Domains grouped by service name, e.g. [("Netflix", [...]), ("YouTube", [...])]."""
    groups = {}
    for d in sites_with_status(hosts_path):
        groups.setdefault(d.name, []).append(d)
    return list(groups.items())


def sites_text(site_index: int, hosts_path: Path = HOSTS_FILE) -> str:
    groups = site_groups(hosts_path)
    blocked_count = sum(
        1 for _, members in groups if all(d.is_blocked for d in members)
    )
    lines = ["BLOCKED SITES", f"  {len(groups)} sites, {blocked_count} blocked", ""]
    for i, (name, members) in enumerate(groups):
        cursor = ">" if i == site_index else " "
        blocked_members = sum(d.is_blocked for d in members)
        if blocked_members == len(members):
            box = "(x)"
        elif blocked_members == 0:
            box = "( )"
        else:
            box = "(~)"
        lines.append(f"{cursor} {box} {name}")
    lines.append("")
    lines.append("  (b) block all")
    return "\n".join(lines)


def perform_block(hosts_path: Path = HOSTS_FILE) -> None:
    HostsBlocker(hosts_path).block_all([d.url for d in known_domains()])


def sudo_needs_password() -> bool:
    result = subprocess.run(["sudo", "-n", "true"], capture_output=True)
    return result.returncode != 0


class Sidebar(Static):
    selected_index: reactive[int] = reactive(0)

    def render(self) -> str:
        lines = []
        for i, name in enumerate(SECTIONS):
            marker = ">" if i == self.selected_index else " "
            lines.append(f"{marker} {name}")
        return "\n".join(lines)


class Content(Static):
    section: reactive[str] = reactive(SECTIONS[0], layout=True)
    site_index: reactive[int] = reactive(0, layout=True)
    sync_running: reactive[bool] = reactive(False)

    def render(self) -> str:
        if self.section == "dashboard":
            return dashboard_text(sync_running=self.sync_running)
        if self.section == "sites":
            return sites_text(self.site_index)
        return SECTION_CONTENT[self.section]


class UnlockModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, group_name: str, password: str) -> None:
        super().__init__()
        self.group_name = group_name
        self.password = password

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(
                f"UNLOCK {self.group_name.upper()}\n\n"
                "type the password below to unlock:\n\n"
                f"  {self.password}"
            ),
            Input(placeholder="type the password here", id="unlock-input"),
            id="unlock-dialog",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value == self.password)

    def action_cancel(self) -> None:
        self.dismiss(None)


class BlockerApp(App):
    CSS = """
    Sidebar {
        width: 20;
        height: 1fr;
        border: solid $border-blurred;
    }
    Content {
        width: 1fr;
        height: 1fr;
        border: solid $border-blurred;
    }
    Sidebar.focused-pane {
        border: solid $accent;
    }
    Content.focused-pane {
        border: solid $accent;
    }
    UnlockModal {
        align: center middle;
    }
    #unlock-dialog {
        width: 64;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #unlock-dialog Input {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("l", "focus_content", "Focus content / toggle site"),
        Binding("enter", "focus_content", "Focus content / toggle site", show=False),
        Binding("h", "focus_sidebar", "Focus sidebar"),
        Binding("b", "block_sites", "Block"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "blocker"

    focus_pane: reactive[str] = reactive("sidebar")

    @contextmanager
    def _maybe_suspend(self):
        if not sudo_needs_password():
            yield
            return
        try:
            with self.suspend():
                yield
        except SuspendNotSupported:
            yield

    def _run_privileged(self, action, success_message: str) -> bool:
        """Runs a privileged HostsBlocker call, notifying on success/failure."""
        try:
            with self._maybe_suspend():
                action()
        except (subprocess.CalledProcessError, OSError) as e:
            self.notify(f"Failed: {e}", severity="error", timeout=6)
            return False
        self.notify(success_message)
        return True

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(Sidebar(id="sidebar"), Content(id="content"))
        yield Footer()

    def on_mount(self) -> None:
        if not is_password_set():
            setup_password()
        self._update_focus_classes()
        self._start_sync_server()

    def on_unmount(self) -> None:
        self._stop_sync_server()

    _sync_server = None

    def _start_sync_server(self) -> None:
        server = SyncServer()
        try:
            server.start()
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                # another process (most likely the background sync daemon)
                # already owns the port and is serving the extension, which
                # is a success from the user's point of view
                self.query_one(Content).sync_running = True
            else:
                self.query_one(Content).sync_running = False
            return
        self._sync_server = server
        self.query_one(Content).sync_running = True

    def _stop_sync_server(self) -> None:
        if self._sync_server is None:
            return
        self._sync_server.stop()

    def _notify_sync(self) -> None:
        if self._sync_server is not None:
            self._sync_server.notify_change()
        else:
            # another process (the background sync daemon) owns the port -
            # ping it over its own protocol instead, since we have no
            # object to call notify_change() on directly
            threading.Thread(target=notify_external_daemon, daemon=True).start()

    def watch_focus_pane(self) -> None:
        self._update_focus_classes()

    def _update_focus_classes(self) -> None:
        self.query_one(Sidebar).set_class(self.focus_pane == "sidebar", "focused-pane")
        self.query_one(Content).set_class(self.focus_pane == "content", "focused-pane")

    def _sync_content(self) -> None:
        sidebar = self.query_one(Sidebar)
        content = self.query_one(Content)
        content.section = SECTIONS[sidebar.selected_index]
        content.site_index = 0

    def action_cursor_down(self) -> None:
        if self.focus_pane == "sidebar":
            sidebar = self.query_one(Sidebar)
            sidebar.selected_index = min(sidebar.selected_index + 1, len(SECTIONS) - 1)
            self._sync_content()
        else:
            self._move_site_cursor(1)

    def action_cursor_up(self) -> None:
        if self.focus_pane == "sidebar":
            sidebar = self.query_one(Sidebar)
            sidebar.selected_index = max(sidebar.selected_index - 1, 0)
            self._sync_content()
        else:
            self._move_site_cursor(-1)

    def _move_site_cursor(self, delta: int) -> None:
        content = self.query_one(Content)
        if content.section != "sites":
            return
        last = max(len(site_groups()) - 1, 0)
        content.site_index = min(max(content.site_index + delta, 0), last)

    def action_block_sites(self) -> None:
        content = self.query_one(Content)
        if self.focus_pane == "content" and content.section == "sites":
            if self._run_privileged(perform_block, "Blocked all sites"):
                self._notify_sync()
            self._sync_content()

    def action_focus_content(self) -> None:
        if self.focus_pane == "content":
            self._toggle_selected_site()
        else:
            self.focus_pane = "content"

    def _toggle_selected_site(self) -> None:
        content = self.query_one(Content)
        if content.section != "sites":
            return
        groups = site_groups()
        if not groups:
            return
        name, members = groups[content.site_index]
        urls = [d.url for d in members]
        blocker = HostsBlocker()
        all_blocked = all(blocker.is_blocked(u) for u in urls)

        if not all_blocked:
            if self._run_privileged(lambda: blocker.block_all(urls), f"Blocked {name}"):
                self._notify_sync()
            content.refresh(layout=True)
            return

        if not is_password_set():
            if self._run_privileged(
                lambda: blocker.unblock_all(urls), f"Unlocked {name}"
            ):
                self._notify_sync()
            content.refresh(layout=True)
            return

        def handle_result(correct) -> None:
            if correct is None:
                return  # cancelled
            if correct is False:
                self.notify("Incorrect password", severity="error")
                return
            if self._run_privileged(
                lambda: blocker.unblock_all(urls), f"Unlocked {name}"
            ):
                self._notify_sync()
            content.refresh(layout=True)

        self.push_screen(UnlockModal(name, get_password()), handle_result)

    def action_focus_sidebar(self) -> None:
        self.focus_pane = "sidebar"


USAGE = (
    "usage: block [install]\n"
    "  (no arguments)  launch the TUI\n"
    "  install         set up Block.app, the sync daemon, and print\n"
    "                  Chrome extension install instructions"
)


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] == "install":
            from blocker_tui.installer import install

            install()
            return
        print(USAGE)
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 1)
    BlockerApp().run()


if __name__ == "__main__":
    main()
