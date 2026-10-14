import asyncio
import json
import threading
import time

import pytest
import websockets

from blocklib.core import HostsBlocker
from blocklib.ws_server import SyncServer, notify_external_daemon


@pytest.fixture
def running_ws_server():
    server = SyncServer(port=0)
    server.start()
    yield server
    server.stop()


def test_ws_server_sends_current_state_on_connect(running_ws_server):
    async def check():
        uri = f"ws://127.0.0.1:{running_ws_server.port}"
        async with websockets.connect(uri) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=2)
            return json.loads(message)

    body = asyncio.run(check())
    assert "blocked" in body
    assert set(body["blocked"]) == HostsBlocker().blocked_urls


def test_ws_server_pushes_update_promptly_on_notify_change(running_ws_server):
    async def check():
        uri = f"ws://127.0.0.1:{running_ws_server.port}"
        async with websockets.connect(uri) as ws:
            await ws.recv()  # consume the initial state push
            running_ws_server.notify_change()
            start = time.monotonic()
            message = await asyncio.wait_for(ws.recv(), timeout=5)
            elapsed = time.monotonic() - start
            return json.loads(message), elapsed

    body, elapsed = asyncio.run(check())
    assert "blocked" in body
    assert elapsed < 1  # proves it was pushed, not polled


def test_ws_server_handles_multiple_connected_clients(running_ws_server):
    async def check():
        uri = f"ws://127.0.0.1:{running_ws_server.port}"
        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()
            await ws2.recv()
            running_ws_server.notify_change()
            msg1 = await asyncio.wait_for(ws1.recv(), timeout=2)
            msg2 = await asyncio.wait_for(ws2.recv(), timeout=2)
            return json.loads(msg1), json.loads(msg2)

    body1, body2 = asyncio.run(check())
    assert body1 == body2


def test_ws_server_notify_change_is_noop_before_start():
    server = SyncServer(port=0)
    server.notify_change()  # should not raise, even though it's never been started


def test_start_raises_promptly_on_port_conflict(running_ws_server):
    start = time.monotonic()
    with pytest.raises(OSError):
        SyncServer(port=running_ws_server.port).start()
    elapsed = time.monotonic() - start
    assert elapsed < 2  # must fail fast, not hang out the 5s ready-timeout


def test_ws_server_broadcasts_when_any_client_sends_a_message(running_ws_server):
    async def check():
        uri = f"ws://127.0.0.1:{running_ws_server.port}"
        async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
            await ws1.recv()
            await ws2.recv()
            await ws1.send("refresh")
            start = time.monotonic()
            message = await asyncio.wait_for(ws2.recv(), timeout=2)
            elapsed = time.monotonic() - start
            return json.loads(message), elapsed

    body, elapsed = asyncio.run(check())
    assert "blocked" in body
    assert elapsed < 1  # proves it's pushed, not polled


def test_notify_external_daemon_triggers_a_prompt_broadcast(running_ws_server):
    async def check():
        uri = f"ws://127.0.0.1:{running_ws_server.port}"
        async with websockets.connect(uri) as ws:
            await ws.recv()  # consume the initial state push
            threading.Thread(
                target=notify_external_daemon,
                args=(running_ws_server.port,),
                daemon=True,
            ).start()
            start = time.monotonic()
            message = await asyncio.wait_for(ws.recv(), timeout=2)
            elapsed = time.monotonic() - start
            return json.loads(message), elapsed

    body, elapsed = asyncio.run(check())
    assert "blocked" in body
    assert elapsed < 1


def test_notify_external_daemon_does_not_raise_when_nothing_is_listening():
    notify_external_daemon(port=1, timeout=0.5)  # port 1 is closed; connect fails fast
