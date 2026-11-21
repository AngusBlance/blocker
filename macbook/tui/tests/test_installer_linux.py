"""installer_linux.py: the .desktop entry, systemd units and the root
helper's install, with sudo and systemctl faked - these run on any OS. The
unit files are also checked by systemd itself where it's installed."""

import configparser
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from blocker_tui import installer_linux as installer


def test_install_launcher_puts_block_in_the_app_menu(tmp_path, monkeypatch):
    entry = tmp_path / "applications" / "block.desktop"
    monkeypatch.setattr(installer, "DESKTOP_ENTRY", entry)
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/home/me/bin/block")

    assert installer.install_launcher() == entry

    desktop = configparser.ConfigParser(interpolation=None)
    desktop.read_string(entry.read_text())
    section = desktop["Desktop Entry"]
    assert section["Name"] == "Block"
    assert section["Exec"] == '"/home/me/bin/block"'
    assert section["Terminal"] == "true"


def test_the_launcher_falls_back_to_block_on_path(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    assert 'Exec="block"' in installer.desktop_entry()


def test_desktop_exec_quotes_odd_paths():
    assert installer._desktop_exec_arg('/a b/$x"`\\') == '"/a b/\\$x\\"\\`\\\\"'
    assert installer._desktop_exec_arg("/100%/block") == '"/100%%/block"'


@pytest.mark.skipif(
    not shutil.which("desktop-file-validate"), reason="needs desktop-file-utils"
)
def test_the_desktop_entry_is_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/home/me/bin/block")
    entry = tmp_path / "block.desktop"
    entry.write_text(installer.desktop_entry())
    result = subprocess.run(
        ["desktop-file-validate", str(entry)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == ""


def fake_systemctl(monkeypatch):
    calls = []
    monkeypatch.setattr(
        installer.subprocess, "run", lambda cmd, **kw: calls.append(cmd)
    )
    return calls


def test_install_sync_daemon_writes_a_user_service_for_the_entry_point(
    tmp_path, monkeypatch
):
    unit = tmp_path / "systemd" / "user" / "blocker-sync.service"
    monkeypatch.setattr(installer, "SYNC_UNIT_FILE", unit)
    calls = fake_systemctl(monkeypatch)

    installer.install_sync_daemon()

    service = configparser.ConfigParser(interpolation=None)
    service.read_string(unit.read_text())
    assert service["Service"]["ExecStart"] == f'"{installer.VENV_BLOCKER_SYNC}"'
    assert service["Service"]["Restart"] == "always"
    assert service["Install"]["WantedBy"] == "default.target"
    name = installer.SYNC_NAME
    assert calls == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", name],
        # restart, so a reinstall after an update runs the new code
        ["systemctl", "--user", "restart", name],
    ]


def test_unit_values_escape_specifiers_and_quotes():
    assert installer._exec_arg('/a b/50%/"x"/$HOME') == ('"/a b/50%%/\\"x\\"/$$HOME"')


PYTHON = "/usr/bin/python3"


def _fake_sudo(monkeypatch, fail_start=False):
    """Records sudo commands; files are captured before their temp dir goes."""
    calls, copied = [], {}

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "install" and "-d" not in cmd:
            copied[cmd[-1]] = open(cmd[-2], "rb").read()
        returncode = 0
        if fail_start and cmd[1:3] == ["systemctl", "start"]:
            returncode = 1
        return subprocess.CompletedProcess(cmd, returncode, b"", b"why it failed")

    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setattr(installer, "resolve_scheduler_python", lambda: PYTHON)
    return calls, copied


def parse_unit(text: bytes) -> configparser.ConfigParser:
    # Path units repeat PathChanged=, so keep every value.
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.optionxform = str
    unit.read_string(text.decode())
    return unit


def test_install_scheduler_installs_root_owned_copies_and_systemd_units(
    tmp_path, monkeypatch
):
    schedules = tmp_path / ".blocker" / "schedules.json"
    monkeypatch.setattr(installer, "SCHEDULES_FILE", schedules)
    calls, copied = _fake_sudo(monkeypatch)

    installer.install_scheduler()

    assert all(cmd[0] == "sudo" for cmd in calls)
    triggers = ["blocker-scheduler.timer", "blocker-scheduler.path"]
    assert calls[0] == ["sudo", "systemctl", "stop", *triggers]
    assert calls[1] == ["sudo", "rm", "-rf", str(installer.SCHEDULER_DIR)]
    d, units = installer.SCHEDULER_DIR, installer.SYSTEM_UNIT_DIR
    assert list(copied) == [
        str(d / "schedule.py"),
        str(d / "schedule_helper.py"),
        str(d / "allowed-domains.txt"),
        str(units / "blocker-scheduler.service"),
        str(units / "blocker-scheduler.timer"),
        str(units / "blocker-scheduler.path"),
    ]
    for cmd in calls:
        if cmd[1] == "install":
            assert "-o root -g root" in " ".join(cmd)
    for name in installer.SCHEDULER_FILES:
        assert copied[str(d / name)] == (installer.BLOCKLIB_DIR / name).read_bytes()
    allowed = copied[str(d / "allowed-domains.txt")].decode().split()
    assert "youtube.com" in allowed and "www.tiktok.com" in allowed

    service = parse_unit(copied[str(units / "blocker-scheduler.service")])
    assert service["Service"]["Type"] == "oneshot"
    assert service["Service"]["ExecStart"] == (
        f'"{PYTHON}" "-I" "{d / "schedule_helper.py"}" "{schedules}"'
    )
    assert service["Unit"]["StartLimitIntervalSec"] == "0"
    timer = parse_unit(copied[str(units / "blocker-scheduler.timer")])
    assert timer["Timer"]["OnCalendar"] == "*:*:00/30"
    path = copied[str(units / "blocker-scheduler.path")].decode()
    assert f"PathChanged={schedules.parent}\n" in path
    assert "PathChanged=/etc/hosts\n" in path
    assert schedules.parent.is_dir()  # so there's something to watch

    assert calls[-3:] == [
        ["sudo", "systemctl", "daemon-reload"],
        ["sudo", "systemctl", "enable", "--now", *triggers],
        ["sudo", "systemctl", "start", "blocker-scheduler.service"],
    ]


def test_install_scheduler_says_why_the_first_run_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "s.json")
    _fake_sudo(monkeypatch, fail_start=True)
    with pytest.raises(RuntimeError, match="why it failed"):
        installer.install_scheduler()


def test_scheduler_installed_looks_for_the_service(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "SYSTEM_UNIT_DIR", tmp_path)
    assert installer.scheduler_installed() is False
    (tmp_path / "blocker-scheduler.service").write_text("")
    assert installer.scheduler_installed() is True


def test_a_missing_interpreter_says_to_install_python(tmp_path):
    with pytest.raises(RuntimeError, match="apt install python3"):
        installer.resolve_scheduler_python(tmp_path / "missing")


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not installer.SYSTEM_PYTHON.exists(),
    reason="needs Linux's /usr/bin/python3",
)
def test_the_system_python_is_accepted():
    # The stable path, not the versioned file it points at.
    assert installer.resolve_scheduler_python() == str(installer.SYSTEM_PYTHON)


