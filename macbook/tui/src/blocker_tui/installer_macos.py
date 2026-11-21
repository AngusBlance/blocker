"""`block install` on macOS: Block.app, a LaunchAgent for the sync daemon
and a LaunchDaemon for the schedule helper (see installer.py)."""

import os
import plistlib
import subprocess
import tempfile
import time
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

APP_BUNDLE = Path.home() / "Applications" / "Block.app"
# overridable so integration tests can bootstrap a disposable, self-cleaning
# agent instead of touching the real com.angusblance.blocker-sync
LAUNCH_AGENT_LABEL = os.environ.get(
    "BLOCKER_LAUNCH_AGENT_LABEL", "com.angusblance.blocker-sync"
)
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)
LOGS_DIR = Path.home() / "Library" / "Logs"
SYNC_NAME = LAUNCH_AGENT_LABEL

LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/"
    "LaunchServices.framework/Versions/A/Support/lsregister"
)

INFO_PLIST = dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>CFBundleName</key>
        <string>Block</string>
        <key>CFBundleDisplayName</key>
        <string>Block</string>
        <key>CFBundleIdentifier</key>
        <string>com.angusblance.block</string>
        <key>CFBundleVersion</key>
        <string>1.0</string>
        <key>CFBundleShortVersionString</key>
        <string>1.0</string>
        <key>CFBundlePackageType</key>
        <string>APPL</string>
        <key>CFBundleExecutable</key>
        <string>block</string>
        <key>LSMinimumSystemVersion</key>
        <string>10.13</string>
    </dict>
    </plist>
    """)

LAUNCHER_SCRIPT = dedent("""\
    #!/bin/bash
    osascript <<'EOF'
    tell application "Terminal"
        activate
        do script "exec block"
    end tell
    EOF
    """)


def install_launcher() -> Path:
    """Creates/updates ~/Applications/Block.app so it's searchable in
    Spotlight/Launchpad. Its only job is opening a Terminal that runs the
    installed `block` command - no hardcoded repo paths."""
    macos_dir = APP_BUNDLE / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    (APP_BUNDLE / "Contents" / "Info.plist").write_text(INFO_PLIST)
    launcher = macos_dir / "block"
    launcher.write_text(LAUNCHER_SCRIPT)
    launcher.chmod(0o755)
    subprocess.run([LSREGISTER, "-f", str(APP_BUNDLE)], check=True)
    return APP_BUNDLE


def _sync_daemon_plist() -> str:
    return dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCH_AGENT_LABEL}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{VENV_BLOCKER_SYNC}</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{REPO_ROOT}</string>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>ThrottleInterval</key>
            <integer>10</integer>
            <key>StandardOutPath</key>
            <string>{LOGS_DIR / "blocker-sync.log"}</string>
            <key>StandardErrorPath</key>
            <string>{LOGS_DIR / "blocker-sync.err.log"}</string>
        </dict>
        </plist>
        """)


