import os
import subprocess
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# the daemon's own declared entry point (blocklib's [project.scripts]), not
# a hand-rolled `python -m` invocation - same as Block.app calling `block`
# rather than reaching around it with a raw interpreter command
VENV_BLOCKER_SYNC = REPO_ROOT / ".venv" / "bin" / "blocker-sync"
# The loadable extension; extension/ itself also holds its lint tooling.
EXTENSION_DIR = REPO_ROOT / "extension" / "src"

APP_BUNDLE = Path.home() / "Applications" / "Block.app"
# overridable so integration tests can bootstrap a disposable, self-cleaning
# agent instead of touching the real com.angusblance.blocker-sync
LAUNCH_AGENT_LABEL = os.environ.get(
    "BLOCKER_LAUNCH_AGENT_LABEL", "com.angusblance.blocker-sync"
)
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)
LOGS_DIR = Path.home() / "Library" / "Logs"

LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/"
    "LaunchServices.framework/Versions/A/Support/lsregister"
)

INFO_PLIST = dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>CFBundleName</key>
        <string>Block</string>
        <key>CFBundleDisplayName</key>
        <string>Block</string>
        <key>CFBundleIdentifier</key>
        <string>com.angusblance.block</string>
        <key>CFBundleVersion</key>
        <string>1.0</string>
        <key>CFBundleShortVersionString</key>
        <string>1.0</string>
        <key>CFBundlePackageType</key>
        <string>APPL</string>
        <key>CFBundleExecutable</key>
        <string>block</string>
        <key>LSMinimumSystemVersion</key>
        <string>10.13</string>
    </dict>
    </plist>
    """)

LAUNCHER_SCRIPT = dedent("""\
    #!/bin/bash
    osascript <<'EOF'
    tell application "Terminal"
        activate
        do script "exec block"
    end tell
    EOF
    """)


def install_block_app() -> Path:
    """Creates/updates ~/Applications/Block.app so it's searchable in
    Spotlight/Launchpad. Its only job is opening a Terminal that runs the
    installed `block` command - no hardcoded repo paths."""
    macos_dir = APP_BUNDLE / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    (APP_BUNDLE / "Contents" / "Info.plist").write_text(INFO_PLIST)
    launcher = macos_dir / "block"
    launcher.write_text(LAUNCHER_SCRIPT)
    launcher.chmod(0o755)
    subprocess.run([LSREGISTER, "-f", str(APP_BUNDLE)], check=True)
    return APP_BUNDLE


def _sync_daemon_plist() -> str:
    return dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCH_AGENT_LABEL}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{VENV_BLOCKER_SYNC}</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{REPO_ROOT}</string>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>ThrottleInterval</key>
            <integer>10</integer>
            <key>StandardOutPath</key>
            <string>{LOGS_DIR / "blocker-sync.log"}</string>
            <key>StandardErrorPath</key>
            <string>{LOGS_DIR / "blocker-sync.err.log"}</string>
        </dict>
        </plist>
        """)


def install_sync_daemon() -> None:
    """Writes the LaunchAgent plist and (re)loads it so the sync daemon
    runs now and on every future login."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    was_already_installed = LAUNCH_AGENT_PLIST.exists()
    LAUNCH_AGENT_PLIST.write_text(_sync_daemon_plist())

    uid = os.getuid()
    if was_already_installed:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(LAUNCH_AGENT_PLIST)],
            capture_output=True,
        )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(LAUNCH_AGENT_PLIST)],
        check=True,
    )


def print_extension_instructions() -> None:
    print("\nChrome extension (one-time, manual step - Chrome requires this,")
    print("it won't let anything load an unpacked extension silently):")
    print(
        "  1. In the chrome://extensions tab that just opened, enable 'Developer mode'"
    )
    print("  2. Click 'Load unpacked' and select:")
    print(f"     {EXTENSION_DIR}")
    if not os.environ.get("BLOCKER_NO_OPEN_CHROME"):
        subprocess.run(
            ["open", "-a", "Google Chrome", "chrome://extensions"], check=False
        )


def install() -> None:
    bundle = install_block_app()
    print(f"Installed {bundle}")
    install_sync_daemon()
    print(f"Sync daemon installed and running ({LAUNCH_AGENT_LABEL})")
    print_extension_instructions()


if __name__ == "__main__":
    install()
