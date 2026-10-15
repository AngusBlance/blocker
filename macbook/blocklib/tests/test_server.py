import json
import threading
import urllib.error
import urllib.request

import pytest

from blocklib.server import make_server


@pytest.fixture
def running_server():
    server = make_server(port=0)  # port 0 = let the OS pick a free port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=2)


def get(server, path):
    port = server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as resp:
        return resp.status, json.loads(resp.read())


def test_server_binds_to_localhost_only():
    server = make_server(port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_blocked_domains_endpoint_returns_json(running_server):
    status, body = get(running_server, "/blocked-domains")
    assert status == 200
    assert "blocked" in body
    assert isinstance(body["blocked"], list)


def test_blocked_domains_matches_real_hosts_blocker_state(running_server):
    from blocklib.core import HostsBlocker

    _, body = get(running_server, "/blocked-domains")
    assert set(body["blocked"]) == HostsBlocker().all_blocked_urls


def test_unknown_path_returns_404(running_server):
    port = running_server.server_address[1]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/not-a-real-path")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=2)
    assert exc_info.value.code == 404
