"""The unlock dialog and the admin (sudo) password prompt."""

from __future__ import annotations

import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _label(text: str, role: str | None = None, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


def _button(text: str, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.PointingHandCursor)
    if primary:
        button.setProperty("role", "primary")
    return button


class NoPasteLineEdit(QLineEdit):
    """Typing it out by hand is the point; paste and drag-drop are off."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.Paste):
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:  # pragma: no cover - Qt hook
        pass


class UnlockDialog(QDialog):
    """Shows the long unlock password and asks for it to be typed back.
    Accepted only when it matches."""

    def __init__(self, site: str, password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.password = password
        self.setWindowTitle(f"Unlock {site}")
        self.setModal(True)
        self.setMinimumWidth(620)

        self.input = NoPasteLineEdit()
        self.input.setPlaceholderText("type the password here")
        self.counter = _label("", "muted")
        self.unlock_button = _button("unlock", primary=True)
        self.unlock_button.setEnabled(False)
        keep = _button("keep it blocked")

        # Shown in fixed-width lines: one 128-character token won't word-wrap.
        box = _label(
            "\n".join(password[i : i + 64] for i in range(0, len(password), 64)),
            wrap=False,
        )
        box.setObjectName("password-box")
        # Selectable would allow copy; the friction of typing it is the point.
        box.setTextInteractionFlags(Qt.NoTextInteraction)

        buttons = QHBoxLayout()
        buttons.addWidget(self.counter)
        buttons.addStretch()
        buttons.addWidget(keep)
        buttons.addWidget(self.unlock_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(_label(f"UNLOCK {site.upper()}", "heading"))
        layout.addWidget(
            _label(
                "type the password below to unlock. paste is off on purpose.", "muted"
            )
        )
        layout.addWidget(box)
        layout.addWidget(self.input)
        layout.addLayout(buttons)

        self.input.textChanged.connect(self._on_text)
        self.input.returnPressed.connect(self._submit)
        self.unlock_button.clicked.connect(self._submit)
        keep.clicked.connect(self.reject)
        self._on_text("")

    def _on_text(self, text: str) -> None:
        self.counter.setText(f"{len(text)} / {len(self.password)}")
        self.counter.setStyleSheet("")
        self.unlock_button.setEnabled(len(text) == len(self.password))

    def _submit(self) -> None:
        if self.input.text() == self.password:
            self.accept()
        else:
            self.counter.setText("that doesn't match.")
            self.counter.setStyleSheet("color: #ba3c5b;")


def sudo_is_cached() -> bool:
    return subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0


def sudo_with_password(password: str) -> bool:
    """Validates and caches sudo credentials, so blocklib's own `sudo` calls
    from this process then run without prompting."""
    result = subprocess.run(
        ["sudo", "-S", "-v", "-p", ""],
        input=password + "\n",
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class AdminDialog(QDialog):
    """Asks for the Mac login password that blocklib needs to edit /etc/hosts.
    Only shown when sudo doesn't already have cached credentials."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Admin password")
        self.setModal(True)
        self.setMinimumWidth(440)

        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.input.setPlaceholderText("your Mac login password")
        self.error = _label("", "muted")
        ok = _button("continue", primary=True)
        cancel = _button("cancel")

        buttons = QHBoxLayout()
        buttons.addWidget(self.error)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(_label("ADMIN PASSWORD", "heading"))
        layout.addWidget(
            _label(
                "blocking edits /etc/hosts, which needs your Mac password. it isn't stored.",
                "muted",
            )
        )
        layout.addWidget(self.input)
        layout.addLayout(buttons)

        ok.clicked.connect(self._submit)
        self.input.returnPressed.connect(self._submit)
        cancel.clicked.connect(self.reject)

    def _submit(self) -> None:
        if sudo_with_password(self.input.text()):
            self.accept()
        else:
            self.input.clear()
            self.error.setText("wrong password")
            self.error.setStyleSheet("color: #ba3c5b;")


def ensure_admin(parent: QWidget | None = None) -> bool:
    """True once sudo can run without prompting, asking for the password if
    needed. False if the user cancels."""
    if sudo_is_cached():
        return True
    return AdminDialog(parent).exec() == QDialog.Accepted
