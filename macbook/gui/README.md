# blocker gui

Desktop app for the blocker, built with PySide6 (Qt). Same `blocklib` backend
and look as the TUI, in a real window.

```sh
cd macbook/gui
uv run blocker-gui
```

- **dashboard**: blocked or open at a glance, "block everything", and a tile per site.
- **sites**: a switch per site. Turning one off asks for the unlock password, typed by hand (paste is off).
- Blocking edits `/etc/hosts`, so the app asks for your Mac password when sudo needs it. It's passed straight to `sudo` and not stored.
- Changes made elsewhere (the TUI, the terminal) show up live.

The UI runs on macOS, Windows and Linux, but blocking only works on macOS for now, because `blocklib` is macOS-only.

This is its own uv project (not a member of the `macbook/` workspace) with `blocklib` as a path dependency.

```sh
uv run pytest            # headless, against a temporary hosts file
uv run ruff check . && uv run ruff format --check .
```
