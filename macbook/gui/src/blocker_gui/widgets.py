"""Custom widgets: an animated toggle switch, the logo, and toast messages."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QGraphicsOpacityEffect, QLabel, QWidget

from . import theme


class ToggleSwitch(QAbstractButton):
    """A square on/off switch with a sliding knob. Clicking emits
    `toggled_by_user` with the requested state; the owner decides whether the
    change actually happens (unblocking needs the password first) and calls
    set_on() to make it stick."""

    toggled_by_user = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(56, 30)
        self._on = False
        self._pos = 0.0  # 0 = off, 1 = on; animated
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.clicked.connect(lambda: self.toggled_by_user.emit(not self._on))

    def is_on(self) -> bool:
        return self._on

    def set_on(self, on: bool, animate: bool = True) -> None:
        self._on = on
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if on else 0.0)
            self._anim.start()
        else:
            self.knob = 1.0 if on else 0.0

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def sizeHint(self) -> QSize:
        return QSize(56, 30)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off, on = QColor(theme.BORDER), QColor(theme.ACCENT)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRect(self.rect())
        inset = 4
        size = self.height() - inset * 2
        x = inset + (self.width() - size - inset * 2) * self._pos
        p.setBrush(QColor(theme.BG if self._pos > 0.5 else theme.FG))
        p.drawRect(QRectF(x, inset, size, size))


class Logo(QWidget):
    """The app icon: an orange square with an x, like the TUI's (x) marker."""

    def __init__(self, size: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        stroke = max(2.0, s * 0.09)
        pen = QPen(QColor(theme.ACCENT), stroke)
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen)
        half = stroke / 2
        p.drawRect(QRectF(half, half, s - stroke, s - stroke))
        pen.setWidthF(stroke * 1.1)
        p.setPen(pen)
        a, b = s * 0.32, s * 0.68
        p.drawLine(QPointF(a, a), QPointF(b, b))
        p.drawLine(QPointF(a, b), QPointF(b, a))


class Toast(QLabel):
    """A short message that fades in at the bottom right of its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(220)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._fade.finished.connect(self._on_fade_done)

    def show_message(self, text: str, tone: str = "ok") -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        parent = self.parentWidget()
        self.move(
            parent.width() - self.width() - 24, parent.height() - self.height() - 24
        )
        self.raise_()
        self.show()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(2600 if tone == "ok" else 5000)

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade_done(self) -> None:
        if self._fade.endValue() == 0.0:
            self.hide()
