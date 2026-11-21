"""Focus mode's apps on Linux: while focus is on, apps it doesn't allow are
closed. Runs as the user (systemd user service `blocker-focus-apps`, set up
by `block install`), never on the Mac.

How it tells apps apart: GNOME (and Chrome and Electron apps, and snapd and
Flatpak) start every app in its own systemd unit named after its desktop
ID - `app-gnome-org.gnome.TextEditor-4242.scope`, `snap.obsidian.obsidian-
<uuid>.scope`. So once a second it reads /proc for the units the user's
processes are in, turns each name back into a desktop ID, and stops the
units of apps that aren't allowed (`systemctl --user stop`, which closes the
app as a logout would). Wayland doesn't let one app see another's windows,
so this works from processes, not windows.

What it never closes, so focus can't break the desktop or lose work:
- units with no app in the menu behind them (services, helpers, anything
  it can't name);
- anything started from a terminal (a unit whose first process - the one
  started into it from outside - has a controlling tty), such as an editor
  in a terminal tab, whatever helpers it starts - and terminal apps
  themselves. An app with a terminal inside it (VS Code's) isn't spared:
  only the shell it starts has the tty;
- Chrome and Chromium, and the web apps installed from them, where the
  extension filters sites instead, and Block itself.
Apps set to start at login (a tablet driver, a dictation tool) aren't
spared here; the TUI ticks them in the allow list, to untick if wanted.
Other browsers can't be allowed: the extension only works in Chrome, so
they'd be a way round focus.

It's a commitment device, like the rest of Block: `systemctl --user stop
blocker-focus-apps` turns it off.
"""

import contextlib
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from . import focus as focus_mode

POLL_SECONDS = 1.0
# The installed apps barely change; reread them now and then, not every poll.
APPS_REFRESH_SECONDS = 30.0
# One notification per app this often, however often it's reopened.
NOTIFY_EVERY_SECONDS = 30.0

# Chrome is filtered by the extension instead; Block is how focus is run.
ALWAYS_ALLOWED = frozenset(
    {
        "block",
        "google-chrome",
        "google-chrome-stable",
        "google-chrome-beta",
        "google-chrome-unstable",
        "com.google.Chrome",
        "chromium",
        "chromium-browser",
        "chromium_chromium",
        "org.chromium.Chromium",
    }
)
# Web apps installed from Chrome or Chromium ("Install page as app"):
# chrome-<32-letter app id>-<profile>. They're Chrome windows, filtered by
# the extension, and Chrome itself can start inside one's unit.
_CHROME_WEB_APP = re.compile(r"^(chrome|chromium|google-chrome)-[a-p]{32}-")
# Terminals whose entries don't all say Categories=TerminalEmulator.
TERMINALS = frozenset(
    {
        "alacritty",
        "Alacritty",
        "kitty",
        "foot",
        "org.gnome.Terminal",
        "org.gnome.Ptyxis",
        "org.gnome.Console",
        "com.mitchellh.ghostty",
        "org.wezfurlong.wezterm",
        "org.kde.konsole",
        "com.gexperts.Tilix",
        "xterm",
    }
)


@dataclass(frozen=True)
class App:
    id: str  # desktop ID: the .desktop file's name without .desktop
    name: str
    terminal: bool = False
    browser: bool = False


# Finding the installed apps


def _env_dirs(env: Mapping[str, str], var: str, default: str) -> List[Path]:
    return [Path(d) for d in (env.get(var) or default).split(":") if d]


# Flatpak's and snapd's, in case the session didn't add them to
# XDG_DATA_DIRS (a user service's environment can lack them).
EXTRA_DATA_DIRS = (
    Path("/var/lib/flatpak/exports/share"),
    Path("/var/lib/snapd/desktop"),
)


