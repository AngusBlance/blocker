# blocker

Site blocker for macOS (`blocklib/`, `tui/`, `extension/`) and Android (`androidlib/`, `android-mobile/`).

## Android

**[Download blocker.apk](https://github.com/AngusBlance/blocker/releases/download/android-latest/blocker.apk)** ([release page](https://github.com/AngusBlance/blocker/releases/tag/android-latest))

1. Open the link on your phone and install the APK (allow your browser to install unknown apps if asked).
2. In Blocker, go to **settings → agree and open settings** and turn on **Blocker**.
3. If the switch is greyed out, go to **Settings → Apps → Blocker → ⋮ → Allow restricted settings** and try again.

The APK is rebuilt on every push that changes the app, and new builds install over the old one.

## Development

CI runs these on every pull request and on `main`. To run them locally:

```sh
# Python (blocklib, tui)
uv run ruff check . && uv run ruff format --check .
(cd blocklib && uv run --all-packages pytest)
(cd tui && uv run --all-packages pytest)
uv run --all-packages pytest tests

# JS/TS (android-mobile, androidlib, extension)
npx eslint . && npx prettier --check .
npx tsc --noEmit -p android-mobile && npx tsc --noEmit -p androidlib

# Kotlin (androidlib), with ktlint installed
ktlint "androidlib/**/*.kt"
```

`uv run ruff format .`, `npx prettier --write .` and `ktlint --format` fix formatting.

Tests that edit the real `/etc/hosts` with sudo are skipped unless you set `RUN_LIVE_HOSTS_TESTS=1`.
