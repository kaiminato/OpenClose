# Open/Close Voice Control

A Windows app that listens for the spoken words **"open"** and **"close"** (fully offline, using [Vosk](https://alphacephei.com/vosk/)) and uses them to show or hide a translucent mask over a display of your choice.

- **"close"** - covers the selected display with an always-on-top white mask (5 % opacity by default) framed by a 2 px blue border. If the mouse pointer is on that display, its position is remembered and marked with a small red dot.
- **"open"** - removes the mask and, if a position was remembered, moves the mouse pointer back to it.

Say the word on its own. A command inside a sentence ("open the door") is ignored. The app acts once the lone word has stood for the **Response delay** (default 0.5 s, adjustable 0.1-2.0 s in the window) with nothing said after it; a shorter delay reacts faster but gives you less time to continue a sentence before it fires.

The status box shows **Idle** (not listening), **Opened** (listening, display not covered) or **Closed** (mask showing).

While the mask is showing, the cursor can move over it as usual, but mouse events on that display are intercepted at the system level: no movement, click or wheel event reaches any window, hook or application underneath. The mask takes keyboard focus, so pressing **Esc** closes it without the voice command.

**Screenshot tools.** When ShareX, the Windows Snipping Tool, Greenshot, Lightshot or Flameshot owns the foreground window (for example during a region capture), the mask steps aside: mouse blocking pauses and the mask drops below the tool's overlay, so you can start or end a region anywhere, including over the mask. Blocking resumes as soon as the tool's window closes. The status shows "Closed (screenshot)" meanwhile. Note that the capture itself still contains the mask tint and border, because the tool grabs the screen before it shows its overlay; say "open" first if you want a clean shot. To add another tool, extend `PASSTHROUGH_APPS` in `app.py`.

## Setup (once)

```bash
pip install -r requirements.txt
python setup_model.py
```

The second command downloads the small English speech model (~40 MB) into `model/`.

## Run

```bash
python app.py
```

1. Pick the **Display** to cover (click **Identify** to flash each display's number) and the **Microphone** to listen on.
2. Adjust **Mask opacity** if 10 % is too faint or too strong (updates live).
3. Click **Start listening** and say "close" to cover the display or "open" to uncover it.

The control window stays on top of other windows. Closing it hides it to the system tray; the app keeps listening. Use the tray icon's menu to show the window again, toggle listening, or quit.

## Building a standalone exe

```bash
pip install pyinstaller
python build_exe.py
```

This produces `dist/OpenClose/OpenClose.exe`. Copy the whole `dist/OpenClose` folder to any Windows PC and double-click the exe; Python and the model are bundled inside.

## Files

- `app.py` - control window, wiring between voice, mask and cursor
- `overlay.py` - the translucent always-on-top mask with the cursor marker
- `recognizer.py` - microphone capture and Vosk keyword recognition
- `identify.py` - the numbered badges shown by the Identify button
- `theme.py` - dark theme (palette + stylesheet)
- `cursor_util.py` - DPI-safe cursor read/move via Win32
- `make_icon.py` - regenerates `assets/icon.ico` and `assets/icon.png`
- `setup_model.py` - downloads the Vosk model
- `build_exe.py` - builds the standalone exe
