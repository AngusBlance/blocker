"""Where the Mac keeps schedules: ~/.blocker/schedules.json, written by the
user (the TUI) and read by the root helper that applies them.

Saving goes through schedule.replace_all and ending early through
schedule.pause_json, so the same lock rules hold as on Android: without the
unlock password nothing running can be weakened (decision D1). The file can
be edited by hand, so entries this version can't read are kept as they are,
and a file that isn't a JSON list at all is never saved over.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from . import schedule as sch
from .password import CONFIG_DIR

SCHEDULES_FILE = CONFIG_DIR / "schedules.json"


class DamagedError(sch.ScheduleError):
    """schedules.json exists but can't be read as a list of schedules."""


def read_text(path: Path = SCHEDULES_FILE) -> Optional[str]:
    """The file's text, None if there isn't one. Raises DamagedError if it
    can't be read (permissions, not UTF-8, a folder...)."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise DamagedError(f"can't read {path}: {e}") from e


def _split(text: Optional[str]) -> Tuple[List[sch.Schedule], list]:
    """Readable schedules, and the raw entries that aren't."""
    if text is None or not text.strip():
        return [], []
    try:
        items = sch.loads_untrusted(text)
    except (ValueError, RecursionError) as e:
        raise DamagedError(f"schedules.json isn't valid JSON: {e!r}") from e
    if not isinstance(items, list):
        raise DamagedError("schedules.json should hold a list")
    schedules, unreadable = [], []
    for item in items:
        try:
            schedules.append(sch.Schedule.from_json(item))
        except sch.ScheduleError:
            unreadable.append(item)
    return schedules, unreadable


def load(path: Path = SCHEDULES_FILE) -> List[sch.Schedule]:
    """Every readable schedule; one bad entry doesn't hide the rest. Raises
    DamagedError if the file as a whole can't be read."""
    return _split(read_text(path))[0]


def write_text(text: str, path: Path = SCHEDULES_FILE) -> None:
    """Atomically: the root helper may read it at any moment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".schedules-")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def update(
    change,
    password_ok: bool,
    now: datetime,
    path: Path = SCHEDULES_FILE,
) -> List[sch.Schedule]:
    """Reads the stored list, applies `change` (list -> list) to it and
    stores the result, all at once so nothing written meanwhile is lost.
    Raises schedule.LockedError if that would weaken a running schedule
    without the password, DamagedError if the file can't be read."""
    stored, unreadable = _split(read_text(path))
    result = sch.replace_all(stored, change(list(stored)), password_ok, now)
    items = [s.to_json() for s in result] + unreadable
    write_text(json.dumps(items), path)
    return result


def save(
    incoming: List[sch.Schedule],
    password_ok: bool,
    now: datetime,
    path: Path = SCHEDULES_FILE,
) -> List[sch.Schedule]:
    """Stores `incoming` as the whole list (see update)."""
    return update(lambda _: incoming, password_ok, now, path)


def end_early(
    schedule_id: str, password_ok: bool, now: datetime, path: Path = SCHEDULES_FILE
) -> str:
    """Pauses the occurrence running now. One of schedule.PAUSED,
    WRONG_PASSWORD or NOT_RUNNING; DamagedError if the file can't be read."""
    stored = read_text(path)
    _split(stored)  # a damaged file is DamagedError, not "not running"
    result, text = sch.pause_json(stored, schedule_id, password_ok, now)
    if text is not None:
        write_text(text, path)
    return result
