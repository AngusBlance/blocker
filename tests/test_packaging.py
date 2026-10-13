"""Builds the real wheels from scratch and installs them into a totally
isolated venv - proves blocklib and blocker-tui actually work together as
distributable artifacts, not just via the dev workspace's editable shortcuts.

Safe to run anytime: everything happens in tmp_path, nothing touches the
real .venv, ~/.local, ~/Applications, or launchd.
"""

import os
import signal
import subprocess
import time
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_wheel(package: str, dist_dir: Path) -> Path:
    subprocess.run(
        ["uv", "build", "--package", package, "-o", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(dist_dir.glob(f"{package.replace('-', '_')}-*-py3-none-any.whl"))
    assert len(wheels) == 1, f"expected exactly one {package} wheel, found {wheels}"
    return wheels[0]


@pytest.fixture(scope="module")
def built_wheels(tmp_path_factory):
    dist_dir = tmp_path_factory.mktemp("dist")
    return {
        "blocklib": _build_wheel("blocklib", dist_dir),
        "blocker-tui": _build_wheel("blocker-tui", dist_dir),
    }


def test_blocklib_wheel_has_the_real_package_and_no_stray_top_level_modules(built_wheels):
    with zipfile.ZipFile(built_wheels["blocklib"]) as z:
        names = z.namelist()

    assert "blocklib/__init__.py" in names
    assert "blocklib/core.py" in names
    assert "blocklib/sync_daemon.py" in names
    # a bad [tool.hatch.build...] config could leak a flat top-level module
    # instead of a real package - this is exactly the mistake fixed earlier
    stray_top_level_py = [n for n in names if n.endswith(".py") and "/" not in n]
    assert stray_top_level_py == []


def test_blocker_tui_wheel_has_the_real_package_and_console_script(built_wheels):
    with zipfile.ZipFile(built_wheels["blocker-tui"]) as z:
        names = z.namelist()
        entry_points_name = next(n for n in names if n.endswith("entry_points.txt"))
        entry_points = z.read(entry_points_name).decode()

    assert "blocker_tui/__init__.py" in names
    assert "blocker_tui/app.py" in names
    assert "blocker_tui/installer.py" in names
    assert "block = blocker_tui.app:main" in entry_points


@pytest.fixture(scope="module")
def installed_venv(built_wheels, tmp_path_factory):
    """A venv containing only the two local wheels plus whatever they
    declare as real dependencies - nothing from the dev workspace."""
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
            str(built_wheels["blocklib"]),
            str(built_wheels["blocker-tui"]),
        ],
        check=True,
        capture_output=True,
    )
    return venv_dir


def test_block_command_runs_from_a_totally_fresh_install(installed_venv):
    result = subprocess.run(
        [str(installed_venv / "bin" / "block"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage: block" in result.stdout


def test_block_command_rejects_unknown_args_from_a_fresh_install(installed_venv):
    result = subprocess.run(
        [str(installed_venv / "bin" / "block"), "bogus"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "usage: block" in result.stdout


def test_blocker_sync_console_script_also_works_from_the_fresh_install(installed_venv):
    # blocklib's own entry point, used by the launchd daemon - proves the
    # two packages' entry points don't collide and both actually resolve.
    # Uses an ephemeral port (not DEFAULT_WS_PORT) so this never competes
    # with the real daemon that may already be running on this machine.
    env = dict(os.environ, BLOCKER_SYNC_PORT="0")
    proc = subprocess.Popen(
        [str(installed_venv / "bin" / "blocker-sync")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.5)
        still_running = proc.poll() is None
        if not still_running:
            pytest.fail(f"blocker-sync exited immediately: {proc.stderr.read()}")
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
