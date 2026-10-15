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

import pytest

from blocklib import schedule_helper as helper
from blocklib.core import BEGIN_MARK, END_MARK, HostsBlocker
from blocklib.sync_daemon import run

CLT_PYTHON = "/Library/Developer/CommandLineTools/usr/bin/python3"
LONDON = ZoneInfo("Europe/London")
MONDAY_10AM = datetime(2026, 10, 12, 10, tzinfo=LONDON)
BASE = "127.0.0.1 localhost\n::1 localhost\n"
MANUAL = f"{BEGIN_MARK}\n127.0.0.1 netflix.com\n::1 netflix.com\n{END_MARK}\n"


def schedule(
    id="work",
    domains=("youtube.com",),
    start=540,
    end=1020,
    plan_days=(1, 2, 3, 4, 5),
    **extra,
):
    return {
        "id": id,
        "name": id.title(),
        "sites": ["YouTube"],
        "domains": list(domains),
        "apps": [],
        "plan": {"type": "every", "days": list(plan_days), "start": start, "end": end},
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


ALLOWED = helper.with_www(["youtube.com", "netflix.com", "tiktok.com"])


def apply(schedules_path, hosts_path, now=MONDAY_10AM, allowed=ALLOWED):
    flushes = []
    changed = helper.apply(
        schedules_path,
        hosts_path,
        now=now,
        flush=lambda: flushes.append(1),
        allowed=allowed,
        lock_path=hosts_path.parent / "hosts.lock",
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
        "youtube.com\n",
    ]
    schedules_path, hosts_path = setup(
        tmp_path, [schedule(domains=[*evil, "Netflix.COM"])]
    )
    apply(schedules_path, hosts_path)
    assert helper.scheduled_hostnames(hosts_path.read_text()) == {
        "netflix.com",
        "www.netflix.com",
        "youtube.com",  # from "youtube.com\n", trimmed
        "www.youtube.com",
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


def test_unbalanced_markers_take_their_entries_with_them(tmp_path):
    schedules_path, hosts_path = setup(
        tmp_path, [], hosts=BASE + helper.BEGIN + "\n127.0.0.1 x.com\n"
    )
    apply(schedules_path, hosts_path)
    assert hosts_path.read_text() == BASE
    hosts_path.write_text(BASE + helper.END + "\n")
    apply(schedules_path, hosts_path)
    assert hosts_path.read_text() == BASE


def test_installed_copy_runs_standalone_in_isolated_mode(tmp_path):
    """As the LaunchDaemon runs it: two files in a folder, `python -I`, no
    blocklib package or dependencies installed."""
    install = tmp_path / "Blocker"
    install.mkdir()
    src = Path(helper.__file__).parent
    for name in ("schedule.py", "schedule_helper.py"):
        shutil.copy(src / name, install / name)
    # A stray json.py beside it must not shadow the standard library.
    (install / "json.py").write_text("raise SystemExit('shadowed')\n")
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


@pytest.mark.skipif(
    not Path(CLT_PYTHON).exists(), reason="needs the Command Line Tools' python"
)
def test_the_real_interpreter_applies_schedules_from_the_installed_copy(tmp_path):
    install = tmp_path / "Blocker"
    install.mkdir()
    src = Path(helper.__file__).parent
    for name in ("schedule.py", "schedule_helper.py"):
        shutil.copy(src / name, install / name)
    (install / helper.ALLOWLIST_NAME).write_text("youtube.com\nwww.youtube.com\n")
    schedules_path, hosts_path = setup(
        tmp_path, [schedule(start=0, end=0, plan_days=list(range(1, 8)))]
    )
    script = (
        "import importlib.util, pathlib, sys;"
        f"spec = importlib.util.spec_from_file_location('h', {str(install / 'schedule_helper.py')!r});"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
        f"print(m.apply(pathlib.Path({str(schedules_path)!r}), pathlib.Path({str(hosts_path)!r}),"
        f" flush=lambda: None, lock_path=pathlib.Path({str(tmp_path / 'lock')!r})))"
    )
    result = subprocess.run(
        [CLT_PYTHON, "-I", "-c", script], capture_output=True, text=True
    )
    assert result.stdout.strip() == "True", result.stderr
    assert helper.scheduled_hostnames(hosts_path.read_text()) == {
        "youtube.com",
        "www.youtube.com",
    }


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


def test_only_allowlisted_hostnames_are_ever_written(tmp_path):
    schedules_path, hosts_path = setup(
        tmp_path,
        [schedule(domains=["youtube.com", "swscan.apple.com", "ocsp.digicert.com"])],
    )
    apply(schedules_path, hosts_path)
    assert helper.scheduled_hostnames(hosts_path.read_text()) == {
        "youtube.com",
        "www.youtube.com",
    }
    # No allowlist installed: nothing at all.
    apply(schedules_path, hosts_path, allowed=set())
    assert hosts_path.read_text() == BASE + MANUAL


def test_hostile_schedule_files_dont_crash_or_hang_it(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    for text in ["[" * 100_000, "[" + "9" * 300_000 + "]", "\x00\xff"]:
        schedules_path.write_text(text, errors="surrogateescape")
        apply(schedules_path, hosts_path)
        assert hosts_path.read_text() == BASE + MANUAL
        apply(tmp_path / "missing.json", hosts_path)


def test_a_fifo_or_hard_link_is_ignored_without_blocking(tmp_path):
    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo)
    assert helper.read_schedules(fifo) is None  # returns, doesn't hang
    real = tmp_path / "real.json"
    real.write_text("[]")
    os.link(real, tmp_path / "linked.json")
    assert helper.read_schedules(tmp_path / "linked.json") is None


def test_a_symlinked_hosts_file_is_refused(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    real = tmp_path / "elsewhere"
    real.write_text(BASE)
    hosts_path.unlink()
    hosts_path.symlink_to(real)
    with pytest.raises(helper.UnsafeHosts):
        apply(schedules_path, hosts_path)
    assert real.read_text() == BASE


def test_a_hosts_file_read_mid_truncate_is_never_written_back(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()], hosts="")
    with pytest.raises(helper.UnsafeHosts):
        apply(schedules_path, hosts_path)
    assert hosts_path.read_text() == ""


def test_a_hosts_file_that_changes_mid_update_is_left_for_next_time(
    tmp_path, monkeypatch
):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    real_mkstemp = helper.tempfile.mkstemp

    def racing_mkstemp(**kw):
        hosts_path.write_text(BASE + MANUAL + "127.0.0.1 new.com\n")  # core's cp
        os.utime(hosts_path, ns=(0, 1))
        return real_mkstemp(**kw)

    monkeypatch.setattr(helper.tempfile, "mkstemp", racing_mkstemp)
    assert apply(schedules_path, hosts_path) == (False, 0)
    assert "new.com" in hosts_path.read_text()  # their write survives
    assert not list(tmp_path.glob(".hosts-blocker-*"))


def test_the_lock_is_held_while_writing(tmp_path, monkeypatch):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    lock = hosts_path.parent / "hosts.lock"
    seen = []

    def check_locked(*a, **kw):
        import fcntl

        fd = os.open(lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            seen.append("free")
        except BlockingIOError:
            seen.append("held")
        finally:
            os.close(fd)
        return real(*a, **kw)

    real = helper.os.replace
    monkeypatch.setattr(helper.os, "replace", check_locked)
    apply(schedules_path, hosts_path)
    assert seen == ["held"]


def test_stale_temp_files_are_cleaned_up(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    (tmp_path / ".hosts-blocker-stale").write_text("x")
    apply(schedules_path, hosts_path)
    assert not list(tmp_path.glob(".hosts-blocker-*"))


def test_main_logs_one_line_instead_of_crashing(tmp_path, monkeypatch, capsys):
    def boom(*a, **kw):
        raise helper.UnsafeHosts("nope")

    monkeypatch.setattr(helper, "apply", boom)
    assert helper.main(["x", str(tmp_path / "s.json")]) == 1
    err = capsys.readouterr().err
    assert "error" in err and "Traceback" not in err


def test_clear_removes_the_section(tmp_path):
    schedules_path, hosts_path = setup(tmp_path, [schedule()])
    apply(schedules_path, hosts_path)
    helper.apply_names([], hosts_path, tmp_path / "hosts.lock", flush=lambda: None)
    assert hosts_path.read_text() == BASE + MANUAL
