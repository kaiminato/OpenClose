"""Dark theme for the control window and tray menu."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from paths import asset

BG = "#1b1d23"
SURFACE = "#262932"
SURFACE_HOVER = "#2d313c"
SURFACE_PRESSED = "#20232b"
BORDER = "#363a46"
TEXT = "#e6e8ee"
MUTED = "#9aa0ae"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#729dff"
DANGER = "#ff6b6b"
DANGER_HOVER = "#ff8585"

QSS = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 10pt;
}}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#status {{
    font-size: 20pt;
    font-weight: 600;
    padding: 12px;
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#error {{ color: {DANGER}; }}
QLabel#heard {{ font-size: 12pt; font-weight: 600; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 0 8px;
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {ACCENT}; }}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    image: url("{{CHEVRON}}");
    width: 12px; height: 12px;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: 0;
    padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; background: {SURFACE_HOVER}; }}
QPushButton:pressed {{ background: {SURFACE_PRESSED}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary[active="true"] {{ background: {DANGER}; border-color: {DANGER}; }}
QPushButton#primary[active="true"]:hover {{ background: {DANGER_HOVER}; }}
QPushButton#small {{ padding: 0 14px; }}

QSlider::groove:horizontal {{ height: 6px; background: {BORDER}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -5px 0;
    background: white; border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}

QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 6px; }}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 4px; }}

QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(BG))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(MUTED))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(MUTED))
    app.setPalette(pal)
    chevron = asset("chevron-down.svg").as_posix()
    app.setStyleSheet(QSS.replace("{CHEVRON}", chevron))
