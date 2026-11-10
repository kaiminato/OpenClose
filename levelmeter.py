"""Scrolling microphone level graph."""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from theme import ACCENT, BORDER, DANGER, MUTED, SURFACE

MIN_DB = -60.0
HOT_DB = -6.0


def rms_to_db(rms: float) -> float:
    return 20.0 * math.log10(max(rms, 1e-6))


class LevelMeter(QWidget):
    def __init__(self, history: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history = history
        self._values: deque[float] = deque(maxlen=history)  # dB values
        self._active = False
        self._peak_db = MIN_DB
        self.setMinimumHeight(72)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    # ----- public API -----------------------------------------------------

    def push(self, rms: float) -> None:
        db = rms_to_db(rms)
        self._values.append(db)
        self._peak_db = max(self._peak_db * 0.9 + db * 0.1, db)  # fast attack, slow decay
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._values.clear()
            self._peak_db = MIN_DB
        self.update()

    @property
    def latest_db(self) -> float:
        return self._values[-1] if self._values else MIN_DB

    # ----- painting -------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(SURFACE))
        p.drawRoundedRect(r, 8, 8)

        inner = r.adjusted(8, 8, -8, -8)
        if not self._active:
            p.setPen(QColor(MUTED))
            p.drawText(inner, Qt.AlignmentFlag.AlignCenter, "Microphone idle")
            return

        # Reference lines at -40 and -20 dB.
        p.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
        for ref in (-40.0, -20.0):
            y = inner.bottom() - inner.height() * self._norm(ref)
            p.drawLine(int(inner.left()), int(y), int(inner.right()), int(y))

        # Bars, newest on the right.
        n = self._history
        bar_w = inner.width() / n
        p.setPen(Qt.PenStyle.NoPen)
        for i, db in enumerate(self._values):
            x = inner.left() + (n - len(self._values) + i) * bar_w
            h = inner.height() * self._norm(db)
            color = QColor(DANGER) if db > HOT_DB else QColor(ACCENT)
            p.setBrush(color)
            p.drawRect(QRectF(x + 0.5, inner.bottom() - h, max(bar_w - 1.0, 1.0), h))

        # Current level readout.
        p.setPen(QColor("white"))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        p.setFont(font)
        p.drawText(inner, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, f"{self.latest_db:5.0f} dB")

    @staticmethod
    def _norm(db: float) -> float:
        return max(0.0, min(1.0, (db - MIN_DB) / (0.0 - MIN_DB)))