def application_dirs(env: Mapping[str, str] = os.environ) -> List[Path]:
    """Where .desktop files live, most important first (the XDG order), plus
    Flatpak's and snapd's."""
    home = Path(env.get("HOME") or Path.home())
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    dirs = [
        data_home,
        *_env_dirs(env, "XDG_DATA_DIRS", "/usr/local/share:/usr/share"),
        data_home / "flatpak/exports/share",
        *EXTRA_DATA_DIRS,
    ]
    seen: List[Path] = []
    for d in dirs:
        if d / "applications" not in seen:
            seen.append(d / "applications")
    return seen


def autostart_dirs(env: Mapping[str, str] = os.environ) -> List[Path]:
    home = Path(env.get("HOME") or Path.home())
    config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    return [
        config_home / "autostart",
        *(d / "autostart" for d in _env_dirs(env, "XDG_CONFIG_DIRS", "/etc/xdg")),
    ]


def parse_desktop_entry(text: str) -> Dict[str, str]:
    """The [Desktop Entry] group's untranslated keys."""
    entry: Dict[str, str] = {}
    group = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
            continue
        if group != "Desktop Entry" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if "[" not in key:  # Name[fr]= and the like
            entry.setdefault(key, value.strip())
    return entry


def _entries(dirs: Iterable[Path]) -> Iterable[Tuple[str, Dict[str, str]]]:
    """(desktop ID, entry) for each .desktop file, the first of each ID
    only: one earlier in the list hides (overrides) later ones."""
    seen: Set[str] = set()
    for d in dirs:
        try:
            files = sorted(d.rglob("*.desktop"))
        except OSError:
            continue
        for path in files:
            # The spec's desktop ID: subfolders joined with "-".
            app_id = "-".join(path.relative_to(d).with_suffix("").parts)
            if app_id in seen:
                continue
            seen.add(app_id)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            yield app_id, parse_desktop_entry(text)


def _true(entry: Dict[str, str], key: str) -> bool:
    return entry.get(key, "").lower() == "true"


def installed_apps(dirs: Iterable[Path]) -> Dict[str, App]:
    """The apps in the menu, by desktop ID."""
    apps: Dict[str, App] = {}
    for app_id, entry in _entries(dirs):
        if entry.get("Type") != "Application" or not entry.get("Name"):
            continue
        if _true(entry, "NoDisplay") or _true(entry, "Hidden"):
            continue
        categories = set(entry.get("Categories", "").split(";"))
        apps[app_id] = App(
            app_id,
            entry["Name"],
            terminal="TerminalEmulator" in categories or app_id in TERMINALS,
            browser="WebBrowser" in categories,
        )
    return apps


def current_desktops(env: Mapping[str, str] = os.environ) -> Set[str]:
    """XDG_CURRENT_DESKTOP's names, e.g. {"ubuntu", "GNOME"}."""
    return {d for d in env.get("XDG_CURRENT_DESKTOP", "").split(":") if d}


def _shown_here(entry: Dict[str, str], desktops: Set[str]) -> bool:
    only = {d for d in entry.get("OnlyShowIn", "").split(";") if d}
    never = {d for d in entry.get("NotShowIn", "").split(";") if d}
    return (not only or bool(only & desktops)) and not never & desktops


def autostart_ids(dirs: Iterable[Path], desktops: Iterable[str] = ()) -> Set[str]:
    """Desktop IDs started at login on this desktop (and not switched off)."""
    desktops = set(desktops)
    return {
        app_id
        for app_id, entry in _entries(dirs)
        if not _true(entry, "Hidden")
        and entry.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
        and _shown_here(entry, desktops)
    }


def choosable(apps: Dict[str, App]) -> List[App]:
    """The apps worth offering in the TUI: not ones that are always allowed,
    and not other browsers (they can't be)."""
    found: Dict[str, App] = {}
    for a in apps.values():
        # The same app under two cases (Beeper.desktop, beeper.desktop)
        # is one choice: allowing either allows both (see find_app).
        if not always_allowed(a) and not a.browser:
            found.setdefault(a.id.lower(), a)
    return sorted(found.values(), key=lambda a: a.name.lower())


def at_login(choices: List[App], autostart: Set[str]) -> List[App]:
    """Of `choices`, the ones that start at login: the TUI ticks them, so a
    tablet driver isn't closed unless someone unticks it."""
    starts = {a.lower() for a in autostart}
    return [a for a in choices if a.id.lower() in starts]


