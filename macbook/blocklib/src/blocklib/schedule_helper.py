"""Applies schedules to /etc/hosts. Runs as root from a LaunchDaemon.

`block install` copies this file and schedule.py into a root-owned folder
(/Library/Application Support/Blocker) and runs it with the system python
every 30 seconds and whenever ~/.blocker changes:

    /usr/bin/python3 -I schedule_helper.py /Users/me/.blocker/schedules.json

It writes the domains of every running schedule into its own section of the
hosts file, between BEGIN and END below, and leaves the rest alone (the
manual blocks live in the BLOCKER-BEGIN/END section). The schedules file is
written by the user, so everything read from it is validated before it goes
anywhere near /etc/hosts.
"""

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from . import schedule as sch
except ImportError:  # run as a script from the installed copy
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import schedule as sch  # type: ignore[no-redef]

HOSTS_FILE = Path("/etc/hosts")
BEGIN = "# BLOCKER-SCHEDULE-BEGIN"
END = "# BLOCKER-SCHEDULE-END"
MAX_SCHEDULES_BYTES = 1_000_000

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOSTNAME = re.compile(rf"^(?=.{{1,253}}$)(?:{_LABEL}\.)+[a-z]{{2,63}}$")


def valid_hostname(name: str) -> bool:
    return bool(_HOSTNAME.match(name))


def hostnames(domains: Iterable[str]) -> List[str]:
    """What to block for these domains: each valid one and its www. form
    (hosts entries don't cover subdomains), sorted."""
    names = set()
    for d in domains:
        d = d.strip().lower()
        if not valid_hostname(d):
            continue
        names.add(d)
        if not d.startswith("www."):
            names.add("www." + d)
    return sorted(n for n in names if valid_hostname(n))


def strip_section(content: str) -> List[str]:
    """The hosts file's lines without our section."""
    lines = content.splitlines()
    if BEGIN in lines and END in lines:
        start, end = lines.index(BEGIN), lines.index(END)
        if start < end:
            return lines[:start] + lines[end + 1 :]
    return [line for line in lines if line not in (BEGIN, END)]


def render(content: str, names: List[str]) -> str:
    lines = strip_section(content)
    if names:
        entries = [e for n in names for e in (f"127.0.0.1 {n}", f"::1 {n}")]
        lines = [*lines, BEGIN, *entries, END]
    return "\n".join(lines) + "\n" if lines else ""


def scheduled_hostnames(content: str) -> set:
    """Hostnames in our section (for the sync daemon and the TUI)."""
    lines = content.splitlines()
    if BEGIN not in lines or END not in lines:
        return set()
    start, end = lines.index(BEGIN), lines.index(END)
    names = set()
    for line in lines[start + 1 : end]:
        parts = line.split()
        if len(parts) == 2:
            names.add(parts[1])
    return names


def read_schedules(path: Path) -> Optional[str]:
    """The schedules file's text, or None if it's missing or unsafe to
    trust: not a regular file, a symlink, or oversized."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SCHEDULES_BYTES:
            return None
        with os.fdopen(fd, "r", encoding="utf-8", errors="replace") as f:
            fd = -1
            return f.read(MAX_SCHEDULES_BYTES)
    finally:
        if fd >= 0:
            os.close(fd)


def write_hosts(hosts: Path, content: str) -> None:
    """Atomically, keeping the file's mode."""
    real = Path(os.path.realpath(hosts))
    mode = stat.S_IMODE(real.stat().st_mode) if real.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=".hosts-blocker-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, real)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def flush_dns() -> None:
    subprocess.run(["dscacheutil", "-flushcache"], check=False)
    subprocess.run(["killall", "-HUP", "mDNSResponder"], check=False)


def apply(schedules_path: Path, hosts: Path = HOSTS_FILE, now=None, flush=flush_dns):
    """Brings the hosts file's scheduled section up to date. True if it
    changed."""
    now = now or sch.local_now()
    schedules = sch.list_from_json_skipping_bad(read_schedules(schedules_path))
    names = hostnames(sch.active_domains(schedules, now))
    current = hosts.read_text()
    updated = render(current, names)
    if updated == current:
        return False
    write_hosts(hosts, updated)
    flush()
    return True


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: schedule_helper.py /path/to/schedules.json", file=sys.stderr)
        return 2
    if apply(Path(argv[1])):
        print(f"{sch.local_now():%Y-%m-%d %H:%M:%S} updated scheduled blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
