import os
import socket
import subprocess

import pytest

from blocker_tui.app import BlockerApp
from blocklib.core import HostsBlocker

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_HOSTS_TESTS"),
    reason="edits the real /etc/hosts with sudo - opt in with RUN_LIVE_HOSTS_TESTS=1",
)

NETFLIX_URLS = ["netflix.com", "www.netflix.com"]


def resolved_ip(url: str) -> str:
    try:
        return socket.gethostbyname(url)
    except socket.gaierror:
        return "(no resolution)"


def ping_once(url: str) -> str:
    result = subprocess.run(
        ["ping", "-c", "1", "-t", "2", url],
        capture_output=True,
        text=True,
    )
    return "replied" if result.returncode == 0 else "no reply"


def is_reachable_over_http(url: str) -> bool:
    """Actually attempts a connection to the real website, not just DNS."""
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "--max-time",
            "4",
            "-w",
            "%{http_code}",
            f"https://{url}",
        ],
        capture_output=True,
        text=True,
    )
    code = result.stdout.strip()
    return code not in ("", "000")


async def test_block_netflix_via_keystrokes_then_verify_unreachable():
    """
    Live test against the real /etc/hosts and real DNS resolution.
    Needs your actual sudo password (and will prompt for it) — run this
    yourself, it is not something Claude can run on your behalf.
    """
    blocker = HostsBlocker()

    for url in NETFLIX_URLS:
        if blocker.is_blocked(url):
            blocker.unblock(url)

    for url in NETFLIX_URLS:
        ip = resolved_ip(url)
        reachable = is_reachable_over_http(url)
        print(
            f"before block: {url} -> {ip} (ping: {ping_once(url)}, http reachable: {reachable})"
        )
        assert ip not in ("127.0.0.1", "::1")
        assert reachable is True

    app = BlockerApp()
    async with app.run_test() as pilot:
        await pilot.press("j")  # sidebar -> sites
        await pilot.press("l")  # focus content pane
        await pilot.press("l")  # toggle netflix.com (cursor starts at index 0)
        await pilot.press("j")  # move cursor to www.netflix.com
        await pilot.press("l")  # toggle www.netflix.com

    for url in NETFLIX_URLS:
        assert blocker.is_blocked(url)
        ip = resolved_ip(url)
        reachable = is_reachable_over_http(url)
        print(
            f"after block: {url} -> {ip} (ping: {ping_once(url)}, http reachable: {reachable})"
        )
        assert ip == "127.0.0.1"
        assert reachable is False
