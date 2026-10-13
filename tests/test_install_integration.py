"""Exercises `block install`'s real OS side effects end to end: a fresh
editable install in an isolated venv, then the actual Block.app bundle
creation and a real (but disposable, self-cleaning) launchd agent.

NOT run by default - set RUN_PACKAGING_INTEGRATION_TESTS=1 to opt in.
Unlike test_packaging.py, this genuinely talks to launchd and the Launch
Services database, even though it's sandboxed behind a fake $HOME and a
throwaway agent label so it can never collide with (or be mistaken for)
the real com.angusblance.blocker-sync agent.
"""

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_PACKAGING_INTEGRATION_TESTS"),
    reason="touches real launchd/Launch Services - opt in with RUN_PACKAGING_INTEGRATION_TESTS=1",
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
    )

    try:
        first = subprocess.run(
            [str(editable_venv / "bin" / "block"), "install"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        second = subprocess.run(
            [str(editable_venv / "bin" / "block"), "install"],
            capture_output=True, text=True, env=env, timeout=30,
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
