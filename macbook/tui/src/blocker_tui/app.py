import errno
import subprocess
import sys
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static

from blocker_tui import schedules as sched_ui
from blocker_tui.installer import scheduler_installed
from blocker_tui.schedule_editor import ScheduleEditor
from blocklib import schedule_store
from blocklib.core import HOSTS_FILE, HostsBlocker
from blocklib.domain import known_domains
from blocklib.password import get_password, is_password_set, setup_password
from blocklib.schedule import (
    PAUSED,
    EveryPlan,
    ForPlan,
    LockedError,
    ScheduleError,
)
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
    """Blocked manually or by a running schedule."""
    return bool(HostsBlocker(hosts_path).all_blocked_urls)


def read_schedules():
    """(schedules, None), or ([], why) if schedules.json can't be read."""
    try:
        return schedule_store.load(sched_ui.SCHEDULES_PATH), None
    except ScheduleError as e:
        return [], str(e)


def load_schedules() -> list:
    return read_schedules()[0]


def dashboard_text(hosts_path: Path = HOSTS_FILE, sync_running: bool = False) -> str:
    state = "BLOCKED" if get_status(hosts_path) else "not blocked"
    sync_state = f"ws://127.0.0.1:{DEFAULT_WS_PORT}" if sync_running else "NOT RUNNING"
    lines = [
        "STATUS",
        f"  state           {state}",
        f"  extension sync  {sync_state}",
        *sched_ui.dashboard_lines(load_schedules(), sched_ui.now()),
    ]
    return "\n".join(lines)


def schedules_text(schedule_id: str) -> str:
    schedules, error = read_schedules()
    return sched_ui.schedules_text(
        schedules, schedule_id, sched_ui.now(), scheduler_installed(), error
    )


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
    scheduled = HostsBlocker(hosts_path).scheduled_urls
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
        by_schedule = (
            " · blocked by a schedule"
            if any(d.url in scheduled for d in members)
            else ""
        )
        lines.append(f"{cursor} {box} {name}{by_schedule}")
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
    schedule_id: reactive[str] = reactive("", layout=True)
    sync_running: reactive[bool] = reactive(False)

    def render(self) -> str:
        if self.section == "dashboard":
            return dashboard_text(sync_running=self.sync_running)
        if self.section == "sites":
            return sites_text(self.site_index)
        if self.section == "schedule":
            return schedules_text(self.schedule_id)
        return SECTION_CONTENT[self.section]


class UnlockModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self, group_name: str, password: str, title: str = "", reason: str = ""
    ) -> None:
        super().__init__()
        self.group_name = group_name
        self.password = password
        self.title = title or f"UNLOCK {group_name.upper()}"
        self.reason = reason or "type the password below to unlock:"

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"{self.title}\n\n{self.reason}\n\n  {self.password}"),
            Input(placeholder="type the password here", id="unlock-input"),
            id="unlock-dialog",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value == self.password)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen):
    """y / n question. Dismisses with True or False."""

    BINDINGS = [
        ("y", "answer(True)", "Yes"),
        ("n", "answer(False)", "No"),
        ("escape", "answer(False)", "No"),
    ]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        yield Vertical(Static(f"{self.question}\n\n  (y) yes   (n) no"), id="dialog")

    def action_answer(self, yes: bool) -> None:
        self.dismiss(yes)


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
    ConfirmModal, ScheduleEditor {
        align: center middle;
    }
    #editor-dialog {
        width: 72;
        height: auto;
        max-height: 90%;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #editor-dialog .label {
        margin-top: 1;
        color: $text-muted;
    }
    #editor-dialog .row {
        height: auto;
    }
    #editor-dialog .row > * {
        margin-right: 1;
    }
    #editor-dialog .inline {
        width: auto;
    }
    #editor-dialog Input.time {
        width: 7;
    }
    #summary {
        margin-top: 1;
        color: $accent;
    }
    #editor-error {
        margin-top: 1;
        color: $error;
    }
    #dialog {
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
        Binding("a", "add_schedule", "Add schedule", show=False),
        Binding("t", "toggle_schedule", "On/off", show=False),
        Binding("e", "end_schedule_early", "End early", show=False),
        Binding("d", "delete_schedule", "Delete schedule", show=False),
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
        self._hosts_mtime = self._read_hosts_mtime()
        # Schedules start and end on the clock: keep the view current, and
        # tell the extension when the root helper rewrites /etc/hosts.
        self.set_interval(5, self._tick)

    @staticmethod
    def _read_hosts_mtime():
        try:
            return HOSTS_FILE.stat().st_mtime_ns
        except OSError:
            return None

    def _tick(self) -> None:
        if self.query_one(Content).section == "schedule":
            self._snap_schedule_cursor()
        self.query_one(Content).refresh(layout=True)
        mtime = self._read_hosts_mtime()
        if mtime != self._hosts_mtime:
            self._hosts_mtime = mtime
            if self._sync_server is not None:
                self._sync_server.notify_change()

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
        content.schedule_id = ""
        if content.section == "schedule":
            self._snap_schedule_cursor()

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
        if content.section == "schedule":
            ids = sched_ui.row_ids(load_schedules(), sched_ui.now())
            content.schedule_id = sched_ui.moved(ids, content.schedule_id, delta)
            return
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
            if self.query_one(Content).section == "schedule":
                self._edit_selected_schedule()
            else:
                self._toggle_selected_site()
        else:
            self.focus_pane = "content"

    # Schedules
    #
    # The selection is a schedule id, not a row number: rows come and go as
    # one-off blocks finish, and a keypress must act on the schedule that was
    # highlighted. Every change re-reads the file when it saves (see
    # schedule_store.update), so nothing written meanwhile is lost.

    def _in_schedules(self) -> bool:
        return (
            self.focus_pane == "content"
            and self.query_one(Content).section == "schedule"
        )

    def _snap_schedule_cursor(self) -> bool:
        """Keeps the selection on a row that's shown. False if it moved."""
        content = self.query_one(Content)
        ids = sched_ui.row_ids(load_schedules(), sched_ui.now())
        if content.schedule_id in ids or (not ids and not content.schedule_id):
            return True
        content.schedule_id = ids[0] if ids else ""
        return False

    def _selected_schedule(self):
        """The highlighted schedule as stored now, or None (saying why) if
        it has gone from the list."""
        content = self.query_one(Content)
        current = sched_ui.now()
        for s in sched_ui.shown(load_schedules(), current):
            if s.id == content.schedule_id:
                return s
        if content.schedule_id:
            self._snap_schedule_cursor()
            self.notify("that schedule has finished; check what's selected.")
        return None

    def _ask_password(self, title: str, reason: str, then) -> None:
        """Shows the unlock password; calls then() once it's typed right."""

        def handle(correct) -> None:
            if correct is None:
                return
            if correct is False:
                self.notify("that password didn't match.", severity="error")
                return
            then()

        if not is_password_set():
            setup_password()
        self.push_screen(UnlockModal("", get_password(), title, reason), handle)

    def _change_schedules(self, change, done: str) -> None:
        """Applies change (list -> list) to the stored schedules. If that
        would weaken a running schedule, asks for the password and tries
        again with it."""

        def write(password_ok: bool) -> None:
            schedule_store.update(
                change, password_ok, sched_ui.now(), sched_ui.SCHEDULES_PATH
            )

        try:
            write(False)
        except LockedError as e:
            self._ask_password(
                f"{e.name.upper()} IS RUNNING",
                "changing a running schedule needs the unlock password:",
                lambda: self._finish_change(lambda: write(True), done),
            )
            return
        except (OSError, ScheduleError) as e:
            self.notify(f"couldn't save: {e}", severity="error", timeout=6)
            return
        self._after_schedule_change(done)

    def _finish_change(self, write, done: str) -> None:
        try:
            write()
        except (OSError, ScheduleError) as e:
            self.notify(f"couldn't save: {e}", severity="error", timeout=6)
            return
        self._after_schedule_change(done)

    def _after_schedule_change(self, message: str) -> None:
        self.notify(message)
        self._snap_schedule_cursor()
        self.query_one(Content).refresh(layout=True)

    def action_toggle_schedule(self) -> None:
        if not self._in_schedules():
            return
        s = self._selected_schedule()
        if s is None:
            return
        if isinstance(s.plan, ForPlan):
            self.notify("one-off blocks just run out; (e) ends one early.")
            return
        on = not s.enabled

        def change(stored):
            return [replace(x, enabled=on) if x.id == s.id else x for x in stored]

        self._change_schedules(change, f"{s.name} turned {'on' if on else 'off'}.")

    def _edit_selected_schedule(self) -> None:
        s = self._selected_schedule()
        if s is None:
            return
        if isinstance(s.plan, ForPlan):
            self.notify("one-off blocks can't be edited; (e) ends one early.")
            return

        def saved(edited) -> None:
            if edited is None:
                return

            def change(stored):
                if not any(x.id == edited.id for x in stored):
                    return [*stored, edited]  # deleted meanwhile: keep the edit
                return [edited if x.id == edited.id else x for x in stored]

            self._change_schedules(change, f"saved {edited.name}.")

        self.push_screen(ScheduleEditor(s), saved)

    def action_add_schedule(self) -> None:
        if not self._in_schedules():
            return

        def add(new) -> None:
            if new is None:
                return
            self._change_schedules(lambda stored: [*stored, new], f"added {new.name}.")
            if new.id in sched_ui.row_ids(load_schedules(), sched_ui.now()):
                self.query_one(Content).schedule_id = new.id

        self.push_screen(ScheduleEditor(), add)

    def action_end_schedule_early(self) -> None:
        if not self._in_schedules():
            return
        s = self._selected_schedule()
        if s is None:
            return
        if not s.is_active(sched_ui.now()):
            self.notify(f"{s.name} isn't running.")
            return

        def end() -> None:
            try:
                result = schedule_store.end_early(
                    s.id, True, sched_ui.now(), sched_ui.SCHEDULES_PATH
                )
            except (OSError, ScheduleError) as e:
                self.notify(f"couldn't end it: {e}", severity="error", timeout=6)
                return
            if result == PAUSED:
                self._after_schedule_change(f"{s.name} ended early.")
            else:
                self._after_schedule_change(f"{s.name} had already finished.")

        reason = (
            "this ends it until next time; it comes back as scheduled."
            if isinstance(s.plan, EveryPlan)
            else "this ends the block now."
        )
        self._ask_password(f"END {s.name.upper()} EARLY", reason, end)

    def action_delete_schedule(self) -> None:
        if not self._in_schedules():
            return
        s = self._selected_schedule()
        if s is None:
            return

        def confirmed(yes: bool) -> None:
            # A running one then also asks for the password.
            if yes:
                self._change_schedules(
                    lambda stored: [x for x in stored if x.id != s.id],
                    f"deleted {s.name}.",
                )

        self.push_screen(ConfirmModal(f"delete {s.name}?"), confirmed)

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
    "usage: block [install | uninstall-scheduler]\n"
    "  (no arguments)       launch the TUI\n"
    "  install              set up Block.app, the sync daemon, the schedule\n"
    "                       helper, and print Chrome extension instructions\n"
    "  uninstall-scheduler  remove the schedule helper and its blocks"
)


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] == "install":
            from blocker_tui.installer import install

            install()
            return
        if sys.argv[1] == "uninstall-scheduler":
            from blocker_tui.installer import uninstall_scheduler

            try:
                uninstall_scheduler()
            except (OSError, subprocess.CalledProcessError) as e:
                print(f"Couldn't remove the schedule helper: {e}")
                sys.exit(1)
            print("Schedule helper removed")
            return
        print(USAGE)
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 1)
    BlockerApp().run()


if __name__ == "__main__":
    main()
