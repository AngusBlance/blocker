import os
import plistlib
import subprocess
import tempfile
import time
from pathlib import Path
from textwrap import dedent

import blocklib
from blocklib.schedule_store import SCHEDULES_FILE

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# the daemon's own declared entry point (blocklib's [project.scripts]), not
# a hand-rolled `python -m` invocation - same as Block.app calling `block`
# rather than reaching around it with a raw interpreter command
VENV_BLOCKER_SYNC = REPO_ROOT / ".venv" / "bin" / "blocker-sync"
# The loadable extension; extension/ itself also holds its lint tooling.
EXTENSION_DIR = REPO_ROOT / "extension" / "src"

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


def install_block_app() -> Path:
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


# The schedule helper runs as root (it writes /etc/hosts when schedules start
# and end, with nobody there to type a password), so it runs from root-owned
# copies of its files, never from the user-writable repo, with an interpreter
# only root can change.
SCHEDULER_LABEL = "com.angusblance.blocker-scheduler"
SCHEDULER_DIR = Path("/Library/Application Support/Blocker")
SCHEDULER_PLIST = Path("/Library/LaunchDaemons") / f"{SCHEDULER_LABEL}.plist"
SCHEDULER_FILES = ("schedule.py", "schedule_helper.py")
SCHEDULER_LOG = Path("/Library/Logs/blocker-scheduler.log")
NEWSYSLOG_CONF = Path("/etc/newsyslog.d") / f"{SCHEDULER_LABEL}.conf"
BLOCKLIB_DIR = Path(blocklib.__file__).resolve().parent
# Not /usr/bin/python3: that shim runs whatever `xcode-select -p` points at,
# which can be an Xcode.app in the user-writable /Applications.
CLT_PYTHON = Path("/Library/Developer/CommandLineTools/usr/bin/python3")


def _root_only(path: Path) -> bool:
    """`path` and every folder above it are owned by root and writable by
    no one else."""
    for p in [path, *path.parents]:
        info = p.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            return False
    return True


def resolve_scheduler_python(candidate: Path = CLT_PYTHON) -> str:
    """The Command Line Tools' python, resolved to its real file, checked to
    be root-only along with its standard library, and able to run the
    helper. Raises RuntimeError otherwise."""
    if not candidate.exists():
        raise RuntimeError(
            "schedules need Apple's Command Line Tools: run `xcode-select --install`"
        )
    python = Path(os.path.realpath(candidate))
    result = subprocess.run(
        [str(python), "-I", "-c", "import sys, zoneinfo; print(sys.prefix)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{python} can't run the schedule helper")
    stdlib = Path(result.stdout.strip()) / "lib"
    for p in (python, stdlib):
        if not _root_only(p):
            raise RuntimeError(f"{p} isn't root-only; not running it as root")
    return str(python)


def allowlist_text() -> str:
    """The only hostnames the root helper will ever write: the known sites."""
    from blocklib.domain import known_domains
    from blocklib.schedule_helper import with_www

    return "\n".join(sorted(with_www(d.url for d in known_domains()))) + "\n"


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
            "WatchPaths": [str(SCHEDULES_FILE.parent)],
            "StandardOutPath": str(SCHEDULER_LOG),
            "StandardErrorPath": str(SCHEDULER_LOG),
        }
    )


# Rotate at 1 MB, keep 3 compressed.
NEWSYSLOG_LINE = f"{SCHEDULER_LOG}\troot:wheel\t644\t3\t1024\t*\tJ\n"


def scheduler_installed() -> bool:
    return SCHEDULER_PLIST.exists()


def _sudo(*cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["sudo", *cmd], check=check, capture_output=not check)


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
    """Removes scheduled blocks from /etc/hosts, then the helper itself."""
    if (SCHEDULER_DIR / "schedule_helper.py").exists():
        python = resolve_scheduler_python()
        _sudo(
            python,
            "-I",
            str(SCHEDULER_DIR / "schedule_helper.py"),
            "--clear",
            check=False,
        )
    _sudo("launchctl", "bootout", f"system/{SCHEDULER_LABEL}", check=False)
    _sudo("rm", "-rf", str(SCHEDULER_DIR), str(SCHEDULER_PLIST), str(NEWSYSLOG_CONF))


def print_extension_instructions() -> None:
    print("\nChrome extension (one-time, manual step - Chrome requires this,")
    print("it won't let anything load an unpacked extension silently):")
    print(
        "  1. In the chrome://extensions tab that just opened, enable 'Developer mode'"
    )
    print("  2. Click 'Load unpacked' and select:")
    print(f"     {EXTENSION_DIR}")
    if not os.environ.get("BLOCKER_NO_OPEN_CHROME"):
        subprocess.run(
            ["open", "-a", "Google Chrome", "chrome://extensions"], check=False
        )


def install() -> None:
    bundle = install_block_app()
    print(f"Installed {bundle}")
    install_sync_daemon()
    print(f"Sync daemon installed and running ({LAUNCH_AGENT_LABEL})")
    if not os.environ.get("BLOCKER_NO_SCHEDULER"):
        print("\nSchedules need a small helper that runs as root, so sudo will")
        print("ask for your Mac password (once):")
        try:
            install_scheduler()
        except RuntimeError as e:
            print(f"Schedule helper NOT installed: {e}")
        else:
            print(f"Schedule helper installed and running ({SCHEDULER_LABEL})")
    print_extension_instructions()


if __name__ == "__main__":
    install()
