"""`block install`: sets the desktop app up for the OS it's running on.

The steps are the same everywhere - a launcher in the app menu, the sync
daemon for the Chrome extension, the root schedule helper, then the
extension - and each OS does them its own way: installer_macos.py (launchd,
Block.app) and installer_linux.py (systemd, a .desktop entry).
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import blocklib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# the daemon's own declared entry point (blocklib's [project.scripts]), not
# a hand-rolled `python -m` invocation - same as the launcher calling `block`
# rather than reaching around it with a raw interpreter command
VENV_BLOCKER_SYNC = REPO_ROOT / ".venv" / "bin" / "blocker-sync"
# The loadable extension; extension/ itself also holds its lint tooling.
EXTENSION_DIR = REPO_ROOT / "extension" / "src"

# The schedule helper runs as root (it writes /etc/hosts when schedules start
# and end, with nobody there to type a password), so it runs from root-owned
# copies of its files, never from the user-writable repo, with an interpreter
# only root can change.
BLOCKLIB_DIR = Path(blocklib.__file__).resolve().parent
SCHEDULER_FILES = ("schedule.py", "schedule_helper.py")


class UnsupportedOS(RuntimeError):
    pass


def this_os():
    """The installer module for the OS we're running on."""
    if sys.platform == "darwin":
        from blocker_tui import installer_macos

        return installer_macos
    if sys.platform.startswith("linux"):
        from blocker_tui import installer_linux

        return installer_linux
    raise UnsupportedOS(f"block install supports macOS and Linux, not {sys.platform}")


def _root_only(path: Path) -> bool:
    """`path` and every folder above it are owned by root and writable by
    no one else."""
    for p in [path, *path.parents]:
        info = p.lstat()
        # Linux shows every symlink as 0777, but no one can rewrite one in
        # place: changing it means replacing it in its folder, checked too.
        writable = not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022
        if info.st_uid != 0 or writable:
            return False
    return True


def resolve_root_python(candidate: Path, missing: str) -> str:
    """`candidate`, once it's checked to be root-only through to its real
    file, along with its standard library, and able to run the helper.
    Raises RuntimeError (saying `missing` if there's no such file)
    otherwise."""
    if not candidate.exists():
        raise RuntimeError(missing)
    # Checked through to the real file, but the helper keeps the stable path,
    # so an update to a newer python still runs.
    python = Path(os.path.realpath(candidate))
    result = subprocess.run(
        [str(python), "-I", "-c", "import sys, zoneinfo; print(sys.prefix)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{python} can't run the schedule helper")
    stdlib = Path(result.stdout.strip()) / "lib"
    for p in (candidate, python, stdlib):
        if not _root_only(p):
            raise RuntimeError(f"{p} isn't root-only; not running it as root")
    return str(candidate)


def allowlist_text() -> str:
    """The only hostnames the root helper will ever write: the known sites."""
    from blocklib.domain import known_domains
    from blocklib.schedule_helper import with_www

    return "\n".join(sorted(with_www(d.url for d in known_domains()))) + "\n"


def _sudo(*cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["sudo", *cmd], check=check, capture_output=not check)


def scheduler_installed() -> bool:
    try:
        return this_os().scheduler_installed()
    except UnsupportedOS:
        return False


def uninstall_scheduler() -> None:
    this_os().uninstall_scheduler()


def print_extension_instructions(open_chrome) -> None:
    """`open_chrome` opens chrome://extensions, True if it could."""
    opened = not os.environ.get("BLOCKER_NO_OPEN_CHROME") and open_chrome()
    print("\nChrome extension (one-time, manual step - Chrome requires this,")
    print("it won't let anything load an unpacked extension silently):")
    if opened:
        print(
            "  1. In the chrome://extensions tab that just opened, "
            "enable 'Developer mode'"
        )
    else:
        print("  1. Open chrome://extensions in Chrome and enable 'Developer mode'")
    print("  2. Click 'Load unpacked' and select:")
    print(f"     {EXTENSION_DIR}")


def install() -> None:
    platform = this_os()
    print(f"Installed {platform.install_launcher()}")
    platform.install_sync_daemon()
    print(f"Sync daemon installed and running ({platform.SYNC_NAME})")
    # Focus closing apps is Linux only so far; the Mac's installer has none.
    install_focus_apps = getattr(platform, "install_focus_apps", None)
    if install_focus_apps is not None:
        try:
            install_focus_apps()
        except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
            print(f"Focus app closer NOT installed (focus won't close apps): {e}")
        else:
            print(
                f"Focus app closer installed and running ({platform.FOCUS_APPS_NAME})"
            )
    if not os.environ.get("BLOCKER_NO_SCHEDULER"):
        print("\nSchedules need a small helper that runs as root, so sudo will")
        print("ask for your password (once):")
        try:
            platform.install_scheduler()
        except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
            print(f"Schedule helper NOT installed: {e}")
        else:
            print(f"Schedule helper installed and running ({platform.SCHEDULER_NAME})")
    print_extension_instructions(platform.open_chrome_extensions)


if __name__ == "__main__":
    install()
