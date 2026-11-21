"""Focus mode on the Mac: until it ends, only the allowed sites can be open in
Chrome. The extension enforces it (an allow list can't be done in
/etc/hosts, which can only block names); this is the model and the store,
~/.blocker/focus.json, written by the TUI and sent to the extension by the
sync server.

Ending early needs the unlock password, like ending a schedule early (D1).
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from .password import CONFIG_DIR
from .schedule_helper import valid_hostname
from .schedule_store import write_text

FOCUS_FILE = CONFIG_DIR / "focus.json"
MAX_MS = 12 * 60 * 60 * 1000

# Sites people focus on that need more than one domain to work: Google Docs
# signs in on accounts.google.com. Only the pages you open are checked, so
# what a page loads (scripts, fonts, video) needs no listing.
PRESETS: Dict[str, Tuple[str, ...]] = {
    "Google Docs": ("docs.google.com", "accounts.google.com"),
    "Udemy": ("udemy.com",),
}


class FocusError(ValueError):
    """A focus that can't be started (or malformed JSON)."""


@dataclass(frozen=True)
class Focus:
    ends_at: int  # epoch ms
    sites: Tuple[str, ...]  # names shown in the TUI: presets and typed domains
    domains: Tuple[str, ...]  # what's allowed; subdomains included

    def is_active(self, now_ms: int) -> bool:
        return now_ms < self.ends_at

    def to_json(self) -> dict:
        return {
            "endsAt": self.ends_at,
            "sites": list(self.sites),
            "domains": list(self.domains),
        }

    @classmethod
    def from_json(cls, data: object) -> "Focus":
        if not isinstance(data, dict):
            raise FocusError("focus should be an object")
        ends_at = data.get("endsAt")
        if not isinstance(ends_at, int) or isinstance(ends_at, bool):
            raise FocusError("endsAt should be a whole number")
        return cls(ends_at, _strings(data, "sites"), _strings(data, "domains"))


def normalize_domain(text: str) -> Optional[str]:
    """The host to allow for what someone typed: "udemy.com",
    "https://www.udemy.com/course/x" and "WWW.Udemy.com" all give
    "udemy.com". None if it isn't a domain."""
    text = text.strip().lower()
    if not text:
        return None
    host = urlsplit(text if "://" in text else f"//{text}").hostname or ""
    if host.startswith("www."):
        host = host[len("www.") :]
    return host if valid_hostname(host) else None


def domains_for(sites: List[str]) -> Tuple[str, ...]:
    """Presets resolve to their domains; anything else is a typed domain."""
    found: List[str] = []
    for site in sites:
        for d in PRESETS.get(site, (site,)):
            if d not in found:
                found.append(d)
    return tuple(found)


def active(text: Optional[str], now_ms: int) -> Optional[Focus]:
    """The running focus, or None. Unreadable counts as none: focus blocks
    nearly everything, so it must never get stuck on."""
    if not text:
        return None
    try:
        focus = Focus.from_json(json.loads(text))
    except (ValueError, RecursionError):
        return None
    return focus if focus.is_active(now_ms) else None


def start(stored: Optional[str], focus: Focus, now_ms: int) -> str:
    """The text to store to start `focus`. One at a time (end it first,
    which needs the password), at most 12 hours, and it must allow
    something."""
    if active(stored, now_ms) is not None:
        raise FocusError("focus is already on")
    if focus.ends_at <= now_ms:
        raise FocusError("focus must end in the future")
    if focus.ends_at - now_ms > MAX_MS:
        raise FocusError("focus can last at most 12 hours")
    if not focus.domains:
        raise FocusError("allow at least one site")
    for d in focus.domains:
        if not valid_hostname(d):
            raise FocusError(f"not a domain: {d}")
    return json.dumps(focus.to_json())


ENDED, WRONG_PASSWORD, NOT_RUNNING = "ended", "wrong_password", "not_running"


def end(stored: Optional[str], password_ok: bool, now_ms: int) -> str:
    if active(stored, now_ms) is None:
        return NOT_RUNNING
    return ENDED if password_ok else WRONG_PASSWORD


# The store


def now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def load(path: Path = FOCUS_FILE, now: Optional[int] = None) -> Optional[Focus]:
    return active(_read(path), now_ms() if now is None else now)


def save_start(focus: Focus, path: Path = FOCUS_FILE, now: Optional[int] = None):
    write_text(start(_read(path), focus, now_ms() if now is None else now), path)


def save_end(password_ok: bool, path: Path = FOCUS_FILE, now: Optional[int] = None):
    result = end(_read(path), password_ok, now_ms() if now is None else now)
    if result == ENDED:
        path.unlink(missing_ok=True)
    return result


def _strings(data: dict, key: str) -> Tuple[str, ...]:
    values = data.get(key)
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise FocusError(f"{key} should be a list of strings")
    return tuple(values)
