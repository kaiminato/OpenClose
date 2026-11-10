"""Open/Close voice-controlled display mask.

Usage:
    python app.py              # run the app
    python app.py --selftest   # load model + open mic, exit 0 on success
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from cursor_util import get_physical_pos, physical_rect, physical_to_logical, set_physical_pos
from identify import show_identify_badges
from levelmeter import rms_to_db
from overlay import MaskOverlay
from paths import asset
from recognizer import DEFAULT_TRIGGER_DELAY, VoiceRecognizer, default_input_device, list_input_devices
from theme import apply_dark_theme
from wininput import MouseBlocker, foreground_window_info

APP_TITLE = "Open/Close Voice Control"
DEFAULT_OPACITY_PERCENT = 5
QUIET_DB = -50.0           # below this the mic is considered silent
QUIET_BLOCKS_WARN = 30     # 3 s of silence (10 blocks/s) -> show the "no sound" warning
CONTROL_HEIGHT = 34

# While one of these programs owns the foreground window (e.g. a screenshot tool's
# region-capture overlay), the mask steps aside: mouse blocking is paused and the mask
# drops below the tool's overlay so a region can be picked anywhere. Lower-case exe names.
PASSTHROUGH_APPS = {
    "sharex.exe",
    "snippingtool.exe",          # Windows Snipping Tool
    "screenclippinghost.exe",    # Windows Win+Shift+S overlay
    "greenshot.exe",
    "lightshot.exe",
    "flameshot.exe",
}
FOREGROUND_POLL_MS = 100


def _fill_row(box: QComboBox) -> None:
    """Make a combobox stretch to the row width while long entries get elided, not widen the window."""
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(24)


class WordBridge(QObject):
    """Carries recognizer-thread events to the GUI thread."""

    word = Signal(str)
    level = Signal(float)


class ControlWindow(QWidget):
    def __init__(self, icon: QIcon) -> None:
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(icon)
        # The layout uses SetFixedSize, so the window takes its width from the widest row.
        # The status label spans the full width and sets that width (plus 2 x 18 px margins).
        self._content_width = 484

        self.recognizer: VoiceRecognizer | None = None
        self.bridge = WordBridge()
        self.bridge.word.connect(self.on_word)
        self.bridge.level.connect(self.on_level)
        self._quiet_blocks = 0

        self.overlay = MaskOverlay(DEFAULT_OPACITY_PERCENT / 100)
        self.overlay.dismiss_requested.connect(self.hide_mask)
        self.blocker = MouseBlocker()
        self._mask_rect: tuple[int, int, int, int] | None = None
        self._passthrough = False
        self._fg_timer = QTimer(self)
        self._fg_timer.setInterval(FOREGROUND_POLL_MS)
        self._fg_timer.timeout.connect(self._watch_foreground)
        self._saved_pos: tuple[int, int] | None = None  # physical pixels
        self._quitting = False
        self._tray_hint_shown = False

        # ----- widgets ------------------------------------------------------
        self.display_box = QComboBox()
        self.display_box.setFixedHeight(CONTROL_HEIGHT)
        _fill_row(self.display_box)
        self._screens: list[QScreen] = []
        self._refresh_screens()
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self._refresh_screens())
        app.screenRemoved.connect(lambda _s: self._refresh_screens())

        self.identify_button = QPushButton("Identify")
        self.identify_button.setObjectName("small")
        self.identify_button.setFixedHeight(CONTROL_HEIGHT)
        self.identify_button.setToolTip("Flash each display's number for two seconds")
        self.identify_button.clicked.connect(self.identify_displays)
        display_row = QHBoxLayout()
        display_row.setSpacing(8)
        display_row.addWidget(self.display_box, 1)
        display_row.addWidget(self.identify_button)

        self.mic_box = QComboBox()
        self.mic_box.setFixedHeight(CONTROL_HEIGHT)
        _fill_row(self.mic_box)
        self._devices = list_input_devices()
        for idx, name in self._devices:
            self.mic_box.addItem(name, idx)
            self.mic_box.setItemData(self.mic_box.count() - 1, name, Qt.ItemDataRole.ToolTipRole)
        self._select_default_mic()

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setFixedSize(68, CONTROL_HEIGHT)
        self.opacity_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.opacity_slider.valueChanged.connect(self.opacity_spin.setValue)
        self.opacity_spin.valueChanged.connect(self.opacity_slider.setValue)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.opacity_slider.setValue(DEFAULT_OPACITY_PERCENT)
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(8)
        opacity_row.addWidget(self.opacity_slider, 1)
        opacity_row.addWidget(self.opacity_spin)

        # Response delay: how long a lone "open"/"close" must stand before it fires.
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setRange(1, 20)  # tenths of a second: 0.1 .. 2.0 s
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 2.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setSuffix(" s")
        self.delay_spin.setFixedSize(68, CONTROL_HEIGHT)
        self.delay_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.delay_slider.valueChanged.connect(lambda v: self.delay_spin.setValue(v / 10))
        self.delay_spin.valueChanged.connect(lambda v: self.delay_slider.setValue(round(v * 10)))
        self.delay_spin.valueChanged.connect(self._on_delay_changed)
        self.delay_slider.setValue(round(DEFAULT_TRIGGER_DELAY * 10))
        delay_row = QHBoxLayout()
        delay_row.setSpacing(8)
        delay_row.addWidget(self.delay_slider, 1)
        delay_row.addWidget(self.delay_spin)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(self._content_width)

        self.listen_button = QPushButton("Start listening")
        self.listen_button.setObjectName("primary")
        self.listen_button.setFixedHeight(40)
        self.listen_button.clicked.connect(self.toggle_listening)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        # ----- layout -------------------------------------------------------
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Display", display_row)
        form.addRow("Microphone", self.mic_box)
        form.addRow("Mask opacity", opacity_row)
        form.addRow("Response delay", delay_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addWidget(self.listen_button)
        layout.addWidget(self.error_label)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # ----- tray ---------------------------------------------------------
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_TITLE)
        menu = QMenu()
        self.show_action = QAction("Show window", menu)
        self.show_action.triggered.connect(self.show_window)
        self.tray_listen_action = QAction("Start listening", menu)
        self.tray_listen_action.triggered.connect(self.toggle_listening)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(self.show_action)
        menu.addAction(self.tray_listen_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ----- displays / mics ------------------------------------------------

    def _refresh_screens(self) -> None:
        current = self.display_box.currentData()
        self._screens = list(QGuiApplication.screens())
        primary = QGuiApplication.primaryScreen()
        self.display_box.clear()
        for i, screen in enumerate(self._screens):
            g = screen.geometry()
            label = f"{i + 1}: {screen.name()} {g.width()}x{g.height()}"
            if screen is primary:
                label += " (primary)"
            self.display_box.addItem(label, screen.name())
        idx = self.display_box.findData(current) if current is not None else -1
        if idx < 0 and primary is not None and primary in self._screens:
            idx = self._screens.index(primary)
        self.display_box.setCurrentIndex(max(idx, 0))

    def _selected_screen(self) -> QScreen | None:
        i = self.display_box.currentIndex()
        return self._screens[i] if 0 <= i < len(self._screens) else None

    def identify_displays(self) -> None:
        self._badges = show_identify_badges(self, self._screens)

    def _select_default_mic(self) -> None:
        if not self._devices:
            self._show_error("No microphone found.")
            return
        default = default_input_device()
        idx = self.mic_box.findData(default) if default is not None else -1
        self.mic_box.setCurrentIndex(max(idx, 0))

    def _selected_mic(self) -> int | None:
        data = self.mic_box.currentData()
        return int(data) if data is not None else None

    # ----- helpers --------------------------------------------------------

    def _show_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))

    def _on_opacity_changed(self, percent: int) -> None:
        self.overlay.set_opacity(percent / 100)

    def _on_delay_changed(self, seconds: float) -> None:
        if self.recognizer:
            self.recognizer.trigger_delay = seconds

    def _listening(self) -> bool:
        return bool(self.recognizer and self.recognizer.running)

    def _update_status(self) -> None:
        # "Closed" = the display is covered by the mask; "Opened" = listening, no mask.
        if self.overlay.isVisible():
            self.status_label.setText("Closed")
        elif self._listening():
            self.status_label.setText("Opened")
        else:
            self.status_label.setText("Idle")

    def _set_listen_ui(self, listening: bool) -> None:
        text = "Stop listening" if listening else "Start listening"
        self.listen_button.setText(text)
        self.tray_listen_action.setText(text)
        self.listen_button.setProperty("active", "true" if listening else "false")
        self.listen_button.style().unpolish(self.listen_button)
        self.listen_button.style().polish(self.listen_button)
        self.mic_box.setEnabled(not listening)
        self._quiet_blocks = 0
        self._update_status()

    # ----- recognizer feedback --------------------------------------------

    def on_level(self, rms: float) -> None:
        if rms_to_db(rms) < QUIET_DB:
            self._quiet_blocks += 1
            if self._quiet_blocks == QUIET_BLOCKS_WARN:
                self._show_error(
                    "No sound is reaching the app. Check the selected microphone and its "
                    "input level in Windows sound settings."
                )
        else:
            if self._quiet_blocks >= QUIET_BLOCKS_WARN:
                self._show_error("")
            self._quiet_blocks = 0

    # ----- listening ------------------------------------------------------

    def toggle_listening(self) -> None:
        if self._listening():
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self) -> None:
        self._show_error("")
        try:
            self.recognizer = VoiceRecognizer(
                on_word=self.bridge.word.emit,
                device=self._selected_mic(),
                on_level=self.bridge.level.emit,
                trigger_delay=self.delay_spin.value(),
            )
            self.recognizer.start()
        except Exception as exc:  # model missing, mic busy, etc.
            self.recognizer = None
            self._show_error(str(exc))
            return
        self._set_listen_ui(True)

    def stop_listening(self) -> None:
        if self.recognizer:
            self.recognizer.stop()
            self.recognizer = None
        self._set_listen_ui(False)

    # ----- mask -----------------------------------------------------------

    def on_word(self, word: str) -> None:
        print(f"Recognized: {word}")
        if word == "close":
            self.show_mask()
        elif word == "open":
            self.hide_mask()

    def show_mask(self) -> None:
        """Voice command "close": cover the selected display."""
        if self.overlay.isVisible():
            return
        screen = self._selected_screen()
        if screen is None:
            self._show_error("No display selected.")
            return
        rect = physical_rect(screen)
        pos = get_physical_pos()
        # Only remember (and later restore) the cursor if it is on the masked display.
        if rect[0] <= pos[0] < rect[2] and rect[1] <= pos[1] < rect[3]:
            self._saved_pos = pos
            marker = physical_to_logical(screen, *pos)
        else:
            self._saved_pos = None
            marker = None
        self.overlay.show_on(screen, marker)

        # Keep mouse events over the masked display from reaching anything underneath.
        # The cursor can still move over the mask; see wininput.MouseBlocker.
        self._mask_rect = rect
        self._passthrough = False
        self._block_mouse()
        self._fg_timer.start()
        self._update_status()

    def hide_mask(self) -> None:
        """Voice command "open": remove the mask and restore the cursor."""
        if not self.overlay.isVisible():
            return
        self._fg_timer.stop()
        self._passthrough = False
        self.blocker.release()
        self.overlay.hide_mask()
        if self._saved_pos is not None:
            set_physical_pos(*self._saved_pos)
        self._update_status()

    def _block_mouse(self) -> None:
        if self._mask_rect is None:
            return
        try:
            self.blocker.block(*self._mask_rect)
        except OSError as exc:
            self._show_error(f"Could not install the mouse block: {exc}")

    def _capture_overlay_in_front(self) -> bool:
        """True while a screenshot tool's capture overlay is the foreground window.

        The overlay is recognised as a topmost window of a known tool that covers the
        masked display; the tool's ordinary windows (settings, main window) do not count.
        """
        name, topmost, (left, top, right, bottom) = foreground_window_info()
        if name not in PASSTHROUGH_APPS or not topmost or self._mask_rect is None:
            return False
        ml, mt, mr, mb = self._mask_rect
        return left <= ml and top <= mt and right >= mr and bottom >= mb

    def _watch_foreground(self) -> None:
        """Pause blocking while a capture overlay is in front; resume after."""
        wants_passthrough = self._capture_overlay_in_front()
        if wants_passthrough == self._passthrough:
            return
        self._passthrough = wants_passthrough
        if wants_passthrough:
            self.blocker.release()
            self.overlay.suspend()
            self.status_label.setText("Closed (screenshot)")
        else:
            self.overlay.resume()
            self._block_mouse()
            self._update_status()

    # ----- tray / lifecycle -----------------------------------------------

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def quit_app(self) -> None:
        self._quitting = True
        self.stop_listening()
        self._fg_timer.stop()
        self.blocker.release()
        self.overlay.hide_mask()
        self.overlay.close()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._quitting or not self.tray.isVisible():
            super().closeEvent(event)
            return
        # Keep running in the tray; listening and the mask are unaffected.
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(
                APP_TITLE,
                "Still running in the tray. Right-click the icon to show the window or quit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )


def selftest() -> int:
    """Load the model and open the default mic for a second; exit code 0 on success.

    Used to check a packaged build: `OpenClose.exe --selftest`.
    """
    import time

    try:
        rec = VoiceRecognizer(on_word=lambda _w: None, device=default_input_device())
        rec.start()
        time.sleep(1)
        rec.stop()
    except Exception as exc:
        print(f"SELFTEST FAILED: {exc}")
        return 1
    print("SELFTEST OK")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)  # the tray keeps the app alive
    apply_dark_theme(app)
    icon = QIcon(str(asset("icon.ico")))
    app.setWindowIcon(icon)
    window = ControlWindow(icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
