"""Desktop app for the blocker: the same blocklib backend as the TUI, with a
Qt (PySide6) window, so it runs like any other app on macOS, Windows and
Linux. Blocking itself is macOS-only for now, because blocklib is."""

from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blocklib.core import HOSTS_FILE, HostsBlocker
from blocklib.domain import known_domains
from blocklib.password import get_password, is_password_set, setup_password
from blocklib.ws_server import DEFAULT_WS_PORT, notify_external_daemon

from . import dialogs, theme
from .widgets import Logo, Toast, ToggleSwitch

SECTIONS = ["dashboard", "sites"]


def site_groups(hosts_path: Path) -> list:
    """[(name, urls, all_blocked)] per site, in the order blocklib lists them."""
    blocked = HostsBlocker(hosts_path).blocked_urls
    groups: dict = {}
    for d in known_domains():
        groups.setdefault(d.name, []).append(d.url)
    return [
        (name, urls, all(u in blocked for u in urls)) for name, urls in groups.items()
    ]


def sync_daemon_running(port: int = DEFAULT_WS_PORT) -> bool:
    """Whether the background sync daemon is listening for the extension."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _label(text: str = "", role: str | None = None) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    return label


def _restyle(widget: QWidget) -> None:
    """Re-applies the stylesheet after a property it depends on changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SiteCard(QFrame):
    def __init__(self, name: str, urls: list) -> None:
        super().__init__()
        self.name = name
        self.urls = urls
        self.setProperty("role", "card")

        title = _label(name)
        title.setFont(QFont(theme.MONO.split(",")[0], 16, QFont.Bold))
        domains = _label(", ".join(urls), "muted")
        domains.setWordWrap(True)
        self.state = _label("", "mono")
        self.toggle = ToggleSwitch()

        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(title)
        text.addWidget(domains)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        layout.addLayout(text, 1)
        layout.addWidget(self.state)
        layout.addWidget(self.toggle)

    def set_blocked(self, blocked: bool, animate: bool = True) -> None:
        self.toggle.set_on(blocked, animate)
        self.state.setText("BLOCKED" if blocked else "open")
        self.state.setStyleSheet(f"color: {theme.ACCENT if blocked else theme.MUTED};")
        self.setProperty("blocked", "true" if blocked else "false")
        _restyle(self)


