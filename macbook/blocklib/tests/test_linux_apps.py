"""Focus mode's app half on Linux: which apps are installed, which unit each
running process is in, and which of them focus closes. Uses fake /proc and
.desktop folders, so it runs anywhere (the module only touches the real
system in stop_unit and notify, which are swapped out here)."""

import json
from pathlib import Path

import pytest

from blocklib import focus as focus_mode
from blocklib import linux_apps as la
from blocklib.focus import AllowedApp, Focus

NOW = 1_760_000_000_000
HOUR = 3_600_000
UID = 1000
APP_SLICE = f"/user.slice/user-{UID}.slice/user@{UID}.service/app.slice"


def desktop(name, extra=""):
    return f"[Desktop Entry]\nType=Application\nName={name}\nExec=x\n{extra}"


@pytest.fixture(autouse=True)
def no_real_system_dirs(monkeypatch):
    monkeypatch.setattr(la, "EXTRA_DATA_DIRS", ())


@pytest.fixture
def system(tmp_path):
    """A home and system folders with a handful of apps, as on Ubuntu."""
    home = tmp_path / "home"
    usr = tmp_path / "usr/share/applications"
    snap = tmp_path / "snap/applications"
    xdg = tmp_path / "etc/xdg/autostart"
    user_apps = home / ".local/share/applications"
    user_autostart = home / ".config/autostart"
    for d in (usr, snap, xdg, user_apps, user_autostart):
        d.mkdir(parents=True)
    (usr / "org.gnome.TextEditor.desktop").write_text(
        desktop("Text Editor", "Categories=GNOME;Utility;\n")
    )
    (usr / "google-chrome.desktop").write_text(
        desktop("Google Chrome", "Categories=Network;WebBrowser;\n")
    )
    (usr / "org.gnome.Ptyxis.desktop").write_text(
        desktop("Ptyxis", "Categories=System;TerminalEmulator;\n")
    )
    (usr / "xppentablet.desktop").write_text(desktop("xppentablet"))
    (usr / "org.gnome.Evolution-alarm-notify.desktop").write_text(
        desktop("Evolution Alarm Notify", "NoDisplay=true\n")
    )
    (snap / "firefox_firefox.desktop").write_text(
        desktop("Firefox", "Categories=Network;WebBrowser;\n")
    )
    (snap / "obsidian_obsidian.desktop").write_text(desktop("Obsidian"))
    (snap / "discord_discord.desktop").write_text(desktop("Discord"))
    (user_apps / "Beeper.desktop").write_text(desktop("Beeper"))
    (user_apps / "beeper.desktop").write_text(desktop("Beeper"))
    (user_apps / "block.desktop").write_text(desktop("Block", "Terminal=true\n"))
    # The user hid the system's Text Editor? No: hid a different one.
    (user_apps / "org.gnome.Characters.desktop").write_text(
        desktop("Characters", "Hidden=true\n")
    )
    (usr / "org.gnome.Characters.desktop").write_text(desktop("Characters"))
    (xdg / "xppentablet.desktop").write_text(desktop("xppentablet"))
    (xdg / "org.gnome.Evolution-alarm-notify.desktop").write_text(desktop("x"))
    # A web app installed from Chrome ("Install page as app").
    (user_apps / "chrome-abcdefghijklmnopabcdefghijklmnop-Default.desktop").write_text(
        desktop("YouTube")
    )
    (xdg / "kde-only.desktop").write_text(desktop("KDE thing", "OnlyShowIn=KDE;\n"))
    (xdg / "not-gnome.desktop").write_text(desktop("Not here", "NotShowIn=GNOME;\n"))
    (xdg / "turned-off.desktop").write_text(
        desktop("Off", "X-GNOME-Autostart-enabled=false\n")
    )
    env = {
        "HOME": str(home),
        "XDG_DATA_DIRS": f"{tmp_path / 'usr/share'}:{tmp_path / 'snap'}",
        "XDG_CONFIG_DIRS": str(tmp_path / "etc/xdg"),
    }
    return env


