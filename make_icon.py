"""Draw the app icon with Qt and write assets/icon.png + assets/icon.ico.

Usage:
    python make_icon.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

ASSETS = Path(__file__).resolve().parent / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0  # scale factor from the 256-px design grid

    # Background: rounded square with a blue -> violet gradient.
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4f86ff"))
    grad.setColorAt(1.0, QColor("#8b5cf6"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(0, 0, size, size), 56 * s, 56 * s)

    # Monitor frame.
    frame = QRectF(44 * s, 56 * s, 168 * s, 110 * s)
    p.setPen(QPen(QColor("white"), 14 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor(255, 255, 255, 40))
    p.drawRoundedRect(frame, 14 * s, 14 * s)
    # Stand.
    p.drawLine(QPointF(128 * s, 166 * s), QPointF(128 * s, 196 * s))
    p.drawLine(QPointF(92 * s, 200 * s), QPointF(164 * s, 200 * s))

    # Translucent "mask" covering the left part of the screen, clipped to the frame.
    inner = frame.adjusted(7 * s, 7 * s, -7 * s, -7 * s)
    clip = QPainterPath()
    clip.addRoundedRect(inner, 10 * s, 10 * s)
    p.save()
    p.setClipPath(clip)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 150))
    p.drawRect(QRectF(inner.left(), inner.top(), inner.width() * 0.55, inner.height()))
    p.restore()

    # Cursor arrow on the mask.
    if size >= 32:
        tip = QPointF(104 * s, 88 * s)
        arrow = [(0, 0), (0, 46), (12, 35), (20, 54), (28, 50), (20, 32), (34, 32)]
        poly = QPolygonF([QPointF(tip.x() + dx * s, tip.y() + dy * s) for dx, dy in arrow])
        p.setPen(QPen(QColor("#1b1d23"), 4 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QColor("white"))
        p.drawPolygon(poly)

    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path: Path, images: list[QImage]) -> None:
    """Write a multi-size .ico using PNG-compressed entries (supported since Windows Vista)."""
    entries = [png_bytes(im) for im in images]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    for im, data in zip(images, entries):
        w = 0 if im.width() >= 256 else im.width()
        h = 0 if im.height() >= 256 else im.height()
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + directory + b"".join(entries))


def main() -> int:
    _app = QGuiApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)
    images = [draw_icon(s) for s in SIZES]
    images[-1].save(str(ASSETS / "icon.png"))
    write_ico(ASSETS / "icon.ico", images)
    print(f"Wrote {ASSETS / 'icon.png'} and {ASSETS / 'icon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
