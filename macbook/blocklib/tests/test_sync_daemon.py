import os
import signal
import subprocess
import sys
import threading
import time

from blocklib.sync_daemon import run


def test_run_starts_server_and_stops_it_when_stop_event_is_set():
    calls = []

    class FakeServer:
        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

    stop = threading.Event()
    thread = threading.Thread(target=run, args=(FakeServer(), stop))
    thread.start()
    try:
        deadline = time.monotonic() + 2
        while calls != ["start"] and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls == ["start"]
        stop.set()
    finally:
        thread.join(timeout=2)
    assert calls == ["start", "stop"]


def test_run_stops_server_even_if_it_was_already_stopped_once():
    stop = threading.Event()
    stop.set()  # already set before run() is even called

    class FakeServer:
        def __init__(self):
            self.stopped = False

        def start(self):
            pass

        def stop(self):
            self.stopped = True

    server = FakeServer()
    run(server, stop)
    assert server.stopped is True


def test_daemon_subprocess_exits_cleanly_on_sigterm():
    env = dict(os.environ, BLOCKER_SYNC_PORT="0")
    proc = subprocess.Popen(
        [sys.executable, "-m", "blocklib.sync_daemon"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)  # let it bind and reach stop.wait()
        proc.send_signal(signal.SIGTERM)
        exit_code = proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert exit_code == 0