def always_allowed(app: App) -> bool:
    return (
        app.id in ALWAYS_ALLOWED or app.terminal or bool(_CHROME_WEB_APP.match(app.id))
    )


# From units to apps

_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")
# snap.<snap>.<app>-<uuid>.scope
_SNAP = re.compile(
    r"^snap\.([^.]+)\.([^.]+)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\.scope$"
)


def _unescape(name: str) -> str:
    return _ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), name)


def unit_app_id(unit: str) -> Optional[str]:
    """The desktop ID a unit was started for, or None if it isn't an app's.

    systemd's naming for apps: `app[-<launcher>]-<ID>-<random>.scope` and
    `app[-<launcher>]-<ID>[@<random>].service`, with "-" inside the ID
    escaped as \\x2d, so the dashes split it cleanly. Snaps use
    `snap.<snap>.<app>-<uuid>.scope`, whose desktop ID is <snap>_<app>.
    """
    snap = _SNAP.match(unit)
    if snap:
        return f"{snap.group(1)}_{snap.group(2)}"
    if not unit.startswith("app-"):
        return None
    if unit.endswith(".scope"):
        parts = unit[len("app-") : -len(".scope")].split("-")
        if len(parts) < 2:
            return None
        parts = parts[:-1]  # the random part
    elif unit.endswith(".service"):
        parts = unit[len("app-") : -len(".service")].split("@")[0].split("-")
    else:
        return None
    if len(parts) > 2 or not parts[-1]:
        return None
    return _unescape(parts[-1])  # parts[0] is the launcher, if there are two


def by_lower_id(apps: Dict[str, App]) -> Dict[str, App]:
    """For find_app: built once, not per unit."""
    index: Dict[str, App] = {}
    for app_id, app in sorted(apps.items()):
        index.setdefault(app_id.lower(), app)
    return index


def find_app(
    apps: Dict[str, App], app_id: str, index: Optional[Dict[str, App]] = None
) -> Optional[App]:
    """Desktop IDs are case-sensitive, but apps don't always name their own
    units the same case as their entry (Beeper.desktop, app-beeper-1.scope)."""
    if app_id in apps:
        return apps[app_id]
    return (by_lower_id(apps) if index is None else index).get(app_id.lower())


# Reading /proc


def _unit_of(cgroup_text: str, uid: int) -> Optional[str]:
    """The user-manager unit in a /proc/<pid>/cgroup (cgroup v2), or None."""
    marker = f"/user@{uid}.service/"
    for line in cgroup_text.splitlines():
        if not line.startswith("0::"):
            continue
        path = line[3:]
        if marker not in path:
            return None
        # The last unit on the path: an app can make cgroups of its own
        # inside its unit.
        parts = path.split(marker, 1)[1].split("/")
        units = [p for p in parts if p.endswith((".scope", ".service"))]
        return units[-1] if units else None
    return None


def _parent_and_tty(stat_text: str) -> Tuple[int, bool]:
    """From /proc/<pid>/stat: the parent's pid, and whether the process has a
    controlling terminal. The command name can hold spaces and brackets, so
    split after its last ")": state, ppid, pgrp, session, tty_nr."""
    fields = stat_text[stat_text.rfind(")") + 1 :].split()
    if len(fields) < 5:
        return 0, False
    return int(fields[1]), fields[4] != "0"


def running_units(
    proc: Path = Path("/proc"), uid: Optional[int] = None
) -> Dict[str, bool]:
    """The user's units with processes in them, and whether each was started
    from a terminal: whether a process whose parent is outside the unit (the
    one it was started with) has a tty. nvim run in a terminal was, though
    its server and language servers have no tty; VS Code wasn't, though the
    shell in its terminal tab has one."""
    uid = os.getuid() if uid is None else uid
    found: Dict[str, Dict[int, Tuple[int, bool]]] = {}
    try:
        pids = [p for p in proc.iterdir() if p.name.isdigit()]
    except OSError:
        return {}
    for pid in pids:
        try:
            unit = _unit_of((pid / "cgroup").read_text(), uid)
            if unit is None:
                continue
            parent_tty = _parent_and_tty((pid / "stat").read_text())
        except (OSError, ValueError):  # it exited while we looked
            continue
        found.setdefault(unit, {})[int(pid.name)] = parent_tty
    return {
        unit: any(tty for parent, tty in procs.values() if parent not in procs)
        for unit, procs in found.items()
    }


