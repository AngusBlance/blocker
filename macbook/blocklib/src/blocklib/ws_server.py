import asyncio
import json
import threading

import websockets

from . import focus
from .core import HostsBlocker

DEFAULT_WS_PORT = 8766


def notify_external_daemon(port: int = DEFAULT_WS_PORT, timeout: float = 1.0) -> None:
    """Pings a SyncServer running in a different process so it re-reads
    /etc/hosts and broadcasts the change. Needed when this process doesn't
    own the WebSocket server itself (e.g. the TUI, when the background sync
    daemon already holds the port) and so has no object to call
    notify_change() on directly. Blocking - call from a background thread."""
    try:
        asyncio.run(_ping(port, timeout))
    except OSError:
        pass  # nothing listening there; nothing to notify


async def _ping(port: int, timeout: float) -> None:
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=timeout) as ws:
        await ws.send("refresh")


class SyncServer:
    def __init__(self, port: int = DEFAULT_WS_PORT, focus_path=focus.FOCUS_FILE):
        self.port = port
        self.focus_path = focus_path
        self._loop = None
        self._thread = None
        self._stop_event = None
        self._clients = set()
        self._ready = threading.Event()
        self._error = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        self._thread.join(timeout=2)

    def notify_change(self) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(), self._loop)

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as e:
            self._error = e
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        async with websockets.serve(self._handler, "127.0.0.1", self.port) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stop_event.wait()

    async def _handler(self, websocket) -> None:
        self._clients.add(websocket)
        try:
            await self._send_state(websocket)
            async for _ in websocket:
                # any message is treated as "re-check and broadcast now" -
                # how a different process (e.g. the TUI, via
                # notify_external_daemon) nudges this server since it has
                # no direct handle to call notify_change() on
                await self._broadcast()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)

    def _state(self) -> str:
        """What the extension needs: everything blocked, whether the "Adult
        sites" filter is on (its list stays in /etc/hosts; the extension adds
        keyword rules), and focus mode (the sites it allows and when it ends)
        if it's on."""
        blocker = HostsBlocker()
        current = focus.load(self.focus_path)
        state = {
            "blocked": sorted(blocker.all_blocked_urls),
            "adult": blocker.adult_blocked,
            "focus": None
            if current is None
            else {"until": current.ends_at, "allow": list(current.domains)},
        }
        return json.dumps(state)

    async def _send_state(self, websocket) -> None:
        await websocket.send(self._state())

    async def _broadcast(self) -> None:
        if not self._clients:
            return
        message = self._state()
        await asyncio.gather(
            *(client.send(message) for client in list(self._clients)),
            return_exceptions=True,
        )
