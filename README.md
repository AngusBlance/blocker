# blocker

Site blocker for macOS and Android.

- `macbook/`: Python (uv), plus the Chrome extension.
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
