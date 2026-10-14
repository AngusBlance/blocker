from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from blocker_gui import dialogs
from blocklib.core import HostsBlocker


def blocked(hosts):
    return HostsBlocker(hosts).blocked_urls


def test_starts_on_the_dashboard_showing_open(window):
    assert window.pages.currentIndex() == 0
    assert window.big_state.text() == "OPEN"
    assert window.state_detail.text() == "0 of 3 sites blocked"


def test_nav_switches_to_sites(window, qtbot):
    qtbot.mouseClick(window.nav_buttons["sites"], Qt.LeftButton)
    assert window.pages.currentIndex() == 1
    assert list(window.site_cards) == ["Netflix", "YouTube", "Crunchyroll"]


def test_flipping_a_switch_blocks_every_domain_of_that_site(window, qtbot, isolated):
    qtbot.mouseClick(window.site_cards["Netflix"].toggle, Qt.LeftButton)
    assert blocked(isolated) == {"netflix.com", "www.netflix.com"}
    assert window.site_cards["Netflix"].toggle.is_on()
    assert window.big_state.text() == "BLOCKED"
    assert window.state_detail.text() == "1 of 3 sites blocked: Netflix"


def test_block_everything_blocks_all_sites_and_disables_itself(window, qtbot, isolated):
    qtbot.mouseClick(window.block_all_button, Qt.LeftButton)
    assert len(blocked(isolated)) == 9
    assert not window.block_all_button.isEnabled()


def test_unblocking_with_the_right_password(window, qtbot, isolated, monkeypatch):
    qtbot.mouseClick(window.site_cards["YouTube"].toggle, Qt.LeftButton)
    monkeypatch.setattr(dialogs.UnlockDialog, "exec", lambda self: QDialog.Accepted)
    qtbot.mouseClick(window.site_cards["YouTube"].toggle, Qt.LeftButton)
    assert blocked(isolated) == set()
    assert not window.site_cards["YouTube"].toggle.is_on()


def test_keeping_it_blocked_snaps_the_switch_back(window, qtbot, isolated, monkeypatch):
    qtbot.mouseClick(window.site_cards["YouTube"].toggle, Qt.LeftButton)
    monkeypatch.setattr(dialogs.UnlockDialog, "exec", lambda self: QDialog.Rejected)
    qtbot.mouseClick(window.site_cards["YouTube"].toggle, Qt.LeftButton)
    assert "youtube.com" in blocked(isolated)
    assert window.site_cards["YouTube"].toggle.is_on()


def test_cancelling_the_admin_prompt_changes_nothing(
    window, qtbot, isolated, monkeypatch
):
    monkeypatch.setattr(dialogs, "ensure_admin", lambda parent=None: False)
    qtbot.mouseClick(window.site_cards["Netflix"].toggle, Qt.LeftButton)
    assert blocked(isolated) == set()
    assert not window.site_cards["Netflix"].toggle.is_on()


def test_a_failed_write_shows_an_error_and_keeps_running(
    window, qtbot, isolated, monkeypatch
):
    def fail(self, content):
        raise OSError("sudo: a password is required")

    monkeypatch.setattr(HostsBlocker, "_commit", fail)
    qtbot.mouseClick(window.site_cards["Netflix"].toggle, Qt.LeftButton)
    assert window.toast.property("tone") == "error"
    assert "password is required" in window.toast.text()
    assert not window.site_cards["Netflix"].toggle.is_on()


def test_changes_made_outside_the_app_show_up_live(window, qtbot, isolated):
    HostsBlocker(isolated).block_all(["crunchyroll.com", "www.crunchyroll.com"])
    qtbot.waitUntil(
        lambda: window.site_cards["Crunchyroll"].toggle.is_on(), timeout=3000
    )
    assert window.big_state.text() == "BLOCKED"


def test_dashboard_tiles_follow_the_block_state(window, qtbot):
    qtbot.mouseClick(window.site_cards["Netflix"].toggle, Qt.LeftButton)
    assert window.tiles["Netflix"].text().startswith("(x)")
    assert window.tiles["YouTube"].text().startswith("( )")
    qtbot.mouseClick(window.tiles["YouTube"], Qt.LeftButton)
    assert window.pages.currentIndex() == 1
