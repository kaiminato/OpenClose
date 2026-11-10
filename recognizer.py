"""Offline keyword recognizer for the words "open" and "close" using Vosk.

Two Vosk recognizers run on the same audio:
- a grammar-restricted one (open / close / unknown) that triggers the commands when a
  whole utterance is exactly one of the keywords, and
- an optional free-form one whose text can be shown for diagnostics.

Microphone level (RMS) is reported for every audio block so the UI can draw a meter.
"""
from __future__ import annotations

import json
import math
import queue
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from paths import base_dir

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600          # frames per audio callback (0.1 s) -> 10 meter updates per second
KEYWORDS = ("open", "close")
GRAMMAR = json.dumps(list(KEYWORDS) + ["[unk]"])
COOLDOWN_SECONDS = 0.5     # ignore repeat hits within this window
DEFAULT_TRIGGER_DELAY = 0.5  # seconds the lone keyword must stand before it fires

MODEL_DIR = base_dir() / "model"

SetLogLevel(-1)  # silence Kaldi's startup chatter

WordCallback = Callable[[str], None]
LevelCallback = Callable[[float], None]          # RMS in 0..1
TextCallback = Callable[[str, bool], None]       # (text, is_final)


class VoiceRecognizer:
    """Listens on the microphone and reports keywords, free text and input level.

    All callbacks run on the recognizer's worker thread, not the GUI thread.
    """

    def __init__(
        self,
        on_word: WordCallback,
        device: Optional[int] = None,
        on_level: Optional[LevelCallback] = None,
        on_text: Optional[TextCallback] = None,
        trigger_delay: float = DEFAULT_TRIGGER_DELAY,
    ):
        if not (MODEL_DIR / "conf").is_dir():
            raise FileNotFoundError(
                f"Vosk model not found at {MODEL_DIR}. Run `python setup_model.py` first."
            )
        self._on_word = on_word
        self._on_level = on_level
        self._on_text = on_text
        self._device = device
        self.trigger_delay = float(trigger_delay)
        self._model = Model(str(MODEL_DIR))
        self._audio_q: "queue.Queue[bytes]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.RawInputStream] = None
        self._reset_state()

    # ----- public API -----------------------------------------------------

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        while not self._audio_q.empty():
            self._audio_q.get_nowait()
        self._reset_state()

        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=self._device,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._thread = threading.Thread(target=self._run, name="vosk-recognizer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def process(self, data: bytes) -> None:
        """Feed one block of 16 kHz mono int16 audio. Public so tests can bypass the mic."""
        if self._on_level is not None:
            self._on_level(_rms(data))
        self._audio_time += len(data) / 2 / SAMPLE_RATE  # int16 samples -> seconds

        # --- command recognizer (grammar) -------------------------------
        # A keyword counts only when it stands alone. The live partial result shows the
        # word as soon as it is spoken; once the partial has been exactly that word for
        # `trigger_delay` seconds (no more words followed) it fires. Vosk's own end of
        # utterance is the fallback, e.g. when the delay is longer than its silence rule.
        if self._rec_cmd.AcceptWaveform(data):
            text = json.loads(self._rec_cmd.Result()).get("text", "").strip()
            if text in KEYWORDS and not self._fired:
                self._fire(text)
            self._fired = False
            self._candidate = None
        else:
            partial = json.loads(self._rec_cmd.PartialResult()).get("partial", "").strip()
            if partial in KEYWORDS:
                if partial != self._candidate:
                    self._candidate = partial
                    self._candidate_since = self._audio_time
                elif not self._fired and self._audio_time - self._candidate_since >= self.trigger_delay:
                    self._fired = True
                    self._fire(partial)
            else:
                self._candidate = None  # silence, unknown, or more words -> not a lone keyword

        # --- display recognizer (free text) -----------------------------
        if self._on_text is not None:
            if self._rec_free.AcceptWaveform(data):
                text = json.loads(self._rec_free.Result()).get("text", "").strip()
                if text:
                    self._on_text(text, True)
                else:
                    self._on_text("", False)
            else:
                partial = json.loads(self._rec_free.PartialResult()).get("partial", "").strip()
                self._on_text(partial, False)

    # ----- internals ------------------------------------------------------

    def _reset_state(self) -> None:
        self._rec_cmd = KaldiRecognizer(self._model, SAMPLE_RATE, GRAMMAR)
        self._rec_free = KaldiRecognizer(self._model, SAMPLE_RATE)
        self._audio_time = 0.0            # seconds of audio processed (deterministic clock)
        self._last_hit = -COOLDOWN_SECONDS
        self._candidate: Optional[str] = None
        self._candidate_since = 0.0
        self._fired = False               # keyword already fired in the current utterance

    def _fire(self, word: str) -> None:
        if self._audio_time - self._last_hit >= COOLDOWN_SECONDS:
            self._last_hit = self._audio_time
            self._on_word(word)

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if self._stop.is_set():
            return
        self._audio_q.put(bytes(indata))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._audio_q.get(timeout=0.2)
            except queue.Empty:
                continue
            self.process(data)


def _rms(data: bytes) -> float:
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(samples * samples))) / 32768.0)


def list_input_devices() -> list[tuple[int, str]]:
    """Return (index, name) for every recording device on the default host API.

    Windows exposes each microphone once per audio API (MME, DirectSound, WASAPI,
    WDM-KS); restricting to the default API keeps the list to one entry per mic.
    """
    try:
        default_api = sd.default.hostapi
    except Exception:
        default_api = None
    all_devices = list(sd.query_devices())
    inputs = [(i, d) for i, d in enumerate(all_devices) if d.get("max_input_channels", 0) > 0]

    # MME truncates names to 31 characters; the other APIs carry the full name.
    full_names = [d["name"] for _, d in inputs if d.get("hostapi") != default_api]

    devices = []
    for idx, info in inputs:
        if default_api is not None and info.get("hostapi") != default_api:
            continue
        name = info["name"]
        if len(name) >= 31:
            for full in full_names:
                if full.startswith(name) and len(full) > len(name):
                    name = full
                    break
        devices.append((idx, name))
    return devices


def default_input_device() -> Optional[int]:
    try:
        dev = sd.default.device[0]
        return dev if dev is not None and dev >= 0 else None
    except Exception:
        return None
