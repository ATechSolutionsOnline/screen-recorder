# Screen Recorder

A clean, standalone Windows screen recorder with audio capture, cursor overlay, and one-click installer — no Python or FFmpeg required on the target machine.

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Screen capture** — full screen or custom region
- **System audio** — records microphone or Stereo Mix (system audio)
- **Real Windows cursor** — overlays the exact live cursor via GDI `DrawIconEx`
- **Pause / Resume** — with audio sync (silence inserted to keep A/V in sync)
- **Mic mute** — toggle microphone during recording
- **Resolution output** — Native, 1080p, or 720p
- **Countdown timer** — 3-second countdown before recording starts
- **MP4 output** — video + audio merged via bundled FFmpeg
- **Standalone installer** — single `.exe`, no dependencies needed on target machine

---

## Screenshots

> *Recording in progress — dark UI with live timer and controls*

---

## Download

Head to [**Releases**](../../releases) and download `ScreenRecorderSetup.exe`.  
Run the installer and launch **Screen Recorder** from the desktop or Start menu.

---

## Build from Source

### Requirements

- Windows 10 / 11 (64-bit)
- Python 3.10 or newer
- FFmpeg on PATH (or installed via winget)

### Quick start

```bat
git clone https://github.com/ATechSolutionsOnline/screen-recorder.git
cd screen-recorder
install.bat        # installs Python dependencies
python main.py     # run without building
```

### Build the installer

```bat
build.bat
```

This runs `build.py` which:
1. Bundles the app + FFmpeg into a standalone exe via PyInstaller
2. Creates `dist/ScreenRecorderSetup.exe` via Inno Setup 6

> Inno Setup 6 is installed automatically via winget if not found.

---

## Project Structure

```
screen-recorder/
├── main.py              # Entry point — DPI awareness + launches GUI
├── gui.py               # Tkinter UI (dark theme, pill toggles)
├── recorder.py          # Core recording engine (video + audio threads)
├── region_selector.py   # Full-screen drag-to-select region overlay
├── config.py            # JSON config load/save (AppData when frozen)
├── create_icon.py       # Generates icon.ico at build time
├── build.py             # One-click build: PyInstaller → Inno Setup
├── build.bat            # Convenience wrapper for build.py
├── install.bat          # pip install -r requirements.txt
└── requirements.txt     # Python dependencies
```

---

## Dependencies

| Package | Purpose |
|---|---|
| [mss](https://github.com/BoboTiG/python-mss) | Fast screen capture |
| [opencv-python](https://github.com/opencv/opencv-python) | Video encoding (XVID) |
| [numpy](https://numpy.org) | Frame and audio array processing |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | Audio input stream |
| [scipy](https://scipy.org) | WAV file writing |
| [Pillow](https://github.com/python-pillow/Pillow) | Icon generation |
| [FFmpeg](https://ffmpeg.org) | Audio/video merge (bundled in installer) |
| [PyInstaller](https://pyinstaller.org) | Standalone exe packaging |

---

## How It Works

1. **Video** — `mss` captures frames at the chosen FPS into a temp `.avi` (XVID)
2. **Audio** — `sounddevice` streams microphone/system audio into a temp `.wav`
3. **Cursor** — Win32 `GetCursorInfo` + `DrawIconEx` renders the exact live cursor per frame
4. **Merge** — FFmpeg combines `.avi` + `.wav` into a final `.mp4` (AAC audio, copy video)
5. **Fallback** — if FFmpeg is unavailable, saves `.avi` + `.wav` separately

---

## Hotkeys

| Key | Action |
|---|---|
| `F9` | Start / Stop recording |
| `F10` | Pause / Resume |

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
