"""Where the Mac keeps schedules: ~/.blocker/schedules.json, written by the
user (the TUI) and read by the root helper that applies them.

Saving goes through schedule.replace_all and ending early through
schedule.pause_json, so the same lock rules hold as on Android: without the
unlock password nothing running can be weakened (decision D1).
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import schedule as sch
from .password import CONFIG_DIR

SCHEDULES_FILE = CONFIG_DIR / "schedules.json"


def read_text(path: Path = SCHEDULES_FILE) -> Optional[str]:
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


def load(path: Path = SCHEDULES_FILE) -> List[sch.Schedule]:
    """Every readable schedule; one bad entry doesn't hide the rest."""
    return sch.list_from_json_skipping_bad(read_text(path))


def write_text(text: str, path: Path = SCHEDULES_FILE) -> None:
    """Atomically: the root helper may read it at any moment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".schedules-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save(
    incoming: List[sch.Schedule],
    password_ok: bool,
    now: datetime,
    path: Path = SCHEDULES_FILE,
) -> List[sch.Schedule]:
    """Stores `incoming` as the whole list. Raises schedule.LockedError if
    that would weaken a running schedule and the password wasn't given."""
    stored = sch.replace_all(load(path), incoming, password_ok, now)
    write_text(sch.list_to_json(stored), path)
    return stored


def end_early(
    schedule_id: str, password_ok: bool, now: datetime, path: Path = SCHEDULES_FILE
) -> str:
    """Pauses the occurrence running now. One of schedule.PAUSED,
    WRONG_PASSWORD or NOT_RUNNING."""
    result, text = sch.pause_json(read_text(path), schedule_id, password_ok, now)
    if text is not None:
        write_text(text, path)
    return result
