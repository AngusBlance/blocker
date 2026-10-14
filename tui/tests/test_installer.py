import os

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
