"""Applies schedules to /etc/hosts. Runs as root from a LaunchDaemon.

`block install` copies this file, schedule.py and an allowlist of blockable
domains into a root-owned folder (/Library/Application Support/Blocker) and
runs it with the Command Line Tools' python every 30 seconds and whenever
~/.blocker changes:

    python3 -I schedule_helper.py /Users/me/.blocker/schedules.json
    python3 -I schedule_helper.py --clear      # remove the section (uninstall)

It writes the domains of every running schedule into its own section of the
hosts file, between BEGIN and END below, and leaves the rest alone (the
manual blocks live in the BLOCKER-BEGIN/END section).

The schedules file is written by the user, so as root this treats it as
hostile: it never blocks on or follows it, survives any JSON, and only ever
writes hostnames from the root-owned allowlist (so a user process can't use
it to redirect, say, Apple's update servers). Writes to /etc/hosts hold
LOCK_FILE, which core.py's `sudo lockf ... cp` also takes, so manual blocks
and scheduled ones can't overwrite each other.
"""

import contextlib
import fcntl
import importlib.util
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Set


def _load_schedule_module():
    try:
        from . import schedule

        return schedule
    except ImportError:
        # The installed copy, run as a script: load schedule.py from beside
        # this file by path, without putting this folder ahead of the
        # standard library on sys.path.
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location(
            "blocker_schedule", os.path.join(here, "schedule.py")
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # dataclasses look themselves up here
        spec.loader.exec_module(module)
        return module


sch = _load_schedule_module()

HOSTS_FILE = Path("/etc/hosts")
LOCK_FILE = Path("/var/run/blocker-hosts.lock")
ALLOWLIST_NAME = "allowed-domains.txt"
BEGIN = "# BLOCKER-SCHEDULE-BEGIN"
END = "# BLOCKER-SCHEDULE-END"
MAX_SCHEDULES_BYTES = 1_000_000
_TMP_PREFIX = ".hosts-blocker-"

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_TLD = r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})"
_HOSTNAME = re.compile(rf"(?=.{{1,253}}\Z)(?:{_LABEL}\.)+{_TLD}")


class UnsafeHosts(Exception):
    """The hosts file isn't something root should write to right now."""


def valid_hostname(name: str) -> bool:
    return bool(_HOSTNAME.fullmatch(name))


def with_www(domains: Iterable[str]) -> Set[str]:
    """Each valid domain and its www. form (hosts entries don't cover
    subdomains)."""
    names = set()
    for d in domains:
        d = d.strip().lower()
        if valid_hostname(d):
            names.add(d)
            if not d.startswith("www.") and valid_hostname("www." + d):
                names.add("www." + d)
    return names


def hostnames(domains: Iterable[str], allowed: Set[str]) -> List[str]:
    """What to block for these domains: only names on the allowlist."""
    return sorted(with_www(domains) & allowed)


def load_allowlist(path: Path) -> Set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {line for line in text.split() if valid_hostname(line)}


def _outside_section(lines: List[str]) -> Iterator[str]:
    """Lines not in our section. An unmatched BEGIN runs to the end of the
    file; stray END markers are dropped."""
    inside = False
    for line in lines:
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        elif not inside:
            yield line


def render(content: str, names: List[str]) -> str:
    lines = list(_outside_section(content.splitlines()))
    if names:
        entries = [e for n in names for e in (f"127.0.0.1 {n}", f"::1 {n}")]
        lines = [*lines, BEGIN, *entries, END]
    return "\n".join(lines) + "\n" if lines else ""


def scheduled_hostnames(content: str) -> set:
    """Hostnames in our section (for the sync daemon and the TUI)."""
    names, inside = set(), False
    for line in content.splitlines():
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        elif inside:
            parts = line.split()
            if len(parts) == 2:
                names.add(parts[1])
    return names