def test_uninstall_clears_the_section_then_removes_everything(tmp_path, monkeypatch):
    calls, _ = _fake_sudo(monkeypatch)
    helper_dir = tmp_path / "blocker"
    helper_dir.mkdir()
    (helper_dir / "schedule_helper.py").write_text("")
    monkeypatch.setattr(installer, "SCHEDULER_DIR", helper_dir)
    installer.uninstall_scheduler()
    # stopped first, so it can't put the blocks back
    assert calls[0][1:4] == ["systemctl", "disable", "--now"]
    assert calls[1][1:] == ["systemctl", "stop", "blocker-scheduler.service"]
    assert calls[2][1:] == [
        PYTHON,
        "-I",
        str(helper_dir / "schedule_helper.py"),
        "--clear",
    ]
    assert calls[3][1:4] == ["rm", "-rf", str(helper_dir)]
    for name in installer.SCHEDULER_UNITS:
        assert str(installer.SYSTEM_UNIT_DIR / name) in calls[3]
    assert calls[4][1:] == ["systemctl", "daemon-reload"]


def test_uninstall_still_removes_the_helper_without_its_python(
    tmp_path, monkeypatch, capsys
):
    calls, _ = _fake_sudo(monkeypatch)

    def no_python():
        raise RuntimeError("no python3")

    monkeypatch.setattr(installer, "resolve_scheduler_python", no_python)
    helper_dir = tmp_path / "blocker"
    helper_dir.mkdir()
    (helper_dir / "schedule_helper.py").write_text("")
    monkeypatch.setattr(installer, "SCHEDULER_DIR", helper_dir)
    installer.uninstall_scheduler()
    assert [c[1] for c in calls] == ["systemctl", "systemctl", "rm", "systemctl"]
    assert "by hand" in capsys.readouterr().out


