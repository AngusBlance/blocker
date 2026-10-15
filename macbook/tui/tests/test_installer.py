import os
import plistlib
import subprocess
import sys

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


PYTHON = "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9"


def _fake_sudo(monkeypatch, fail_bootstraps=0):
    """Records sudo commands; files are captured before their temp dir goes."""
    calls, copied = [], {}
    failures = [fail_bootstraps]

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "install" and "-d" not in cmd:
            copied[cmd[-1]] = open(cmd[-2], "rb").read()
        returncode = 0
        if cmd[1:3] == ["launchctl", "bootstrap"] and failures[0]:
            failures[0] -= 1
            returncode = 5
        return subprocess.CompletedProcess(cmd, returncode, b"", b"why it failed")

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer.time, "sleep", lambda s: None)
    monkeypatch.setattr(installer, "resolve_scheduler_python", lambda: PYTHON)
    return calls, copied


def test_install_scheduler_installs_root_owned_copies_and_a_launch_daemon(
    tmp_path, monkeypatch
):
    schedules = tmp_path / ".blocker" / "schedules.json"
    monkeypatch.setattr(installer, "SCHEDULES_FILE", schedules)
    calls, copied = _fake_sudo(monkeypatch)

    installer.install_scheduler()

    assert all(cmd[0] == "sudo" for cmd in calls)
    assert calls[0] == ["sudo", "rm", "-rf", str(installer.SCHEDULER_DIR)]
    d = installer.SCHEDULER_DIR
    assert list(copied) == [
        str(d / "schedule.py"),
        str(d / "schedule_helper.py"),
        str(d / "allowed-domains.txt"),
        str(installer.NEWSYSLOG_CONF),
        str(installer.SCHEDULER_PLIST),
    ]
    for cmd in calls:
        if cmd[1] == "install":
            assert "-o root -g wheel" in " ".join(cmd)
    for name in installer.SCHEDULER_FILES:
        assert copied[str(d / name)] == (installer.BLOCKLIB_DIR / name).read_bytes()
    allowed = copied[str(d / "allowed-domains.txt")].decode().split()
    assert "youtube.com" in allowed and "www.tiktok.com" in allowed
    assert not any("apple.com" in a for a in allowed)

    plist = plistlib.loads(copied[str(installer.SCHEDULER_PLIST)])
    assert plist["Label"] == installer.SCHEDULER_LABEL
    assert plist["ProgramArguments"] == [
        PYTHON,
        "-I",
        str(d / "schedule_helper.py"),
        str(schedules),
    ]
    assert plist["WatchPaths"] == [str(schedules.parent)]
    assert plist["StartInterval"] == 30
    assert plist["RunAtLoad"] is True
    assert plist["StandardErrorPath"] == str(installer.SCHEDULER_LOG)
    assert schedules.parent.is_dir()  # so there's something to watch
    assert [cmd[1:3] for cmd in calls[-3:]] == [
        ["launchctl", "bootout"],
        ["launchctl", "enable"],
        ["launchctl", "bootstrap"],
    ]


def test_install_scheduler_retries_a_bootstrap_launchd_refuses_at_first(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "s.json")
    calls, _ = _fake_sudo(monkeypatch, fail_bootstraps=2)
    installer.install_scheduler()
    assert sum(cmd[1:3] == ["launchctl", "bootstrap"] for cmd in calls) == 3


def test_install_scheduler_gives_up_saying_why(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "s.json")
    _fake_sudo(monkeypatch, fail_bootstraps=99)
    with pytest.raises(RuntimeError, match="why it failed"):
        installer.install_scheduler()


def test_scheduler_plist_escapes_odd_home_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "a&b <c>" / "s.json")
    plist = plistlib.loads(installer._scheduler_plist(PYTHON))
    assert plist["ProgramArguments"][-1].endswith("a&b <c>/s.json")


def test_the_interpreter_must_be_root_only(tmp_path):
    # A python the user owns (this test's own venv) is refused.
    user_python = tmp_path / "python3"
    user_python.symlink_to(sys.executable)
    with pytest.raises(RuntimeError, match="root-only"):
        installer.resolve_scheduler_python(user_python)
    with pytest.raises(RuntimeError, match="Command Line Tools"):
        installer.resolve_scheduler_python(tmp_path / "missing")


@pytest.mark.skipif(
    not installer.CLT_PYTHON.exists(), reason="needs the Command Line Tools"
)
def test_the_command_line_tools_python_is_accepted():
    python = installer.resolve_scheduler_python()
    assert python.startswith("/Library/Developer/CommandLineTools/")
    assert not os.path.islink(python)


def test_uninstall_clears_the_section_then_removes_everything(tmp_path, monkeypatch):
    calls, _ = _fake_sudo(monkeypatch)
    helper_dir = tmp_path / "Blocker"
    helper_dir.mkdir()
    (helper_dir / "schedule_helper.py").write_text("")
    monkeypatch.setattr(installer, "SCHEDULER_DIR", helper_dir)
    installer.uninstall_scheduler()
    assert calls[0][1:] == [
        PYTHON,
        "-I",
        str(helper_dir / "schedule_helper.py"),
        "--clear",
    ]
    assert calls[1][1:3] == ["launchctl", "bootout"]
    assert calls[2][1:3] == ["rm", "-rf"]
    assert str(installer.SCHEDULER_PLIST) in calls[2]
