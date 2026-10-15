import os
import signal
import threading
from pathlib import Path

from .core import HOSTS_FILE
from .ws_server import DEFAULT_WS_PORT, SyncServer

# Schedules start and end without anyone touching the TUI (the root helper
# rewrites /etc/hosts), so watch the file and tell the extension.
POLL_SECONDS = 5


def _mtime(path: Path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def run(
    server: SyncServer,
    stop: threading.Event,
    hosts: Path = HOSTS_FILE,
    poll: float = POLL_SECONDS,
) -> None:
    server.start()
    try:
        seen = _mtime(hosts)
        while not stop.wait(poll):
            now = _mtime(hosts)
            if now != seen:
                seen = now
                server.notify_change()
    finally:
        server.stop()


def main() -> None:
    port = int(os.environ.get("BLOCKER_SYNC_PORT", DEFAULT_WS_PORT))
    server = SyncServer(port=port)
    stop = threading.Event()

    def _handle_signal(signum, frame) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    # Printed once signals are handled; tests wait for it before sending one.
    print(f"blocker-sync starting on port {port}", flush=True)

    run(server, stop)


if __name__ == "__main__":
    main()
