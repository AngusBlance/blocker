"""installer.py: picking this OS's installer, and the steps every OS
shares."""

import sys
import types
from pathlib import Path

import pytest

from blocker_tui import installer, installer_linux, installer_macos


@pytest.mark.parametrize(
    "platform, module",
    [("darwin", installer_macos), ("linux", installer_linux)],
)
def test_this_os_picks_the_installer_for_the_platform(monkeypatch, platform, module):
    monkeypatch.setattr(sys, "platform", platform)
    assert installer.this_os() is module


def test_other_oses_are_refused_by_name(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(installer.UnsupportedOS, match="win32"):
        installer.this_os()
    # The TUI still runs there; it just shows schedules as not installed.
    assert installer.scheduler_installed() is False


def fake_os(calls, scheduler_error=None):
    def scheduler():
        calls.append("scheduler")
        if scheduler_error:
            raise scheduler_error

    def open_chrome():
        calls.append("chrome")
        return True

    return types.SimpleNamespace(
        install_launcher=lambda: calls.append("launcher") or "/apps/Block",
        install_sync_daemon=lambda: calls.append("sync"),
        install_scheduler=scheduler,
        open_chrome_extensions=open_chrome,
        SYNC_NAME="sync-unit",
        SCHEDULER_NAME="scheduler-unit",
    )


def test_install_runs_every_step_of_this_oss_installer(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(installer, "this_os", lambda: fake_os(calls))
    monkeypatch.delenv("BLOCKER_NO_SCHEDULER", raising=False)
    monkeypatch.delenv("BLOCKER_NO_OPEN_CHROME", raising=False)

    installer.install()

    assert calls == ["launcher", "sync", "scheduler", "chrome"]
    out = capsys.readouterr().out
    assert "Installed /apps/Block" in out
    assert "(sync-unit)" in out
    assert "Schedule helper installed and running (scheduler-unit)" in out
    assert "tab that just opened" in out


def test_install_carries_on_without_the_scheduler(monkeypatch, capsys):
    calls = []
    error = RuntimeError("no python")
    monkeypatch.setattr(installer, "this_os", lambda: fake_os(calls, error))
    monkeypatch.delenv("BLOCKER_NO_SCHEDULER", raising=False)
    monkeypatch.setenv("BLOCKER_NO_OPEN_CHROME", "1")

    installer.install()

    assert calls == ["launcher", "sync", "scheduler"]
    out = capsys.readouterr().out
    assert "Schedule helper NOT installed: no python" in out
    assert str(installer.EXTENSION_DIR) in out


def test_install_sets_up_focus_apps_where_the_os_has_it(monkeypatch, capsys):
    calls = []
    platform = fake_os(calls)
    platform.install_focus_apps = lambda: calls.append("focus apps")
    platform.FOCUS_APPS_NAME = "focus-unit"
    monkeypatch.setattr(installer, "this_os", lambda: platform)
    monkeypatch.setenv("BLOCKER_NO_SCHEDULER", "1")
    monkeypatch.setenv("BLOCKER_NO_OPEN_CHROME", "1")

    installer.install()

    assert calls == ["launcher", "sync", "focus apps"]
    assert "(focus-unit)" in capsys.readouterr().out


def test_install_says_so_when_the_focus_app_closer_cant_go_in(monkeypatch, capsys):
    calls = []
    platform = fake_os(calls)

    def fails():
        raise RuntimeError("run `uv sync`")

    platform.install_focus_apps = fails
    platform.FOCUS_APPS_NAME = "focus-unit"
    monkeypatch.setattr(installer, "this_os", lambda: platform)
    monkeypatch.setenv("BLOCKER_NO_SCHEDULER", "1")
    monkeypatch.setenv("BLOCKER_NO_OPEN_CHROME", "1")

    installer.install()

    out = capsys.readouterr().out
    assert (
        "Focus app closer NOT installed (focus won't close apps): run `uv sync`" in out
    )
    assert "installed and running (focus-unit)" not in out


def test_the_macs_installer_has_no_focus_app_closer():
    from blocker_tui import installer_macos

    assert not hasattr(installer_macos, "install_focus_apps")


def test_install_can_skip_the_scheduler(monkeypatch):
    calls = []
    monkeypatch.setattr(installer, "this_os", lambda: fake_os(calls))
    monkeypatch.setenv("BLOCKER_NO_SCHEDULER", "1")
    monkeypatch.setenv("BLOCKER_NO_OPEN_CHROME", "1")
    installer.install()
    assert calls == ["launcher", "sync"]


def test_print_extension_instructions_points_at_the_real_extension_dir(
    monkeypatch, capsys
):
    monkeypatch.delenv("BLOCKER_NO_OPEN_CHROME", raising=False)

    installer.print_extension_instructions(lambda: True)

    out = capsys.readouterr().out
    assert str(installer.EXTENSION_DIR) in out
    assert "Developer mode" in out
    # Chrome needs the folder holding manifest.json, not the one with node_modules.
    assert (installer.EXTENSION_DIR / "manifest.json").is_file()


def test_extension_instructions_without_chrome_say_where_to_go(monkeypatch, capsys):
    monkeypatch.delenv("BLOCKER_NO_OPEN_CHROME", raising=False)
    installer.print_extension_instructions(lambda: False)
    out = capsys.readouterr().out
    assert "Open chrome://extensions in Chrome" in out
    assert "just opened" not in out


def test_the_interpreter_must_be_root_only(tmp_path):
    # A python the user owns (this test's own venv) is refused.
    user_python = tmp_path / "python3"
    user_python.symlink_to(sys.executable)
    with pytest.raises(RuntimeError, match="root-only"):
        installer.resolve_root_python(user_python, "missing")
    with pytest.raises(RuntimeError, match="no python here"):
        installer.resolve_root_python(tmp_path / "missing", "no python here")


def test_the_allowlist_holds_the_known_sites_and_nothing_else():
    allowed = installer.allowlist_text().split()
    assert "youtube.com" in allowed and "www.tiktok.com" in allowed
    assert not any("apple.com" in a or "ubuntu.com" in a for a in allowed)


def test_root_owned_symlinks_count_as_root_only():
    # /usr/bin/python3 on Ubuntu is a root-owned symlink, shown as 0777.
    usr_bin = Path("/usr/bin")
    links = [p for p in usr_bin.glob("python3*") if p.is_symlink()]
    if not links or links[0].lstat().st_uid != 0:
        pytest.skip("no root-owned python3 symlink in /usr/bin")
    assert installer._root_only(links[0])


def test_a_user_owned_symlink_isnt_root_only(tmp_path):
    link = tmp_path / "python3"
    link.symlink_to("/usr/bin/env")
    assert not installer._root_only(link)
