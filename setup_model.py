"""Download the small English Vosk model into ./model (run once).

Usage:
    python setup_model.py
"""
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
ZIP_PATH = ROOT / f"{MODEL_NAME}.zip"


def _progress(block_num: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        return
    done = min(block_num * block_size, total_size)
    pct = done * 100 // total_size
    sys.stdout.write(
        f"\r  downloading... {done // (1024 * 1024)} MB / {total_size // (1024 * 1024)} MB ({pct}%)"
    )
    sys.stdout.flush()


def main() -> None:
    if (MODEL_DIR / "conf").is_dir():
        print(f"Model already present at {MODEL_DIR}. Nothing to do.")
        return

    print(f"Fetching {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, ZIP_PATH, reporthook=_progress)
    print("\n  extracting...")

    extract_root = ROOT / "_model_tmp"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(extract_root)

    inner = extract_root / MODEL_NAME
    if not inner.is_dir():
        raise SystemExit(f"Unexpected zip layout: {MODEL_NAME} folder not found")

    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    shutil.move(str(inner), str(MODEL_DIR))
    shutil.rmtree(extract_root)
    ZIP_PATH.unlink()

    print(f"Done. Model installed at {MODEL_DIR}")


if __name__ == "__main__":
    main()