class Proc:
    """A fake /proc: add(pid, unit, tty=0)."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(exist_ok=True)

    def add(self, pid, unit, tty=0, cgroup=None, comm="app", ppid=1):
        d = self.root / str(pid)
        d.mkdir()
        (d / "cgroup").write_text(cgroup or f"0::{APP_SLICE}/{unit}\n")
        # pid (comm) state ppid pgrp session tty_nr ...
        (d / "stat").write_text(
            f"{pid} ({comm}) S {ppid} {pid} {pid} {tty} -1 4194560\n"
        )


@pytest.fixture
def proc(tmp_path):
    return Proc(tmp_path / "proc")


# Installed apps


def test_installed_apps_are_the_menu_ones_by_desktop_id(system):
    apps = la.installed_apps(la.application_dirs(system))
    assert apps["org.gnome.TextEditor"].name == "Text Editor"
    assert apps["firefox_firefox"].browser
    assert apps["org.gnome.Ptyxis"].terminal
    assert "org.gnome.Evolution-alarm-notify" not in apps  # NoDisplay
    # Hidden in the user's folder hides the system's copy too.
    assert "org.gnome.Characters" not in apps


def test_desktop_ids_in_subfolders_join_with_dashes(tmp_path):
    (tmp_path / "applications/kde").mkdir(parents=True)
    (tmp_path / "applications/kde/konsole.desktop").write_text(desktop("Konsole"))
    assert "kde-konsole" in la.installed_apps([tmp_path / "applications"])


def test_translated_names_and_other_groups_dont_win(tmp_path):
    text = (
        "[Desktop Entry]\nName[fr]=Éditeur\nName=Editor\nType=Application\n"
        "[Desktop Action new]\nName=New Window\n"
    )
    assert la.parse_desktop_entry(text)["Name"] == "Editor"


GNOME = {"ubuntu", "GNOME"}


def test_autostart_ids_skip_switched_off_entries_and_other_desktops(system):
    ids = la.autostart_ids(la.autostart_dirs(system), GNOME)
    assert {"xppentablet", "org.gnome.Evolution-alarm-notify"} <= ids
    assert not {"turned-off", "kde-only", "not-gnome"} & ids
    assert "kde-only" in la.autostart_ids(la.autostart_dirs(system), {"KDE"})


def test_current_desktops_come_from_the_environment():
    assert la.current_desktops({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == GNOME
    assert la.current_desktops({}) == set()


def test_the_tui_offers_apps_but_not_browsers_or_always_allowed_ones(system):
    apps = la.installed_apps(la.application_dirs(system))
    names = [a.name for a in la.choosable(apps)]
    # Not Chrome, its web app, Firefox, the terminal or Block.
    assert names == ["Beeper", "Discord", "Obsidian", "Text Editor", "xppentablet"]


def test_apps_that_start_at_login_are_the_ones_the_tui_ticks(system):
    choices = la.choosable(la.installed_apps(la.application_dirs(system)))
    autostart = la.autostart_ids(la.autostart_dirs(system), GNOME)
    assert [a.name for a in la.at_login(choices, autostart)] == ["xppentablet"]


# Units


@pytest.mark.parametrize(
    "unit, app_id",
    [
        ("app-gnome-org.gnome.TextEditor-4242.scope", "org.gnome.TextEditor"),
        ("app-gnome-google\\x2dchrome-517608.scope", "google-chrome"),
        ("app-com.google.Chrome-517608.scope", "com.google.Chrome"),
        ("app-Beeper-591410.scope", "Beeper"),
        ("app-flatpak-org.vinegarhq.Sober-77.scope", "org.vinegarhq.Sober"),
        ("app-gnome-org.gnome.Nautilus@3f2a.service", "org.gnome.Nautilus"),
        ("app-org.gnome.Nautilus.service", "org.gnome.Nautilus"),
        (
            "snap.obsidian.obsidian-62f4d583-939e-46f2-a990-bbd45b3b76bd.scope",
            "obsidian_obsidian",
        ),
        (
            "snap.anki-desktop.anki-desktop-4a7d0c3f-abfd-4cd8-a9cc-7e3d86ccb72f.scope",
            "anki-desktop_anki-desktop",
        ),
        ("snap.firmware-updater.firmware-notifier.service", None),
        ("vte-spawn-0c4b4f0c-3c3e-4b3a-9c2a-1d2e3f4a5b6c.scope", None),
        ("org.gnome.Shell@wayland.service", None),
        ("app-4242.scope", None),
        ("app.slice", None),
        ("blocker-sync.service", None),
    ],
)
def test_units_name_the_app_they_were_started_for(unit, app_id):
    assert la.unit_app_id(unit) == app_id


def test_running_units_reads_proc_and_marks_terminal_ones(proc):
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    # nvim started from a terminal (its parent, the shell, is outside the
    # unit): its server and clangd start new sessions with no tty, as on
    # the owner's machine, but it still counts as in a terminal.
    nvim = "snap.nvim.nvim-9093939c-c60c-4f21-ab9a-4f28a1970f21.scope"
    proc.add(11, nvim, tty=34817, ppid=500)
    proc.add(15, nvim, ppid=11)
    proc.add(16, nvim, comm="clangd.main", ppid=15)
    # VS Code with its terminal open: the shell (inside the unit) has a tty,
    # VS Code itself doesn't, so focus can close it.
    proc.add(12, "app-gnome-code-12.scope", ppid=1)
    proc.add(13, "app-gnome-code-12.scope", tty=34816, ppid=12)
    # A command name with spaces and brackets doesn't throw the fields off.
    proc.add(14, "app-Beeper-14.scope", comm="Beeper (renderer) x")
    # Someone else's, the system's, and a cgroup an app made inside its unit.
    proc.add(
        20,
        "",
        cgroup="0::/user.slice/user-1001.slice/user@1001.service/app.slice/app-x-1.scope\n",
    )
    proc.add(21, "", cgroup="0::/system.slice/cron.service\n")
    proc.add(22, "", cgroup=f"0::{APP_SLICE}/app-flatpak-org.x.Y-22.scope/inner\n")
    (proc.root / "self").mkdir()
    units = la.running_units(proc.root, uid=UID)
    assert units == {
        "app-gnome-org.gnome.TextEditor-10.scope": False,
        nvim: True,
        "app-gnome-code-12.scope": False,
        "app-Beeper-14.scope": False,
        "app-flatpak-org.x.Y-22.scope": False,
    }


def test_a_process_that_exits_mid_read_is_skipped(proc):
    (proc.root / "99").mkdir()  # no cgroup file: it's gone
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    assert list(la.running_units(proc.root, uid=UID)) == [
        "app-gnome-org.gnome.TextEditor-10.scope"
    ]


# Deciding


@pytest.fixture
def installed(system):
    return la.installed_apps(la.application_dirs(system))


def closed(apps, units, allowed=()):
    return [unit for unit, _ in la.to_close(units, apps, allowed)]


def test_focus_closes_apps_it_doesnt_allow_and_keeps_allowed_ones(installed):
    units = {
        "app-gnome-org.gnome.TextEditor-10.scope": False,
        "snap.obsidian.obsidian-62f4d583-939e-46f2-a990-bbd45b3b76bd.scope": False,
        "snap.discord.discord-11111111-2222-3333-4444-555555555555.scope": False,
    }
    assert closed(installed, units, ["obsidian_obsidian"]) == [
        "app-gnome-org.gnome.TextEditor-10.scope",
        "snap.discord.discord-11111111-2222-3333-4444-555555555555.scope",
    ]


def test_never_closes_what_keeps_the_desktop_and_block_working(installed):
    units = {
        "app-gnome-google\\x2dchrome-1.scope": False,  # Chrome: sites filtered
        "app-com.google.Chrome-1.scope": False,  # no menu entry
        "app-gnome-org.gnome.Ptyxis-2.scope": False,  # a terminal
        "app-gnome-block-3.scope": False,  # Block
        # A Chrome web app: Chrome can start inside its unit.
        "app-gnome-chrome\\x2dabcdefghijklmnopabcdefghijklmnop\\x2dDefault-4.scope": False,
        "app-gnome-org.gnome.Evolution\\x2dalarm\\x2dnotify-5.scope": False,
        "app-gnome-org.gnome.TextEditor-6.scope": True,  # in a terminal
        "app-gnome-something.unknown-7.scope": False,  # not an app we know
        "blocker-focus-apps.service": False,
    }
    assert closed(installed, units) == []


def test_apps_that_start_at_login_close_unless_allowed(installed):
    # Not spared by the enforcer: the TUI ticks them, so they're allowed
    # unless someone unticks them (a Discord set to open on startup).
    units = {"app-gnome-xppentablet-4.scope": False}
    assert closed(installed, units) == list(units)
    assert closed(installed, units, ["xppentablet"]) == []


def test_other_browsers_close_even_if_allowed(installed):
    units = {"snap.firefox.firefox-11111111-2222-3333-4444-555555555555.scope": False}
    assert closed(installed, units, ["firefox_firefox"]) == list(units)


def test_allowing_an_app_matches_its_units_whatever_their_case(installed):
    units = {"app-Beeper-1.scope": False, "app-gnome-beeper-1.scope": False}
    assert closed(installed, units, ["beeper"]) == []
    assert closed(installed, units, []) == sorted(units)


# The enforcer


class Recorder:
    def __init__(self):
        self.stopped = []
        self.notified = []

    def stop(self, unit):
        self.stopped.append(unit)

    def notify(self, app, ends_at):
        self.notified.append((app.name, ends_at))


def start_focus(path, apps=(), ends_at=NOW + HOUR):
    focus_mode.save_start(
        Focus(ends_at, ("Udemy",), ("udemy.com",), tuple(apps)), path, NOW
    )


def make_enforcer(tmp_path, system, proc, rec, clock=lambda: 0.0):
    return la.Enforcer(
        focus_file=tmp_path / "focus.json",
        proc=proc.root,
        env=system,
        stop=rec.stop,
        notify=rec.notify,
        clock=clock,
    )


def test_enforcer_does_nothing_without_focus(tmp_path, system, proc):
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    rec = Recorder()
    enforcer = make_enforcer(tmp_path, system, proc, rec)
    assert enforcer.check(NOW) == []
    assert rec.stopped == []


def test_enforcer_closes_and_notifies_during_focus_and_stops_when_it_ends(
    tmp_path, system, proc, monkeypatch
):
    monkeypatch.setattr(la.os, "getuid", lambda: UID)
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    proc.add(11, "snap.obsidian.obsidian-62f4d583-939e-46f2-a990-bbd45b3b76bd.scope")
    start_focus(tmp_path / "focus.json", [AllowedApp("obsidian_obsidian", "Obsidian")])
    rec = Recorder()
    enforcer = make_enforcer(tmp_path, system, proc, rec)
    enforcer.check(NOW + 1000)
    assert rec.stopped == ["app-gnome-org.gnome.TextEditor-10.scope"]
    assert rec.notified == [("Text Editor", NOW + HOUR)]
    # Reopened straight away: closed again, but not notified again yet.
    enforcer.check(NOW + 2000)
    assert rec.stopped == ["app-gnome-org.gnome.TextEditor-10.scope"] * 2
    assert len(rec.notified) == 1
    # Once focus is over, nothing is closed.
    enforcer.check(NOW + HOUR)
    assert len(rec.stopped) == 2


def test_enforcer_notifies_again_after_a_while(tmp_path, system, proc, monkeypatch):
    monkeypatch.setattr(la.os, "getuid", lambda: UID)
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    start_focus(tmp_path / "focus.json")
    now = [0.0]
    rec = Recorder()
    enforcer = make_enforcer(tmp_path, system, proc, rec, clock=lambda: now[0])
    enforcer.check(NOW + 1)
    now[0] = la.NOTIFY_EVERY_SECONDS
    enforcer.check(NOW + 2)
    assert len(rec.notified) == 2


def test_enforcer_survives_a_broken_focus_file(tmp_path, system, proc):
    (tmp_path / "focus.json").write_text(json.dumps({"endsAt": "soon"}))
    proc.add(10, "app-gnome-org.gnome.TextEditor-10.scope")
    rec = Recorder()
    assert make_enforcer(tmp_path, system, proc, rec).check(NOW) == []


def test_run_keeps_going_after_an_error(monkeypatch):
    import threading

    stop = threading.Event()
    calls = []

    class Flaky:
        def check(self):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            stop.set()

    la.run(Flaky(), stop, poll=0)
    assert len(calls) == 2
