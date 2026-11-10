"""Cursor position helpers that work across monitors with different DPI scaling.

Qt's QCursor.setPos() mis-places the pointer when the current and target
monitors use different scale factors, so the real pointer is read and moved
through Win32 in physical pixels, and only the marker drawing converts to
Qt's logical coordinates.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint
from PySide6.QtGui import QScreen

_user32 = ctypes.windll.user32


def get_physical_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def set_physical_pos(x: int, y: int) -> None:
    _user32.SetCursorPos(int(x), int(y))


def physical_rect(screen: QScreen) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of `screen` in physical pixels, right/bottom exclusive."""
    geo = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    return geo.x(), geo.y(), geo.x() + round(geo.width() * dpr), geo.y() + round(geo.height() * dpr)


def physical_to_logical(screen: QScreen, x: int, y: int) -> QPoint:
    """Map a physical pixel position to Qt logical coordinates on `screen`.

    Qt 6 keeps each screen's native origin and scales only the extent, so a
    point is converted relative to the screen's top-left corner.
    """
    geo = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    lx = geo.x() + round((x - geo.x()) / dpr)
    ly = geo.y() + round((y - geo.y()) / dpr)
    return QPoint(lx, ly)
