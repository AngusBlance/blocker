"""`block install` on Linux (built on Ubuntu): a .desktop entry, a systemd
user service for the sync daemon and system units for the schedule helper
(see installer.py)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

from blocker_tui.installer import (
    BLOCKLIB_DIR,
    REPO_ROOT,
    SCHEDULER_FILES,
    VENV_BLOCKER_SYNC,
    _sudo,
    allowlist_text,
    resolve_root_python,
)
from blocklib.schedule_store import SCHEDULES_FILE


def _xdg_dir(variable: str, default: str) -> Path:
    return Path(os.environ.get(variable) or Path.home() / default)


DESKTOP_ENTRY = (
    _xdg_dir("XDG_DATA_HOME", ".local/share") / "applications" / "block.desktop"
)

# overridable so integration tests can start a disposable, self-cleaning
# service instead of touching the real blocker-sync
SYNC_UNIT = os.environ.get("BLOCKER_SYNC_UNIT", "blocker-sync")
SYNC_NAME = f"{SYNC_UNIT}.service"
USER_UNIT_DIR = _xdg_dir("XDG_CONFIG_HOME", ".config") / "systemd" / "user"
SYNC_UNIT_FILE = USER_UNIT_DIR / SYNC_NAME

SCHEDULER_UNIT = "blocker-scheduler"
SCHEDULER_NAME = f"{SCHEDULER_UNIT}.timer"
SCHEDULER_DIR = Path("/usr/local/lib/blocker")
SYSTEM_UNIT_DIR = Path("/etc/systemd/system")
# The service runs the helper once; the timer and the path unit say when.
SCHEDULER_UNITS = tuple(
    f"{SCHEDULER_UNIT}.{kind}" for kind in ("service", "timer", "path")
)
# What starts the service; the service itself isn't enabled.
SCHEDULER_TRIGGERS = SCHEDULER_UNITS[1:]
SYSTEM_PYTHON = Path("/usr/bin/python3")


def _unit_escape(value: str) -> str:
    """`value` safe in a unit file setting: systemd expands % specifiers."""
    return value.replace("%", "%%")


def _exec_arg(value: str) -> str:
    """One quoted ExecStart= argument (also immune to $ expansion)."""
    quoted = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    return f'"{_unit_escape(quoted)}"'


def _desktop_exec_arg(value: str) -> str:
    """One quoted argument of a .desktop Exec= key."""
    for c in ("\\", '"', "`", "$"):
        value = value.replace(c, "\\" + c)
    return '"' + value.replace("%", "%%") + '"'


def desktop_entry() -> str:
    # The full path: the app menu's PATH needn't hold ~/.local/bin.
    block = shutil.which("block") or "block"
    return dedent(f"""\
        [Desktop Entry]
        Type=Application
        Name=Block
        Comment=Block distracting sites
        Exec={_desktop_exec_arg(block)}
        Icon=security-high
        Terminal=true
        Categories=Utility;
        """)


def install_launcher() -> Path:
    """Puts Block in the app menu. Its only job is opening a terminal that
    runs the installed `block` command - no hardcoded repo paths."""
    DESKTOP_ENTRY.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_ENTRY.write_text(desktop_entry())
    return DESKTOP_ENTRY


def _sync_unit() -> str:
    return dedent(f"""\
        [Unit]
        Description=Blocker: keeps the Chrome extension in sync

        [Service]
        ExecStart={_exec_arg(str(VENV_BLOCKER_SYNC))}
        WorkingDirectory={_unit_escape(str(REPO_ROOT))}
        Restart=always
        RestartSec=10

        [Install]
        WantedBy=default.target
        """)


def _systemctl_user(*args: str) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


def install_sync_daemon() -> None:
    """Writes the user service and (re)starts it so the sync daemon runs now
    and on every future login. Its output goes to the journal
    (`journalctl --user -u blocker-sync`)."""
    SYNC_UNIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_UNIT_FILE.write_text(_sync_unit())
    _systemctl_user("daemon-reload")
    _systemctl_user("enable", SYNC_NAME)
    # restart, not start: an install after a code update runs the new code
    _systemctl_user("restart", SYNC_NAME)


def resolve_scheduler_python(candidate: Path = SYSTEM_PYTHON) -> str:
    """The system's python, if it's safe to run as root (see
    installer.resolve_root_python)."""
    return resolve_root_python(
        candidate, "schedules need python3: run `sudo apt install python3`"
    )


def _scheduler_service(python: str) -> str:
    args = [python, "-I", str(SCHEDULER_DIR / "schedule_helper.py")]
    args.append(str(SCHEDULES_FILE))
    return dedent(f"""\
        [Unit]
        Description=Blocker: apply schedules to /etc/hosts
        # Saving schedules can start it a few times a second; never refuse.
        StartLimitIntervalSec=0

        [Service]
        Type=oneshot
        ExecStart={" ".join(_exec_arg(a) for a in args)}
        """)


# Schedules start and end on the clock, at most 30s late (every minute's :00
# and :30, so on time for schedules set to the minute).
SCHEDULER_TIMER = dedent("""\
    [Unit]
    Description=Blocker: start and end schedules on time

    [Timer]
    OnCalendar=*:*:00/30
    AccuracySec=1s

    [Install]
    WantedBy=timers.target
    """)


def _scheduler_path_unit() -> str:
    # A saved change is picked up through the folder (saves replace the
    # file); /etc/hosts too, so if a manual block's write lands on top of a
    # change of ours, the scheduled section goes back straight away.
    return dedent(f"""\
        [Unit]
        Description=Blocker: apply schedule changes straight away

        [Path]
        PathChanged={_unit_escape(str(SCHEDULES_FILE.parent))}
        PathChanged=/etc/hosts

        [Install]
        WantedBy=paths.target
        """)


def scheduler_installed() -> bool:
    return (SYSTEM_UNIT_DIR / SCHEDULER_UNITS[0]).exists()


def install_scheduler() -> None:
    """Copies the helper into a fresh SCHEDULER_DIR and starts its systemd
    units. Needs sudo, which asks for your password once. Its output goes to
    the journal (`journalctl -u blocker-scheduler`)."""
    python = resolve_scheduler_python()
    SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)

    root_owned = ("-o", "root", "-g", "root", "-m", "644")
    with tempfile.TemporaryDirectory() as tmp:
        files = {
            f"{SCHEDULER_UNIT}.service": _scheduler_service(python),
            f"{SCHEDULER_UNIT}.timer": SCHEDULER_TIMER,
            f"{SCHEDULER_UNIT}.path": _scheduler_path_unit(),
            "allowed-domains.txt": allowlist_text(),
        }
        for name, text in files.items():
            (Path(tmp) / name).write_text(text)
        # Stopped first, so nothing runs the helper while it's replaced.
        _sudo("systemctl", "stop", *SCHEDULER_TRIGGERS, check=False)
        # Start from an empty folder: nothing stale sits beside the helper.
        _sudo("rm", "-rf", str(SCHEDULER_DIR))
        _sudo(
            "install", "-d", "-o", "root", "-g", "root", "-m", "755", str(SCHEDULER_DIR)
        )
        for name in SCHEDULER_FILES:
            _sudo(
                "install",
                *root_owned,
                str(BLOCKLIB_DIR / name),
                str(SCHEDULER_DIR / name),
            )
        _sudo(
            "install",
            *root_owned,
            str(Path(tmp) / "allowed-domains.txt"),
            str(SCHEDULER_DIR / "allowed-domains.txt"),
        )
        for name in SCHEDULER_UNITS:
            _sudo(
                "install",
                *root_owned,
                str(Path(tmp) / name),
                str(SYSTEM_UNIT_DIR / name),
            )
    _sudo("systemctl", "daemon-reload")
    _sudo("systemctl", "enable", "--now", *SCHEDULER_TRIGGERS)
    # Once now, so anything already running blocks straight away.
    result = _sudo("systemctl", "start", SCHEDULER_UNITS[0], check=False)
    if result.returncode != 0:
        why = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"the schedule helper failed: {why}")


def uninstall_scheduler() -> None:
    """Stops the helper, removes its blocks from /etc/hosts, then removes
    the helper. Stopped first, so it can't put the blocks back."""
    _sudo("systemctl", "disable", "--now", *SCHEDULER_TRIGGERS, check=False)
    _sudo("systemctl", "stop", SCHEDULER_UNITS[0], check=False)
    helper = SCHEDULER_DIR / "schedule_helper.py"
    if helper.exists():
        try:
            python = resolve_scheduler_python()
        except RuntimeError as e:
            print(f"Couldn't clear scheduled blocks from /etc/hosts ({e});")
            print("remove its BLOCKER-SCHEDULE section by hand.")
        else:
            result = _sudo(python, "-I", str(helper), "--clear", check=False)
            if result.returncode != 0:
                why = (result.stderr or b"").decode(errors="replace").strip()
                print(f"Couldn't clear scheduled blocks from /etc/hosts: {why}")
    units = [str(SYSTEM_UNIT_DIR / name) for name in SCHEDULER_UNITS]
    _sudo("rm", "-rf", str(SCHEDULER_DIR), *units)
    _sudo("systemctl", "daemon-reload", check=False)


CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def open_chrome_extensions() -> bool:
    chrome = next((c for c in map(shutil.which, CHROMES) if c), None)
    if chrome is None:
        return False
    # Not waited on: with no Chrome open yet, this one is Chrome.
    subprocess.Popen(
        [chrome, "chrome://extensions"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True
