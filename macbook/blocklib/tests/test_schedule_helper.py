"""The root helper that applies schedules to /etc/hosts. Tests use temp
files for both, never the real /etc/hosts."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from blocklib import schedule_helper as helper
from blocklib.core import BEGIN_MARK, END_MARK, HostsBlocker
from blocklib.sync_daemon import run

LONDON = ZoneInfo("Europe/London")
MONDAY_10AM = datetime(2026, 10, 12, 10, tzinfo=LONDON)
BASE = "127.0.0.1 localhost\n::1 localhost\n"
MANUAL = f"{BEGIN_MARK}\n127.0.0.1 netflix.com\n::1 netflix.com\n{END_MARK}\n"


def schedule(id="work", domains=("youtube.com",), start=540, end=1020, **extra):
    return {
        "id": id,
        "name": id.title(),
        "sites": ["YouTube"],
        "domains": list(domains),
        "apps": [],
        "plan": {"type": "every", "days": [1, 2, 3, 4, 5], "start": start, "end": end},
        "action": {"type": "block"},
        "enabled": True,
        **extra,
    }


def setup(tmp_path, schedules, hosts=BASE + MANUAL):
    schedules_path = tmp_path / "schedules.json"
    schedules_path.write_text(json.dumps(schedules))
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text(hosts)
    return schedules_path, hosts_path


def apply(schedules_path, hosts_path, now=MONDAY_10AM):
    flushes = []
    changed = helper.apply(
        schedules_path, hosts_path, now=now, flush=lambda: flushes.append(1)
    )
    return changed, len(flushes)


def test_running_schedules_get_their_own_section(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    assert apply(schedules_path, hosts_path) == (True, 1)
    content = hosts_path.read_text()
    assert content.startswith(BASE + MANUAL)  # the rest is untouched
    assert helper.scheduled_hostnames(content) == {"youtube.com", "www.youtube.com"}
    blocker = HostsBlocker(hosts_path)
    assert blocker.blocked_urls == {"netflix.com"}  # manual only
    assert blocker.all_blocked_urls == {
        "netflix.com",
        "youtube.com",
        "www.youtube.com",
    }


def test_nothing_changes_when_nothing_did(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    assert apply(schedules_path, hosts_path) == (False, 0)


def test_section_goes_when_the_schedule_ends_or_is_paused(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    evening = datetime(2026, 10, 12, 18, tzinfo=LONDON)
    assert apply(schedules_path, hosts_path, now=evening) == (True, 1)
    assert hosts_path.read_text() == BASE + MANUAL

    paused_until = int(datetime(2026, 10, 12, 17, tzinfo=LONDON).timestamp() * 1000)
    schedules_path.write_text(json.dumps([schedule(pausedUntil=paused_until)]))
    assert apply(schedules_path, hosts_path) == (False, 0)


def test_manual_blocks_and_scheduled_ones_dont_disturb_each_other(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    blocker = HostsBlocker(hosts_path)
    blocker._commit = lambda content: hosts_path.write_text(content)
    blocker.unblock("netflix.com")
    blocker.block("tiktok.com")
    assert blocker.blocked_urls == {"tiktok.com"}
    assert blocker.scheduled_urls == {"youtube.com", "www.youtube.com"}
    apply(schedules_path, hosts_path)  # still in step
    assert HostsBlocker(hosts_path).blocked_urls == {"tiktok.com"}


def test_hostnames_are_validated_before_they_reach_the_hosts_file(tmp_path):
    evil = [
        "youtube.com\n0.0.0.0 bank.com",
        "youtube.com bank.com",
        "# comment",
        "-bad.com",
        "localhost",
        "a" * 300 + ".com",
        "../etc",
    ]
    schedules_path, hosts_path = setup(
        tmp_path, [schedule(domains=[*evil, "Netflix.COM"])]
    )
    apply(schedules_path, hosts_path)
    assert helper.scheduled_hostnames(hosts_path.read_text()) == {
        "netflix.com",
        "www.netflix.com",
    }
    assert "bank.com" not in hosts_path.read_text()


def test_bad_schedules_are_skipped_not_fatal(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [{"id": "broken"}, schedule()])
    apply(schedules_path, hosts_path)
    assert "youtube.com" in helper.scheduled_hostnames(hosts_path.read_text())
    schedules_path.write_text("{not json")
    apply(schedules_path, hosts_path)
    assert hosts_path.read_text() == BASE + MANUAL


def test_a_missing_or_symlinked_schedules_file_counts_as_no_schedules(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    link = tmp_path / "link.json"
    link.symlink_to(schedules_path)
    apply(link, hosts_path)
    assert hosts_path.read_text() == BASE + MANUAL
    assert apply(tmp_path / "missing.json", hosts_path) == (False, 0)


def test_hosts_mode_is_kept(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    hosts_path.chmod(0o644)
    apply(schedules_path, hosts_path)
    assert hosts_path.stat().st_mode & 0o777 == 0o644
    assert not list(tmp_path.glob(".hosts-blocker-*"))


def test_a_stray_marker_is_cleaned_up(tmp_path):
    schedules_path, hosts_path = setup(
        tmp_path, [], hosts=BASE + helper.BEGIN + "\n127.0.0.1 x.com\n"
    )
    apply(schedules_path, hosts_path)
    assert helper.BEGIN not in hosts_path.read_text()


def test_installed_copy_runs_standalone_in_isolated_mode(tmp_path):
    """As the LaunchDaemon runs it: two files in a folder, `python -I`, no
    blocklib package or dependencies installed."""
    install = tmp_path / "Blocker"
    install.mkdir()
    src = Path(helper.__file__).parent
    for name in ("schedule.py", "schedule_helper.py"):
        shutil.copy(src / name, install / name)
    # Usage error before it touches /etc/hosts.
    result = subprocess.run(
        [sys.executable, "-I", str(install / "schedule_helper.py")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"]},
    )
    assert result.returncode == 2, result.stderr
    assert "usage" in result.stderr


def test_sync_daemon_broadcasts_when_the_hosts_file_changes(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    notified = threading.Event()

    class FakeServer:
        def start(self):
            pass

        def stop(self):
            pass

        def notify_change(self):
            notified.set()

    stop = threading.Event()
    thread = threading.Thread(
        target=run, args=(FakeServer(), stop), kwargs={"hosts": hosts, "poll": 0.01}
    )
    thread.start()
    try:
        time.sleep(0.05)
        assert not notified.is_set()
        hosts.write_text(BASE + MANUAL)
        os.utime(hosts, ns=(0, 1))  # a different mtime even on coarse clocks
        assert notified.wait(2)
    finally:
        stop.set()
        thread.join(timeout=2)