# Deciding


def to_close(
    units: Dict[str, bool],
    apps: Dict[str, App],
    allowed: Iterable[str],
) -> List[Tuple[str, App]]:
    """(unit, app) for every running app focus doesn't allow."""
    allowed_lower = {a.lower() for a in allowed}
    index = by_lower_id(apps)
    closing = []
    for unit, in_terminal in sorted(units.items()):
        if in_terminal:
            continue
        app_id = unit_app_id(unit)
        app = None if app_id is None else find_app(apps, app_id, index)
        if app is None or always_allowed(app):
            continue
        if app.id.lower() in allowed_lower and not app.browser:
            continue
        closing.append((unit, app))
    return closing


# Doing


def stop_unit(unit: str) -> None:
    # --no-block: an app slow to quit mustn't hold up the next look.
    subprocess.run(
        ["systemctl", "--user", "stop", "--no-block", unit],
        check=False,
        capture_output=True,
    )


def notify(app: App, ends_at: int) -> None:
    until = datetime.fromtimestamp(ends_at / 1000).strftime("%H:%M")
    with contextlib.suppress(OSError):
        subprocess.run(
            [
                "notify-send",
                "--app-name=Block",
                "--icon=security-high",
                f"{app.name} is closed during focus",
                f"Focus is on until {until}.",
            ],
            check=False,
            capture_output=True,
        )


class Enforcer:
    def __init__(
        self,
        focus_file: Path = focus_mode.FOCUS_FILE,
        proc: Path = Path("/proc"),
        env: Mapping[str, str] = os.environ,
        stop=stop_unit,
        notify=notify,
        clock=time.monotonic,
    ):
        self.focus_file = focus_file
        self.proc = proc
        self.env = env
        self.stop = stop
        self.notify = notify
        self.clock = clock
        self._apps: Dict[str, App] = {}
        self._apps_read_at: Optional[float] = None
        self._notified: Dict[str, float] = {}

    def _refresh_apps(self) -> None:
        now = self.clock()
        if (
            self._apps_read_at is None
            or now - self._apps_read_at >= APPS_REFRESH_SECONDS
        ):
            self._apps = installed_apps(application_dirs(self.env))
            self._apps_read_at = now

    def check(self, now_ms: Optional[int] = None) -> List[Tuple[str, App]]:
        """One look: closes what focus doesn't allow, if it's on."""
        current = focus_mode.load(self.focus_file, now_ms)
        if current is None:
            # Read the apps afresh when the next focus starts.
            self._apps_read_at = None
            return []
        self._refresh_apps()
        closing = to_close(
            running_units(self.proc),
            self._apps,
            [a.id for a in current.apps],
        )
        for unit, app in closing:
            self.stop(unit)
            last = self._notified.get(app.id)
            if last is None or self.clock() - last >= NOTIFY_EVERY_SECONDS:
                self._notified[app.id] = self.clock()
                self.notify(app, current.ends_at)
        return closing


def run(enforcer: Enforcer, stop: threading.Event, poll: float = POLL_SECONDS) -> None:
    while not stop.is_set():
        try:
            enforcer.check()
        except Exception as e:  # keep going: a crash would end focus early
            print(f"blocker-focus-apps: {e!r}", file=sys.stderr, flush=True)
        stop.wait(poll)


def main() -> None:
    stop = threading.Event()

    def _handle_signal(signum, frame) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    print("blocker-focus-apps starting", flush=True)
    run(Enforcer(), stop)


if __name__ == "__main__":
    main()