class SiteTile(QPushButton):
    """A square dashboard tile per site, like the Android app's tab tiles.
    Clicking it blocks or unblocks the site, same as its switch."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(150, 150)

    def set_blocked(self, blocked: bool) -> None:
        self.setText(
            f"{'(x)' if blocked else '( )'}\n\n{self.name}\n{'blocked' if blocked else 'open'}"
        )
        self.setProperty("blocked", "true" if blocked else "false")
        _restyle(self)


class BlockerWindow(QMainWindow):
    def __init__(self, hosts_path: Path = HOSTS_FILE) -> None:
        super().__init__()
        self.hosts_path = hosts_path
        self.setWindowTitle("Blocker")
        self.resize(940, 620)
        self.setMinimumSize(760, 520)

        if not is_password_set():
            setup_password()

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard())
        self.pages.addWidget(self._build_sites())
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.toast = Toast(root)

        # Pick up changes made elsewhere (the TUI, the terminal) live.
        self.watcher = QFileSystemWatcher([str(hosts_path)], self)
        self.watcher.fileChanged.connect(self._on_hosts_changed)
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._refresh_sync)
        self.sync_timer.start(5000)

        self.show_section("dashboard")
        self.refresh(animate=False)
        self._refresh_sync()

    # -- layout ---------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addWidget(Logo(28))
        name = _label("blocker")
        name.setObjectName("brand")
        brand.addWidget(name)
        brand.addStretch()

        nav = QWidget()
        nav.setObjectName("nav")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for section in SECTIONS:
            button = QPushButton(section)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, s=section: self.show_section(s))
            self.nav_group.addButton(button)
            self.nav_buttons[section] = button
            nav_layout.addWidget(button)

        self.sync_label = _label("", "mono")
        self.sync_label.setWordWrap(True)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 24, 0, 20)
        layout.setSpacing(24)
        brand_row = QWidget()
        brand_row.setLayout(brand)
        brand.setContentsMargins(20, 0, 20, 0)
        layout.addWidget(brand_row)
        layout.addWidget(nav)
        layout.addStretch()
        sync_row = QWidget()
        sync_layout = QVBoxLayout(sync_row)
        sync_layout.setContentsMargins(20, 0, 20, 0)
        sync_layout.addWidget(self.sync_label)
        layout.addWidget(sync_row)
        return sidebar

    def _page(self, heading: str) -> tuple:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(18)
        layout.addWidget(_label(heading, "heading"))
        return page, layout

    def _build_dashboard(self) -> QWidget:
        page, layout = self._page("STATUS")

        self.status_card = QFrame()
        self.status_card.setObjectName("status-card")
        card = QVBoxLayout(self.status_card)
        card.setContentsMargins(32, 28, 32, 28)
        card.setSpacing(8)
        self.big_state = _label()
        self.big_state.setObjectName("big-state")
        self.state_detail = _label("", "muted")
        card.addWidget(self.big_state)
        card.addWidget(self.state_detail)
        layout.addWidget(self.status_card)

        self.block_all_button = QPushButton("block everything")
        self.block_all_button.setProperty("role", "primary")
        self.block_all_button.setCursor(Qt.PointingHandCursor)
        self.block_all_button.clicked.connect(self.block_everything)
        buttons = QHBoxLayout()
        buttons.addWidget(self.block_all_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        layout.addSpacing(12)
        layout.addWidget(_label("SITES", "heading"))
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles = {}
        for name, _, _ in site_groups(self.hosts_path):
            tile = SiteTile(name)
            tile.clicked.connect(lambda _=False, n=name: self.toggle_site(n))
            self.tiles[name] = tile
            tiles.addWidget(tile)
        layout.addLayout(tiles)
        layout.addStretch()
        return page

    def _build_sites(self) -> QWidget:
        page, layout = self._page("SITES")
        self.sites_summary = _label("", "muted")
        layout.addWidget(self.sites_summary)

        list_widget = QWidget()
        self.site_list = QVBoxLayout(list_widget)
        self.site_list.setContentsMargins(0, 0, 0, 0)
        self.site_list.setSpacing(12)
        self.site_cards = {}
        for name, urls, _ in site_groups(self.hosts_path):
            site_card = SiteCard(name, urls)
            site_card.toggle.toggled_by_user.connect(
                lambda on, c=site_card: (
                    self.block_site(c) if on else self.unblock_site(c)
                )
            )
            self.site_cards[name] = site_card
            self.site_list.addWidget(site_card)
        self.site_list.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(list_widget)
        layout.addWidget(scroll, 1)
        layout.addWidget(
            _label(
                "flip a switch to block a site. unblocking needs the password.", "muted"
            )
        )
        return page

    # -- state ------------------------------------------------------------

    def show_section(self, name: str) -> None:
        self.pages.setCurrentIndex(SECTIONS.index(name))
        self.nav_buttons[name].setChecked(True)

    def refresh(self, animate: bool = True) -> None:
        groups = site_groups(self.hosts_path)
        blocked = [name for name, _, is_blocked in groups if is_blocked]
        any_blocked = HostsBlocker(self.hosts_path).is_active

        self.big_state.setText("BLOCKED" if any_blocked else "OPEN")
        self.big_state.setStyleSheet(
            f"color: {theme.ACCENT if any_blocked else theme.SUCCESS};"
        )
        self.state_detail.setText(
            f"{len(blocked)} of {len(groups)} sites blocked"
            + (f": {', '.join(blocked)}" if blocked else "")
        )
        self.status_card.setProperty("blocked", "true" if any_blocked else "false")
        _restyle(self.status_card)
        self.block_all_button.setEnabled(len(blocked) < len(groups))

        self.sites_summary.setText(f"{len(groups)} sites, {len(blocked)} blocked")
        for name, _, is_blocked in groups:
            self.site_cards[name].set_blocked(is_blocked, animate)
            self.tiles[name].set_blocked(is_blocked)

    def _refresh_sync(self) -> None:
        running = sync_daemon_running()
        colour = theme.SUCCESS if running else theme.MUTED
        self.sync_label.setText(
            f"● extension sync\n  {'running' if running else 'off'}"
        )
        self.sync_label.setStyleSheet(f"color: {colour}; font-size: 12px;")

    def _on_hosts_changed(self, path: str) -> None:
        # Replacing the file can drop it from the watch list; re-add it.
        if path not in self.watcher.files() and Path(path).exists():
            self.watcher.addPath(path)
        self.refresh()

    # -- actions ----------------------------------------------------------

    def toggle_site(self, name: str) -> None:
        card = self.site_cards[name]
        if card.toggle.is_on():
            self.unblock_site(card)
        else:
            self.block_site(card)

    def block_everything(self) -> None:
        self._change(
            lambda b: b.block_all([d.url for d in known_domains()]),
            "blocked everything",
        )

    def block_site(self, card: SiteCard) -> None:
        self._change(lambda b: b.block_all(card.urls), f"blocked {card.name}")

    def unblock_site(self, card: SiteCard) -> None:
        if is_password_set():
            dialog = dialogs.UnlockDialog(card.name, get_password(), self)
            if dialog.exec() != dialogs.QDialog.Accepted:
                self.refresh()  # snaps the switch back
                return
        self._change(lambda b: b.unblock_all(card.urls), f"unlocked {card.name}")

    def _change(self, action, message: str) -> None:
        """Runs a blocklib change, getting sudo ready first since blocklib
        edits /etc/hosts with it and a window has no terminal to prompt in."""
        if not dialogs.ensure_admin(self):
            self.refresh()
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            action(HostsBlocker(self.hosts_path))
        except Exception as e:  # sudo or file errors: tell the user, keep running
            self.toast.show_message(f"failed: {e}", "error")
        else:
            self.toast.show_message(message)
            # Let the Chrome extension pick up the change via the sync daemon.
            threading.Thread(target=notify_external_daemon, daemon=True).start()
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.move(
                self.centralWidget().width() - self.toast.width() - 24,
                self.centralWidget().height() - self.toast.height() - 24,
            )


def create_app(argv: list | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("Blocker")
    app.setStyle("Fusion")  # same look on every platform; the stylesheet does the rest
    app.setStyleSheet(theme.STYLESHEET)
    font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
    font.setPointSize(13)
    app.setFont(font)
    return app


def main() -> None:
    app = create_app()
    window = BlockerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
