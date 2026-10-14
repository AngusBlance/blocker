import secrets
from pathlib import Path

from .core import HOSTS_FILE, HostsBlocker

CONFIG_DIR = Path.home() / ".blocker"
PASSWORD_FILE = CONFIG_DIR / "password.txt"


def is_password_set(password_path: Path = PASSWORD_FILE) -> bool:
    return password_path.exists()


def generate_password() -> str:
    # Deliberately long and tedious to type out by hand - the friction is
    # the point. Still just text on screen above the prompt, so unblocking
    # stays possible, just annoying enough that you'll think twice.
    return secrets.token_urlsafe(96)


def setup_password(password_path: Path = PASSWORD_FILE) -> str:
    if password_path.exists():
        raise FileExistsError(f"Password already set up at {password_path}")
    password_path.parent.mkdir(parents=True, exist_ok=True)
    password = generate_password()
    password_path.write_text(password)
    password_path.chmod(0o600)
    return password


def get_password(password_path: Path = PASSWORD_FILE) -> str:
    return password_path.read_text().strip()


def check_password(typed: str, password_path: Path = PASSWORD_FILE) -> bool:
    return typed == get_password(password_path)


def unlock_with_password(
    typed: str,
    urls,
    password_path: Path = PASSWORD_FILE,
    hosts_path: Path = HOSTS_FILE,
) -> bool:
    if not check_password(typed, password_path):
        return False
    HostsBlocker(hosts_path).unblock_all(urls)
    return True
