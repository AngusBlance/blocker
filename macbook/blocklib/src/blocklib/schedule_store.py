"""Where the Mac keeps schedules: ~/.blocker/schedules.json, written by the
user (the TUI) and read by the root helper that applies them."""

from .password import CONFIG_DIR

SCHEDULES_FILE = CONFIG_DIR / "schedules.json"
