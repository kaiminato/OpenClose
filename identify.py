"""Flash a large number on every display so the user can tell them apart."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

from theme import ACCENT, BG

BADGE_SIZE = 180
SHOW_MS = 2000


class IdentifyBadge(QWidget):
    def __init__(self, parent: QWidget | None, screen: QScreen, number: int) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._number = number

        g = screen.geometry()
        self.setScreen(screen)
        self.setGeometry(
            QRect(g.center().x() - BADGE_SIZE // 2, g.center().y() - BADGE_SIZE // 2, BADGE_SIZE, BADGE_SIZE)
        )
        QTimer.singleShot(SHOW_MS, self.close)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(3, 3, -3, -3)
        p.setPen(QPen(QColor(ACCENT), 5))
        bg = QColor(BG)
        bg.setAlpha(235)
        p.setBrush(bg)
        p.drawRoundedRect(r, 24, 24)

        font = QFont("Segoe UI", 72, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(self._number))


def show_identify_badges(parent: QWidget | None, screens: list[QScreen]) -> list[IdentifyBadge]:
    """Show a numbered badge (1-based, in the given order) centred on each screen."""
    badges = []
    for i, screen in enumerate(screens, start=1):
        badge = IdentifyBadge(parent, screen, i)
        badge.show()
        badge.raise_()
        badges.append(badge)
    return badges
