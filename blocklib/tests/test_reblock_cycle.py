import os
import socket
import subprocess
import time

import pytest

from blocklib.core import HostsBlocker
from blocklib.domain import known_domains

BASE_HOSTS = "127.0.0.1 localhost\n::1 localhost\n"


def resolved_ip(url: str) -> str:
    try:
        return socket.gethostbyname(url)
    except socket.gaierror:
        return "(no resolution)"


def ping_once(url: str) -> str:
    result = subprocess.run(
        ["ping", "-c", "1", "-t", "2", url], capture_output=True, text=True
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


def pure_block_all(content: str, urls) -> str:
    for url in urls:
        content = HostsBlocker._insert_domain(content, url)
    return content


def pure_unblock(content: str, url: str) -> str:
    return HostsBlocker._remove_domain(content, url)


def test_bulk_block_then_unblock_each_then_bulk_block_again(tmp_path):
    """
    Reproduces: bulk block all sites, unblock each one individually
    (as the per-site toggle does), then bulk block again. The second
    block_all must end up identical to the first — this is the exact
    sequence a user reported seeing stale/incorrect state after.
    """
    urls = [d.url for d in known_domains()]
    path = tmp_path / "hosts"
    path.write_text(BASE_HOSTS)

    # first bulk block
    content = pure_block_all(path.read_text(), urls)
    path.write_text(content)
    first_pass = HostsBlocker(path)
    assert first_pass.blocked_urls == set(urls)
    assert len(first_pass) == len(urls)

    # unblock every domain individually, like the TUI's per-site toggle does
    for url in urls:
        content = pure_unblock(path.read_text(), url)
        path.write_text(content)

    cleared = HostsBlocker(path)
    assert cleared.blocked_urls == set()
    assert cleared.is_active is False
    # the marker block itself should be fully removed, not left empty
    assert "# BLOCKER-BEGIN" not in path.read_text()
    assert "127.0.0.1 localhost" in path.read_text()

    # bulk block again - this is the step the bug report pointed at
    content = pure_block_all(path.read_text(), urls)
    path.write_text(content)
    second_pass = HostsBlocker(path)

    assert second_pass.blocked_urls == set(urls)
    assert len(second_pass) == len(urls)
    assert second_pass.blocked_urls == first_pass.blocked_urls
    assert "127.0.0.1 localhost" in path.read_text()


def test_bulk_block_unblock_block_cycle_is_stable_over_multiple_repeats(tmp_path):
    """Same cycle run three times in a row - catches any slow drift/corruption."""
    urls = [d.url for d in known_domains()]
    path = tmp_path / "hosts"
    path.write_text(BASE_HOSTS)

    for _ in range(3):
        content = pure_block_all(path.read_text(), urls)
        path.write_text(content)
        assert HostsBlocker(path).blocked_urls == set(urls)

        for url in urls:
            content = pure_unblock(path.read_text(), url)
            path.write_text(content)
        assert HostsBlocker(path).blocked_urls == set()

    assert path.read_text().count("# BLOCKER-BEGIN") == 0
    assert path.read_text().count("127.0.0.1 localhost") == 1


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_HOSTS_TESTS"),
    reason="edits the real /etc/hosts with sudo - opt in with RUN_LIVE_HOSTS_TESTS=1",
)
def test_speed_unblock_then_block_all_against_real_hosts(capsys):
    """
    LIVE test against the real /etc/hosts AND real network reachability -
    real subprocess calls, real sudo, real DNS flush, then actually
    resolving DNS and connecting to each real website, not just checking
    what the hosts file says. Needs your actual sudo password; run this
    yourself, it is not something Claude can run.

    Times block_all -> unblock_all -> block_all, matching the exact cycle
    discussed: block everything, then immediately unblock and re-block.
    """
    urls = [d.url for d in known_domains()]
    blocker = HostsBlocker()

    # get to a known starting state first; not counted in the timing
    blocker.block_all(urls)
    assert blocker.blocked_urls == set(urls)

    start = time.perf_counter()
    blocker.unblock_all(urls)
    assert blocker.blocked_urls == set()
    blocker.block_all(urls)
    assert blocker.blocked_urls == set(urls)
    elapsed = time.perf_counter() - start

    with capsys.disabled():
        print(f"\nunblock_all() + block_all() took {elapsed:.3f}s")
        print("verifying actual reachability (not just hosts file content):")
        failures = []
        for url in urls:
            ip = resolved_ip(url)
            reachable = is_reachable_over_http(url)
            ping = ping_once(url)
            print(
                f"  {url:24s} resolves={ip:16s} http_reachable={reachable!s:5s} ping={ping}"
            )
            if ip not in ("127.0.0.1", "::1"):
                failures.append(f"{url}: resolved to {ip}, not localhost")
            if reachable:
                failures.append(f"{url}: still reachable over HTTP")

        if failures:
            print("\nFAILURES:")
            for f in failures:
                print(f"  - {f}")

    assert not failures, (
        f"{len(failures)} domain(s) not actually blocked - see output above"
    )
    assert elapsed < 30  # sanity ceiling - catches a hang, not a perf budget
