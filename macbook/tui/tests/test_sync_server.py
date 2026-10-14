import asyncio
import json
import socket
import time

import websockets

from blocker_tui.app import BlockerApp, Content, Sidebar
from blocklib.ws_server import SyncServer

# Tests force an ephemeral port (0) for the app's own SyncServer instance so
# they don't collide with the background sync daemon, which holds the real
# DEFAULT_WS_PORT (8766) persistently once installed via launchd.


async def test_server_starts_on_mount_and_is_reachable(monkeypatch):
    monkeypatch.setattr("blocker_tui.app.SyncServer", lambda: SyncServer(port=0))
    app = BlockerApp()
    async with app.run_test():
        port = app._sync_server.port

        async def check():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                return json.loads(await asyncio.wait_for(ws.recv(), timeout=2))

        body = await check()
        assert "blocked" in body


async def test_server_is_closed_after_app_exits(monkeypatch):
    monkeypatch.setattr("blocker_tui.app.SyncServer", lambda: SyncServer(port=0))
    app = BlockerApp()
    async with app.run_test():
        port = app._sync_server.port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        assert result != 0  # non-zero means nothing is listening there anymore


async def test_app_survives_port_already_in_use(monkeypatch):
    blocker_of_the_port = SyncServer(port=0)
    blocker_of_the_port.start()
    monkeypatch.setattr(
        "blocker_tui.app.SyncServer", lambda: SyncServer(port=blocker_of_the_port.port)
    )
    try:
        app = BlockerApp()
        async with app.run_test() as pilot:
            assert app._sync_server is None
            # app should still be fully usable even though its own sync
            # server failed to start
            await pilot.press("j")
            assert app.query_one(Sidebar).selected_index == 1
    finally:
        blocker_of_the_port.stop()


async def test_sync_shows_running_when_another_process_already_owns_the_port(
    monkeypatch,
):
    # e.g. the background sync daemon got there first - that's success, not
    # failure, from the user's point of view: the extension is still synced.
    owner = SyncServer(port=0)
    owner.start()
    monkeypatch.setattr(
        "blocker_tui.app.SyncServer", lambda: SyncServer(port=owner.port)
    )
    try:
        app = BlockerApp()
        async with app.run_test():
            assert app._sync_server is None
            assert app.query_one(Content).sync_running is True
    finally:
        owner.stop()


async def test_notify_sync_pings_the_external_daemon_when_it_owns_the_port(monkeypatch):
    class AlwaysTaken:
        def start(self):
            import errno

            raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr("blocker_tui.app.SyncServer", AlwaysTaken)
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.block_all", lambda self, urls: None
    )
    monkeypatch.setattr(
        "blocker_tui.app.HostsBlocker.is_blocked", lambda self, url: False
    )
    calls = []
    monkeypatch.setattr(
        "blocker_tui.app.notify_external_daemon", lambda: calls.append(1)
    )

    app = BlockerApp()
    async with app.run_test() as pilot:
        assert app._sync_server is None
        await pilot.press("j", "l")
        await pilot.press("l")  # blocks the first group -> should notify

        deadline = time.monotonic() + 1
        while not calls and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        assert calls == [1]
