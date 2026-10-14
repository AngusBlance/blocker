import os
import signal
import threading

from .ws_server import DEFAULT_WS_PORT, SyncServer


def run(server: SyncServer, stop: threading.Event) -> None:
    server.start()
    try:
        stop.wait()
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
