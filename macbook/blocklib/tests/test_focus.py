import json
import threading

import pytest

from blocklib import focus
from blocklib.focus import Focus, FocusError
from blocklib.ws_server import SyncServer

NOW = 1_760_000_000_000
HOUR = 3_600_000
DOCS = Focus(NOW + HOUR, ("Google Docs",), ("docs.google.com", "accounts.google.com"))


@pytest.mark.parametrize(
    "typed, host",
    [
        ("udemy.com", "udemy.com"),
        ("https://www.udemy.com/course/x?y=1", "udemy.com"),
        ("  WWW.Udemy.COM ", "udemy.com"),
        ("en.wikipedia.org", "en.wikipedia.org"),
        ("docs.google.com:443", "docs.google.com"),
        ("not a site", None),
        ("localhost", None),
        ("", None),
    ],
)
def test_typed_sites_become_domains(typed, host):
    assert focus.normalize_domain(typed) == host


def test_presets_resolve_to_their_domains_and_typed_sites_to_themselves():
    assert focus.domains_for(["Google Docs", "wikipedia.org", "Udemy"]) == (
        "docs.google.com",
        "accounts.google.com",
        "wikipedia.org",
        "udemy.com",
    )


def test_starting_checks_length_contents_and_that_none_is_running():
    stored = focus.start(None, DOCS, NOW)
    assert focus.active(stored, NOW) == DOCS
    with pytest.raises(FocusError):
        focus.start(stored, DOCS, NOW)
    later = Focus(NOW + 3 * HOUR, DOCS.sites, DOCS.domains)
    assert focus.active(focus.start(stored, later, NOW + 2 * HOUR), NOW + 2 * HOUR)
    for bad in [
        Focus(NOW, DOCS.sites, DOCS.domains),
        Focus(NOW + 13 * HOUR, DOCS.sites, DOCS.domains),
        Focus(NOW + HOUR, (), ()),
        Focus(NOW + HOUR, ("x",), ("not a domain",)),
    ]:
        with pytest.raises(FocusError):
            focus.start(None, bad, NOW)


def test_finished_or_unreadable_focus_is_no_focus():
    stored = focus.start(None, DOCS, NOW)
    assert focus.active(stored, NOW + HOUR) is None
    for text in [None, "", "{", "[]", '{"endsAt": "1", "sites": [], "domains": []}']:
        assert focus.active(text, NOW) is None


def test_ending_early_needs_the_password(tmp_path):
    path = tmp_path / "focus.json"
    focus.save_start(DOCS, path, NOW)
    assert focus.load(path, NOW) == DOCS
    assert focus.save_end(False, path, NOW) == focus.WRONG_PASSWORD
    assert focus.load(path, NOW) == DOCS
    assert focus.save_end(True, path, NOW) == focus.ENDED
    assert focus.load(path, NOW) is None
    assert focus.save_end(True, path, NOW) == focus.NOT_RUNNING


def test_the_extension_gets_the_focus_with_the_blocks(tmp_path, monkeypatch):
    path = tmp_path / "focus.json"
    server = SyncServer(port=0, focus_path=path)
    monkeypatch.setattr(focus, "now_ms", lambda: NOW)
    state = json.loads(server._state())
    assert state["focus"] is None and isinstance(state["blocked"], list)
    focus.save_start(DOCS, path, NOW)
    state = json.loads(server._state())
    assert state["focus"] == {
        "until": NOW + HOUR,
        "allow": ["docs.google.com", "accounts.google.com"],
    }


def test_the_sync_daemon_rebroadcasts_when_focus_changes(tmp_path):
    from blocklib.sync_daemon import run

    hosts, focus_file = tmp_path / "hosts", tmp_path / "focus.json"
    hosts.write_text("127.0.0.1 localhost\n")
    notified = threading.Event()

    class FakeServer:
        def start(self):
            pass

        def stop(self):
            pass

        def notify_change(self):
            notified.set()

    stop = threading.Event()
    thread = threading.Thread(
        target=run,
        args=(FakeServer(), stop),
        kwargs={"hosts": hosts, "poll": 0.01, "focus_file": focus_file},
    )
    thread.start()
    try:
        focus.save_start(DOCS, focus_file, NOW)
        assert notified.wait(2)
    finally:
        stop.set()
        thread.join(timeout=2)
