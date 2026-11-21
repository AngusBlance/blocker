# blocker

Site blocker for macOS, Ubuntu and Android.

- `macbook/`: the desktop app (macOS and Ubuntu), in Python (uv), plus the Chrome extension.
  - `blocklib/`: backend, blocks sites by editing `/etc/hosts`.
  - `tui/`: Textual app, the `block` command.
  - `extension/`: Chrome extension that syncs with the desktop app. `src/` is what Chrome loads; the rest is its own npm lint setup.
  - `tests/`: packaging tests.
- `android/`: Flutter and Kotlin.
  - `androidlib/`: Kotlin accessibility-service backend.
  - `android-flutter/`: the Flutter app, on the `androidlib` backend.

## macOS

```sh
cd macbook
uv tool install --editable ./tui
block install
```

`block install` sets up the sync agent and walks you through loading `macbook/extension/src` in Chrome.

## Ubuntu

The same app and the same steps; `block install` checks the OS and sets things up the Linux way:

```sh
cd macbook
uv tool install --editable ./tui
block install
```

That puts Block in the app menu, runs the sync daemon as a systemd user service (`blocker-sync.service`), and installs the schedule helper as root-owned systemd units (`blocker-scheduler.timer` and `.path`, logging to `journalctl -u blocker-scheduler`), so sudo asks for your password once. Built and tested on Ubuntu 24.04; focus also on 26.04 (GNOME 50, Wayland).

### Focus sessions

The TUI's **focus** section starts a session for 25 minutes to 2 hours: pick the sites and apps you still need, and until it ends:

- in Chrome, only those sites open; every other page (and any tab already open) goes to a focus page;
- only those apps can run; any other app is closed as it opens, with a notification.

It ends on time by itself, survives a restart, and ending it early needs the unlock password. Sites you've blocked stay blocked even if you allow them.

Always allowed, so focus can't break the desktop: Chrome itself (and web apps installed from it), Block, and your terminal with anything started from it. Apps that start at login (a tablet driver, say) come ticked in the allow list; untick one to have it closed too. Other browsers can't be allowed, since the extension only works in Chrome. Apps are closed by a user service, `blocker-focus-apps.service` (`journalctl --user -u blocker-focus-apps`), which `block install` sets up. It's a commitment device, not a lock: `systemctl --user stop blocker-focus-apps` turns it off, and an app started from a terminal isn't closed.

After updating: run `uv sync` in `macbook/` (it builds `blocker-focus-apps`), then `block install` again, and reload the extension at `chrome://extensions` (it now needs access to every site, to send pages away).

Focus is Ubuntu only for now; on macOS the TUI has no focus section yet.

## Android

**[Download blocker-flutter.apk](https://github.com/AngusBlance/blocker/releases/download/android-latest/blocker-flutter.apk)** ([release page](https://github.com/AngusBlance/blocker/releases/tag/android-latest))

Open the link on your phone and install the APK (allow your browser to install unknown apps if asked). Then open Blocker and follow the setup steps on its dashboard.

The APK is rebuilt on every change to `main` that touches `android/`, and new builds install over the old one.

## Development

CI runs these on every pull request and on `main`. To run them locally:

```sh
# macbook: Python (blocklib, tui)
cd macbook
uv run ruff check . && uv run ruff format --check .
(cd blocklib && uv run --all-packages pytest)
(cd tui && uv run --all-packages pytest)
uv run --all-packages pytest tests

# macbook: Chrome extension
cd macbook/extension && npm ci && npm run lint

# android: Flutter
cd android/android-flutter && flutter analyze && flutter test

# android: Kotlin, with ktlint installed
cd android && ktlint "androidlib/**/*.kt"
```

`uv run ruff format .`, `dart format lib test` and `ktlint --format` fix formatting.

Tests that edit the real `/etc/hosts` with sudo are skipped unless you set `RUN_LIVE_HOSTS_TESTS=1`.