def install_sync_daemon() -> None:
    """Writes the LaunchAgent plist and (re)loads it so the sync daemon
    runs now and on every future login."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    was_already_installed = LAUNCH_AGENT_PLIST.exists()
    LAUNCH_AGENT_PLIST.write_text(_sync_daemon_plist())

    uid = os.getuid()
    if was_already_installed:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(LAUNCH_AGENT_PLIST)],
            capture_output=True,
        )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(LAUNCH_AGENT_PLIST)],
        check=True,
    )


SCHEDULER_LABEL = "com.angusblance.blocker-scheduler"
SCHEDULER_NAME = SCHEDULER_LABEL
SCHEDULER_DIR = Path("/Library/Application Support/Blocker")
SCHEDULER_PLIST = Path("/Library/LaunchDaemons") / f"{SCHEDULER_LABEL}.plist"
SCHEDULER_LOG = Path("/Library/Logs/blocker-scheduler.log")
NEWSYSLOG_CONF = Path("/etc/newsyslog.d") / f"{SCHEDULER_LABEL}.conf"
# Not /usr/bin/python3: that shim runs whatever `xcode-select -p` points at,
# which can be an Xcode.app in the user-writable /Applications.
CLT_PYTHON = Path("/Library/Developer/CommandLineTools/usr/bin/python3")


def resolve_scheduler_python(candidate: Path = CLT_PYTHON) -> str:
    """The Command Line Tools' python, if it's safe to run as root (see
    installer.resolve_root_python)."""
    return resolve_root_python(
        candidate,
        "schedules need Apple's Command Line Tools: run `xcode-select --install`",
    )


def _scheduler_plist(python: str) -> bytes:
    return plistlib.dumps(
        {
            "Label": SCHEDULER_LABEL,
            "ProgramArguments": [
                python,
                "-I",
                str(SCHEDULER_DIR / "schedule_helper.py"),
                str(SCHEDULES_FILE),
            ],
            "RunAtLoad": True,
            # Schedules start and end on the clock (so up to 30s late); a
            # saved change is picked up through the folder within launchd's
            # 10s throttle (saves replace the file).
            "StartInterval": 30,
            # Also /etc/hosts: if a manual block's write lands on top of a
            # change of ours, the scheduled section goes back straight away.
            "WatchPaths": [str(SCHEDULES_FILE.parent), "/private/etc/hosts"],
            "StandardOutPath": str(SCHEDULER_LOG),
            "StandardErrorPath": str(SCHEDULER_LOG),
        }
    )


# Rotate at 1 MB, keep 3 compressed.
NEWSYSLOG_LINE = f"{SCHEDULER_LOG}\troot:wheel\t644\t3\t1024\t*\tJ\n"


def scheduler_installed() -> bool:
    return SCHEDULER_PLIST.exists()


def install_scheduler() -> None:
    """Copies the helper into a fresh SCHEDULER_DIR and loads its
    LaunchDaemon. Needs sudo, which asks for the Mac password once."""
    python = resolve_scheduler_python()
    SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)

    root_owned = ("-o", "root", "-g", "wheel", "-m", "644")
    with tempfile.TemporaryDirectory() as tmp:
        plist = Path(tmp) / f"{SCHEDULER_LABEL}.plist"
        plist.write_bytes(_scheduler_plist(python))
        allowlist = Path(tmp) / "allowed-domains.txt"
        allowlist.write_text(allowlist_text())
        newsyslog = Path(tmp) / "newsyslog.conf"
        newsyslog.write_text(NEWSYSLOG_LINE)
        # Start from an empty folder: nothing stale sits beside the helper.
        _sudo("rm", "-rf", str(SCHEDULER_DIR))
        _sudo(
            "install",
            "-d",
            "-o",
            "root",
            "-g",
            "wheel",
            "-m",
            "755",
            str(SCHEDULER_DIR),
        )
        for name in SCHEDULER_FILES:
            _sudo(
                "install",
                *root_owned,
                str(BLOCKLIB_DIR / name),
                str(SCHEDULER_DIR / name),
            )
        _sudo(
            "install", *root_owned, str(allowlist), str(SCHEDULER_DIR / allowlist.name)
        )
        _sudo("install", *root_owned, str(newsyslog), str(NEWSYSLOG_CONF))
        _sudo("install", *root_owned, str(plist), str(SCHEDULER_PLIST))
    _sudo("launchctl", "bootout", f"system/{SCHEDULER_LABEL}", check=False)
    _sudo("launchctl", "enable", f"system/{SCHEDULER_LABEL}")
    # Straight after a bootout launchd can refuse with "Input/output error"
    # for a moment.
    for _ in range(5):
        result = _sudo(
            "launchctl", "bootstrap", "system", str(SCHEDULER_PLIST), check=False
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError(
        f"launchctl bootstrap failed: {result.stderr.decode(errors='replace').strip()}"
    )


def uninstall_scheduler() -> None:
    """Stops the helper, removes its blocks from /etc/hosts, then removes
    the helper. Stopped first, so it can't put the blocks back."""
    _sudo("launchctl", "bootout", f"system/{SCHEDULER_LABEL}", check=False)
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
    _sudo("rm", "-rf", str(SCHEDULER_DIR), str(SCHEDULER_PLIST), str(NEWSYSLOG_CONF))


def open_chrome_extensions() -> bool:
    result = subprocess.run(
        ["open", "-a", "Google Chrome", "chrome://extensions"], check=False
    )
    return result.returncode == 0
