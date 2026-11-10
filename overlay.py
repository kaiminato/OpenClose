"""Always-on-top translucent mask that covers one display and marks a saved cursor position."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

from theme import ACCENT
from wininput import force_foreground, set_topmost

MARKER_DIAMETER = 5        # small red dot at the saved cursor position
BORDER_WIDTH = 2           # blue frame around the masked display
BORDER_COLOR = QColor(ACCENT)
RAISE_INTERVAL_MS = 500


class MaskOverlay(QWidget):
    """Frameless, topmost white mask with a small marker at the saved cursor position.

    Mouse blocking over the masked display is done by `wininput.MouseBlocker` (owned by
    the controller); this window only draws. Emits `dismiss_requested` on Esc so the
    controller can run its normal "close" handling (cursor snap-back).
    """

    dismiss_requested = Signal()

    def __init__(self, opacity: float = 0.10) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Display mask")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._opacity = 0.10
        self._marker: QPoint | None = None  # in overlay-local coordinates
        self.set_opacity(opacity)

        self._raise_timer = QTimer(self)
        self._raise_timer.setInterval(RAISE_INTERVAL_MS)
        self._raise_timer.timeout.connect(self._keep_on_top)

    # ----- public API -----------------------------------------------------

    @property
    def opacity(self) -> float:
        return self._opacity

    def set_opacity(self, fraction: float) -> None:
        self._opacity = max(0.0, min(1.0, float(fraction)))
        self.update()

    def show_on(self, screen: QScreen, saved_global_pos: QPoint | None) -> None:
        """Cover `screen`; draw the marker at `saved_global_pos` (logical) if given."""
        geo = screen.geometry()
        self.setScreen(screen)
        self.setGeometry(geo)
        self._marker = None if saved_global_pos is None else saved_global_pos - geo.topLeft()
        self.show()
        self.raise_()
        # Take the foreground: apps that read raw mouse input only while they are the
        # foreground window stop receiving it, and Esc works on the mask immediately.
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        self._raise_timer.start()
        self.update()

    def hide_mask(self) -> None:
        self._raise_timer.stop()
        self.hide()

    def suspend(self) -> None:
        """Step aside: stop re-raising and drop below other topmost windows (e.g. a
        screenshot tool's capture overlay). The mask stays visible."""
        self._raise_timer.stop()
        set_topmost(int(self.winId()), False)

    def resume(self) -> None:
        set_topmost(int(self.winId()), True)
        self.raise_()
        self._raise_timer.start()

    # ----- events ---------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(255, 255, 255, round(self._opacity * 255)))

        # 2 px blue frame along the display edge.
        half = BORDER_WIDTH / 2
        painter.setPen(QPen(BORDER_COLOR, BORDER_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(self.rect()).adjusted(half, half, -half, -half))

        if self._marker is None:
            return
        m = self._marker

        # 5x5 px red dot centred on the saved cursor position.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(230, 30, 30)))
        r = MARKER_DIAMETER / 2
        painter.drawEllipse(QRectF(m.x() - r, m.y() - r, MARKER_DIAMETER, MARKER_DIAMETER))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss_requested.emit()
        else:
            super().keyPressEvent(event)

    # ----- internals ------------------------------------------------------

    def _keep_on_top(self) -> None:
        if self.isVisible():
            self.raise_()
