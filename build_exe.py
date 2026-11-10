"""Build a standalone Windows app with PyInstaller.

Usage:
    pip install pyinstaller
    python setup_model.py      # the model must exist before building
    python build_exe.py

Output: dist/OpenClose/OpenClose.exe (plus its support files). Copy the whole
dist/OpenClose folder to another PC; Python does not need to be installed there.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
APP_NAME = "OpenClose"


def main() -> int:
    if not (MODEL_DIR / "conf").is_dir():
        print("Model not found. Run `python setup_model.py` first.")
        return 1

    for stale in (ROOT / "build", ROOT / "dist" / APP_NAME):
        if stale.exists():
            shutil.rmtree(stale)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--windowed",                      # no console window
        "--onedir",                        # folder build: faster start, easier to debug
        "--icon", str(ROOT / "assets" / "icon.ico"),
        "--add-data", f"{MODEL_DIR}{';'}model",
        "--add-data", f"{ROOT / 'assets'}{';'}assets",
        "--collect-all", "vosk",           # libvosk.dll and friends
        "--collect-all", "sounddevice",    # bundled PortAudio dll
        # Trim unused Qt modules to keep the folder small.
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtCharts",
        "--exclude-module", "PySide6.QtDataVisualization",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.QtBluetooth",
        "--exclude-module", "PySide6.QtLocation",
        "--exclude-module", "PySide6.QtPositioning",
        "--exclude-module", "PySide6.QtSerialPort",
        "--exclude-module", "PySide6.QtRemoteObjects",
        "--exclude-module", "PySide6.QtSensors",
        "--exclude-module", "PySide6.QtTextToSpeech",
        str(ROOT / "app.py"),
    ]
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print(f"\nBuilt: {ROOT / 'dist' / APP_NAME / (APP_NAME + '.exe')}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