def read_schedules(path: Path) -> Optional[str]:
    """The schedules file's text, or None if it's missing or not a plain
    file its folder's owner wrote: never a symlink, hard link, FIFO or
    anything oversized."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        owner = os.lstat(Path(path).parent).st_uid
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size > MAX_SCHEDULES_BYTES
            or info.st_nlink != 1
            or info.st_uid != owner
        ):
            return None
        with os.fdopen(fd, "r", encoding="utf-8", errors="replace") as f:
            fd = -1
            return f.read(MAX_SCHEDULES_BYTES)
    finally:
        if fd >= 0:
            os.close(fd)


LOCK_WAIT_SECONDS = 20


@contextlib.contextmanager
def locked(lock_path: Path, wait: float = LOCK_WAIT_SECONDS) -> Iterator[None]:
    """Holds the hosts lock. Gives up after `wait` seconds rather than
    hanging (launchd won't start the next run while this one is stuck)."""
    fd = os.open(
        lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
    )
    try:
        # Only its owner may open it, so no one else can sit on the lock.
        if os.fstat(fd).st_uid == os.geteuid():
            os.fchmod(fd, 0o600)
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{lock_path} is held by someone else")
                time.sleep(0.1)
        yield
    finally:
        os.close(fd)


def _hosts_target(hosts: Path) -> Path:
    """The real hosts file (/etc -> /private/etc), refusing a symlinked file
    or, as root, a folder anyone but root can write to."""
    folder = Path(os.path.realpath(hosts.parent))
    target = folder / hosts.name
    if stat.S_ISLNK(os.lstat(target).st_mode):
        raise UnsafeHosts(f"{target} is a symlink")
    if os.geteuid() == 0:
        info = os.lstat(folder)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise UnsafeHosts(f"{folder} is writable by someone other than root")
    return target


def _looks_like_hosts(content: str) -> bool:
    """Guards against writing back a file read mid-truncate."""
    return any("localhost" in line.split("#", 1)[0] for line in content.splitlines())


def _clean_stale_temp_files(folder: Path) -> None:
    for tmp in folder.glob(_TMP_PREFIX + "*"):
        with contextlib.suppress(OSError):
            if tmp.lstat().st_uid == os.geteuid():
                tmp.unlink()


def _write_hosts(target: Path, content: str, before: os.stat_result) -> bool:
    """Atomically replaces `target`, keeping its mode, unless it changed
    since `before`. True if written."""
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=_TMP_PREFIX)
    try:
        os.fchmod(fd, stat.S_IMODE(before.st_mode))
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        now = os.lstat(target)
        key = ("st_ino", "st_mtime_ns", "st_size")
        if [getattr(now, k) for k in key] != [getattr(before, k) for k in key]:
            os.unlink(tmp)  # someone wrote it meanwhile; next run catches up
            return False
        os.replace(tmp, target)
        return True
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def flush_dns() -> None:
    subprocess.run(["/usr/bin/dscacheutil", "-flushcache"], check=False)
    subprocess.run(["/usr/bin/killall", "-HUP", "mDNSResponder"], check=False)


def apply_names(
    names: List[str],
    hosts: Path = HOSTS_FILE,
    lock_path: Path = LOCK_FILE,
    flush=flush_dns,
) -> bool:
    """Makes the scheduled section hold exactly `names`. True if changed."""
    with locked(lock_path):
        target = _hosts_target(hosts)
        _clean_stale_temp_files(target.parent)
        before = os.lstat(target)
        current = target.read_text(encoding="utf-8", errors="surrogateescape")
        if not _looks_like_hosts(current):
            raise UnsafeHosts(f"{target} has no localhost entry; not touching it")
        updated = render(current, names)
        if updated == current or not _write_hosts(target, updated, before):
            return False
    flush()
    return True


def apply(
    schedules_path: Path,
    hosts: Path = HOSTS_FILE,
    now=None,
    flush=flush_dns,
    allowed: Optional[Set[str]] = None,
    lock_path: Path = LOCK_FILE,
) -> bool:
    """Brings the scheduled section up to date with the schedules file."""
    if allowed is None:
        allowed = load_allowlist(Path(__file__).resolve().parent / ALLOWLIST_NAME)
    now = now or sch.local_now()
    schedules = sch.list_from_json_skipping_bad(read_schedules(schedules_path))
    names = hostnames(sch.active_domains(schedules, now), allowed)
    return apply_names(names, hosts, lock_path, flush)


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: schedule_helper.py /path/to/schedules.json | --clear",
            file=sys.stderr,
        )
        return 2
    try:
        if argv[1] == "--clear":
            changed = apply_names([])
        else:
            changed = apply(Path(argv[1]))
    except Exception as e:  # one line in the log, not a traceback every run
        print(f"{sch.local_now():%Y-%m-%d %H:%M:%S} error: {e!r}", file=sys.stderr)
        return 1
    if changed:
        print(f"{sch.local_now():%Y-%m-%d %H:%M:%S} updated scheduled blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
