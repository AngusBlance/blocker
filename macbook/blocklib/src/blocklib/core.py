import subprocess
import tempfile
from pathlib import Path

from .schedule_helper import LOCK_FILE, scheduled_hostnames

HOSTS_FILE = Path("/etc/hosts")
BEGIN_MARK = "# BLOCKER-BEGIN"
END_MARK = "# BLOCKER-END"


class HostsBlocker:
    def __init__(self, hosts_path: Path = HOSTS_FILE):
        self.hosts_path = hosts_path

    @property
    def raw_content(self) -> str:
        return self.hosts_path.read_text()

    @property
    def blocked_urls(self) -> set:
        return self._parse_blocked_urls(self.raw_content)

    @property
    def scheduled_urls(self) -> set:
        """Blocked by a running schedule: the section the root scheduler
        helper writes (read-only here)."""
        return scheduled_hostnames(self.raw_content)

    @property
    def all_blocked_urls(self) -> set:
        """Everything blocked right now, manually or by a schedule."""
        content = self.raw_content
        return self._parse_blocked_urls(content) | scheduled_hostnames(content)

    @property
    def is_active(self) -> bool:
        return bool(self.blocked_urls)

    def is_blocked(self, url: str) -> bool:
        return url in self.blocked_urls

    def block(self, url: str) -> None:
        self._commit(self._insert_domain(self.raw_content, url))

    def unblock(self, url: str) -> None:
        self._commit(self._remove_domain(self.raw_content, url))

    def block_all(self, urls) -> None:
        content = self.raw_content
        for url in urls:
            content = self._insert_domain(content, url)
        self._commit(content)

    def unblock_all(self, urls) -> None:
        content = self.raw_content
        for url in urls:
            content = self._remove_domain(content, url)
        self._commit(content)

    def _commit(self, content: str) -> None:
        self._write_privileged(content)
        self._flush_dns()

    def _write_privileged(self, content: str) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            # Same lock as the root schedule helper, so neither undoes the
            # other's change; -k keeps the lock file for the next user.
            subprocess.run(
                [
                    "sudo",
                    "/usr/bin/lockf",
                    "-k",
                    "-t",
                    "10",
                    str(LOCK_FILE),
                    "cp",
                    tmp_path,
                    str(self.hosts_path),
                ],
                check=True,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @staticmethod
    def _flush_dns() -> None:
        subprocess.run(["sudo", "/usr/bin/dscacheutil", "-flushcache"], check=True)
        subprocess.run(
            ["sudo", "/usr/bin/killall", "-HUP", "mDNSResponder"], check=True
        )

    @staticmethod
    def _extract_block(content: str):
        lines = content.splitlines()
        try:
            start = lines.index(BEGIN_MARK)
            end = lines.index(END_MARK)
        except ValueError:
            return None
        return lines[start + 1 : end]

    @staticmethod
    def _line_is_for_url(line: str, url: str) -> bool:
        parts = line.split()
        return len(parts) == 2 and parts[1] == url

    @classmethod
    def _parse_blocked_urls(cls, content: str) -> set:
        block = cls._extract_block(content)
        if block is None:
            return set()
        urls = set()
        for line in block:
            parts = line.split()
            if len(parts) == 2:
                urls.add(parts[1])
        return urls

    @classmethod
    def _insert_domain(cls, content: str, url: str) -> str:
        lines = content.splitlines()
        entry_lines = [f"127.0.0.1 {url}", f"::1 {url}"]

        try:
            end = lines.index(END_MARK)
        except ValueError:
            new_block = [BEGIN_MARK, *entry_lines, END_MARK]
            return "\n".join(lines + new_block) + "\n"

        if url in cls._parse_blocked_urls(content):
            return content

        new_lines = lines[:end] + entry_lines + lines[end:]
        return "\n".join(new_lines) + "\n"

    @classmethod
    def _remove_domain(cls, content: str, url: str) -> str:
        lines = content.splitlines()
        try:
            start = lines.index(BEGIN_MARK)
            end = lines.index(END_MARK)
        except ValueError:
            return content

        block_lines = lines[start + 1 : end]
        remaining = [
            line for line in block_lines if not cls._line_is_for_url(line, url)
        ]

        if remaining:
            new_lines = (
                lines[:start] + [BEGIN_MARK] + remaining + [END_MARK] + lines[end + 1 :]
            )
        else:
            new_lines = lines[:start] + lines[end + 1 :]

        return "\n".join(new_lines) + "\n" if new_lines else ""

    def __len__(self) -> int:
        return len(self.blocked_urls)

    def __contains__(self, url: str) -> bool:
        return self.is_blocked(url)

    def __str__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return f"HostsBlocker({state}, {len(self)} blocked)"

    def __repr__(self) -> str:
        return f"HostsBlocker(hosts_path={str(self.hosts_path)!r})"
