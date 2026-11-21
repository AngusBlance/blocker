"""Exercises `block install`'s real OS side effects end to end: a fresh
editable install in an isolated venv, then the actual launcher and a real
(but disposable, self-cleaning) sync daemon - a launchd agent and Block.app
on macOS, a systemd user service and a .desktop entry on Linux.

NOT run by default - set RUN_PACKAGING_INTEGRATION_TESTS=1 to opt in.
Unlike test_packaging.py, this genuinely talks to launchd / systemd, even
though it's sandboxed behind a fake $HOME and a throwaway agent or unit
name so it can never collide with (or be mistaken for) the real
blocker-sync. The root schedule helper is left out: it needs sudo.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_PACKAGING_INTEGRATION_TESTS"),
    reason="touches real launchd/systemd - opt in with RUN_PACKAGING_INTEGRATION_TESTS=1",
)
macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux only"
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def editable_venv(tmp_path_factory):
    """Editable (not wheel) install, matching the real install instructions
    (`uv tool install --editable ./tui`) - installer.py's REPO_ROOT
    discovery only works when the source tree is the real one, not a copy
    inside site-packages, so this has to be editable to be meaningful."""
    venv_dir = tmp_path_factory.mktemp("venv")
    subprocess.run(
        ["uv", "venv", str(venv_dir), "--no-project"], check=True, capture_output=True
    )
    python = venv_dir / "bin" / "python"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "-e",
            str(REPO_ROOT / "blocklib"),
            "-e",
            str(REPO_ROOT / "tui"),
        ],
        check=True,
        capture_output=True,
    )
    return venv_dir


@macos_only
def test_block_install_creates_a_real_app_bundle_and_self_cleaning_daemon(
    editable_venv, tmp_path
):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    label = f"com.angusblance.blocker-sync-test-{os.getpid()}"
    uid = os.getuid()
    plist = fake_home / "Library" / "LaunchAgents" / f"{label}.plist"

    env = dict(
        os.environ,
        HOME=str(fake_home),
        BLOCKER_LAUNCH_AGENT_LABEL=label,
        BLOCKER_NO_OPEN_CHROME="1",
        BLOCKER_NO_SCHEDULER="1",  # needs sudo
    )

    try:
        result = subprocess.run(
            [str(editable_venv / "bin" / "block"), "install"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

        bundle = fake_home / "Applications" / "Block.app"
        assert (bundle / "Contents" / "Info.plist").read_text().count("Block") >= 1
        launcher = bundle / "Contents" / "MacOS" / "block"
        assert "exec block" in launcher.read_text()
        assert os.access(launcher, os.X_OK)

        assert plist.exists()
        assert label in plist.read_text()

        status = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
        )
        assert "state = running" in status.stdout
    finally:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(plist)],
            capture_output=True,
        )


@macos_only
def test_block_install_is_idempotent(editable_venv, tmp_path):
    """Running install twice (e.g. after a code update) should cleanly
    reload rather than erroring on an already-loaded agent."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    label = f"com.angusblance.blocker-sync-test-{os.getpid()}-idempotent"
    uid = os.getuid()
    plist = fake_home / "Library" / "LaunchAgents" / f"{label}.plist"

    env = dict(
        os.environ,
        HOME=str(fake_home),
        BLOCKER_LAUNCH_AGENT_LABEL=label,
        BLOCKER_NO_OPEN_CHROME="1",
        BLOCKER_NO_SCHEDULER="1",  # needs sudo
    )

    try:
        first = subprocess.run(
            [str(editable_venv / "bin" / "block"), "install"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        second = subprocess.run(
            [str(editable_venv / "bin" / "block"), "install"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr

        status = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
        )
        assert "state = running" in status.stdout
    finally:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(plist)],
            capture_output=True,
        )


def _linux_env(fake_home: Path, unit: str, focus_unit: str) -> dict:
    env = dict(
        os.environ,
        HOME=str(fake_home),
        # systemd only reads user units from the real config folder, so
        # the throwaway unit goes there; everything else goes in fake_home
        XDG_CONFIG_HOME=str(Path.home() / ".config"),
        BLOCKER_SYNC_UNIT=unit,
        BLOCKER_FOCUS_APPS_UNIT=focus_unit,
        BLOCKER_NO_OPEN_CHROME="1",
        BLOCKER_NO_SCHEDULER="1",  # needs sudo
    )
    env.pop("XDG_DATA_HOME", None)
    return env


def _remove_user_unit(unit: str) -> None:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", f"{unit}.service"],
        capture_output=True,
    )
    (Path.home() / ".config" / "systemd" / "user" / f"{unit}.service").unlink(
        missing_ok=True
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)


def _wait_until_active(unit: str) -> str:
    state = ""
    for _ in range(20):
        state = subprocess.run(
            ["systemctl", "--user", "is-active", f"{unit}.service"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if state == "active":
            break
        time.sleep(0.25)
    return state


@linux_only
@pytest.mark.parametrize("runs", [1, 2], ids=["fresh", "reinstall"])
def test_block_install_creates_a_desktop_entry_and_a_running_user_service(
    editable_venv, tmp_path, runs
):
    """And running it again (e.g. after a code update) restarts the
    service rather than erroring."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    unit = f"blocker-sync-test-{os.getpid()}-{runs}"
    focus_unit = f"blocker-focus-apps-test-{os.getpid()}-{runs}"
    env = _linux_env(fake_home, unit, focus_unit)

    try:
        for _ in range(runs):
            result = subprocess.run(
                [str(editable_venv / "bin" / "block"), "install"],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            assert result.returncode == 0, result.stdout + result.stderr

        entry = fake_home / ".local" / "share" / "applications" / "block.desktop"
        assert "Terminal=true" in entry.read_text()
        assert f"{unit}.service" in result.stdout
        assert _wait_until_active(unit) == "active"
        enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", f"{unit}.service"],
            capture_output=True,
            text=True,
        )
        assert enabled.stdout.strip() == "enabled"
        assert f"{focus_unit}.service" in result.stdout
        assert _wait_until_active(focus_unit) == "active"
    finally:
        _remove_user_unit(unit)
        _remove_user_unit(focus_unit)
