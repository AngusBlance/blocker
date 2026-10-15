import os
import plistlib
import subprocess

import pytest

from blocker_tui import installer


def test_install_block_app_writes_bundle_and_registers_with_launch_services(
    tmp_path, monkeypatch
):
    bundle = tmp_path / "Block.app"
    monkeypatch.setattr(installer, "APP_BUNDLE", bundle)
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **k: calls.append(a[0]))

    result = installer.install_block_app()

    assert result == bundle
    info_plist = (bundle / "Contents" / "Info.plist").read_text()
    assert "<string>block</string>" in info_plist

    launcher = bundle / "Contents" / "MacOS" / "block"
    assert "exec block" in launcher.read_text()
    assert os.access(launcher, os.X_OK)

    assert any(installer.LSREGISTER in cmd for cmd in calls)


def test_install_sync_daemon_writes_plist_pointing_at_the_entry_point_and_bootstraps(
    tmp_path, monkeypatch
):
    plist_path = tmp_path / "agent.plist"
    monkeypatch.setattr(installer, "LAUNCH_AGENT_PLIST", plist_path)
    monkeypatch.setattr(installer, "LOGS_DIR", tmp_path / "logs")
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **k: calls.append(a[0]))

    installer.install_sync_daemon()

    content = plist_path.read_text()
    assert str(installer.VENV_BLOCKER_SYNC) in content
    assert [cmd[1] for cmd in calls] == ["bootstrap"]


def test_install_sync_daemon_reloads_cleanly_when_already_installed(
    tmp_path, monkeypatch
):
    plist_path = tmp_path / "agent.plist"
    plist_path.write_text("stale previous install")
    monkeypatch.setattr(installer, "LAUNCH_AGENT_PLIST", plist_path)
    monkeypatch.setattr(installer, "LOGS_DIR", tmp_path / "logs")
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **k: calls.append(a[0]))

    installer.install_sync_daemon()

    assert [cmd[1] for cmd in calls] == ["bootout", "bootstrap"]


def test_print_extension_instructions_points_at_the_real_extension_dir(
    monkeypatch, capsys
):
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **k: None)

    installer.print_extension_instructions()

    out = capsys.readouterr().out
    assert str(installer.EXTENSION_DIR) in out
    assert "Developer mode" in out
    # Chrome needs the folder holding manifest.json, not the one with node_modules.
    assert (installer.EXTENSION_DIR / "manifest.json").is_file()


def _fake_sudo(monkeypatch, fail_bootstraps=0):
    """Records commands; the plist copy is captured before its temp dir goes."""
    calls, plists = [], []
    failures = [fail_bootstraps]

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "install" and cmd[-1].endswith(".plist"):
            plists.append(plistlib.loads(open(cmd[-2], "rb").read()))
        returncode = 0
        if cmd[1:3] == ["launchctl", "bootstrap"] and failures[0]:
            failures[0] -= 1
            returncode = 5
        return subprocess.CompletedProcess(cmd, returncode, "", "")

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer.time, "sleep", lambda s: None)
    return calls, plists


def test_install_scheduler_installs_root_owned_copies_and_a_launch_daemon(
    tmp_path, monkeypatch
):
    schedules = tmp_path / ".blocker" / "schedules.json"
    monkeypatch.setattr(installer, "SCHEDULES_FILE", schedules)
    calls, plists = _fake_sudo(monkeypatch)

    installer.install_scheduler()

    assert all(cmd[0] == "sudo" for cmd in calls)
    copied = [cmd[-1] for cmd in calls if cmd[1] == "install" and "-d" not in cmd]
    assert copied == [
        str(installer.SCHEDULER_DIR / "schedule.py"),
        str(installer.SCHEDULER_DIR / "schedule_helper.py"),
        str(installer.SCHEDULER_PLIST),
    ]
    for cmd in calls:
        if cmd[1] == "install":
            assert "-o root -g wheel" in " ".join(cmd)
    # The sources really exist (they're copied from the installed blocklib).
    for name in installer.SCHEDULER_FILES:
        assert (installer.BLOCKLIB_DIR / name).is_file()

    (plist,) = plists
    assert plist["Label"] == installer.SCHEDULER_LABEL
    assert plist["ProgramArguments"] == [
        "/usr/bin/python3",
        "-I",
        str(installer.SCHEDULER_DIR / "schedule_helper.py"),
        str(schedules),
    ]
    assert plist["WatchPaths"] == [str(schedules.parent)]
    assert plist["StartInterval"] == 30
    assert schedules.parent.is_dir()  # so there's something to watch
    assert [cmd[1:3] for cmd in calls[-2:]] == [
        ["launchctl", "bootout"],
        ["launchctl", "bootstrap"],
    ]


def test_install_scheduler_retries_a_bootstrap_launchd_refuses_at_first(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "s.json")
    calls, _ = _fake_sudo(monkeypatch, fail_bootstraps=2)
    installer.install_scheduler()
    assert sum(cmd[1:3] == ["launchctl", "bootstrap"] for cmd in calls) == 3


def test_install_scheduler_gives_up_eventually(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "s.json")
    _fake_sudo(monkeypatch, fail_bootstraps=99)
    with pytest.raises(subprocess.CalledProcessError):
        installer.install_scheduler()


def test_scheduler_plist_escapes_odd_home_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "a&b <c>" / "s.json")
    plist = plistlib.loads(installer._scheduler_plist())
    assert plist["ProgramArguments"][-1].endswith("a&b <c>/s.json")