def test_open_chrome_extensions_uses_the_first_chrome_found(monkeypatch):
    found = {"chromium": "/snap/bin/chromium"}
    monkeypatch.setattr(installer.shutil, "which", found.get)
    opened = []
    monkeypatch.setattr(
        installer.subprocess, "Popen", lambda cmd, **kw: opened.append(cmd)
    )
    assert installer.open_chrome_extensions() is True
    assert opened == [["/snap/bin/chromium", "chrome://extensions"]]


def test_open_chrome_extensions_without_chrome(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    assert installer.open_chrome_extensions() is False


def systemd_verify(*units: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemd-analyze", "verify", *map(str, units)],
        capture_output=True,
        text=True,
    )


needs_systemd = pytest.mark.skipif(
    not shutil.which("systemd-analyze") or not Path(PYTHON).exists(),
    reason="needs systemd and /usr/bin/python3",
)


@needs_systemd
def test_systemd_accepts_the_scheduler_units(tmp_path, monkeypatch):
    schedules = tmp_path / "home dir" / ".blocker" / "schedules.json"
    schedules.parent.mkdir(parents=True)
    monkeypatch.setattr(installer, "SCHEDULES_FILE", schedules)
    texts = {
        "blocker-scheduler.service": installer._scheduler_service(PYTHON),
        "blocker-scheduler.timer": installer.SCHEDULER_TIMER,
        "blocker-scheduler.path": installer._scheduler_path_unit(),
    }
    for name, text in texts.items():
        (tmp_path / name).write_text(text)
    result = systemd_verify(*(tmp_path / name for name in texts))
    assert result.returncode == 0, result.stderr
    # Warnings don't fail verify, so look for them too.
    assert "blocker-scheduler" not in result.stderr, result.stderr


@needs_systemd
def test_systemd_accepts_the_sync_unit(tmp_path):
    unit = tmp_path / "blocker-sync.service"
    unit.write_text(installer._sync_unit())
    result = systemd_verify(unit)
    # verify checks ExecStart exists; a checkout without .venv lacks it.
    if not installer.VENV_BLOCKER_SYNC.exists():
        pytest.skip("no .venv/bin/blocker-sync in this checkout")
    assert result.returncode == 0, result.stderr
    assert "blocker-sync" not in result.stderr, result.stderr


@needs_systemd
def test_the_timer_fires_every_30_seconds():
    result = subprocess.run(
        ["systemd-analyze", "calendar", "--iterations=4", "*:*:00/30"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # "    Next elapse: Tue 2026-10-27 20:18:00 GMT", then "Iteration #2: ..."
    times = [
        datetime.strptime(" ".join(line.split()[-3:-1]), "%Y-%m-%d %H:%M:%S")
        for line in result.stdout.splitlines()
        if line.strip().startswith(("Next elapse", "Iteration"))
    ]
    assert len(times) == 4
    assert all(t.second in (0, 30) for t in times)
    assert {b - a for a, b in zip(times, times[1:])} == {timedelta(seconds=30)}


def test_odd_home_paths_stay_one_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "SCHEDULES_FILE", tmp_path / "a b%c" / "s.json")
    service = parse_unit(installer._scheduler_service(PYTHON).encode())
    assert service["Service"]["ExecStart"].endswith('/a b%%c/s.json"')


def test_user_units_follow_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert installer._xdg_dir("XDG_CONFIG_HOME", ".config") == tmp_path
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert installer._xdg_dir("XDG_CONFIG_HOME", ".config") == (Path.home() / ".config")
    assert os.environ.get("XDG_CONFIG_HOME") is None
