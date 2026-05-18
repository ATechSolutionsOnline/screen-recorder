"""
audio_test.py  --  Run this on any device to diagnose audio issues.
Usage:  python audio_test.py
"""
import sys, os

PASS = "[  OK  ]"
FAIL = "[ FAIL ]"
WARN = "[ WARN ]"

results = []

def check(label, ok, detail=""):
    sym = PASS if ok else FAIL
    line = f"{sym}  {label}"
    if detail:
        line += f"\n         {detail}"
    print(line)
    results.append(ok)
    return ok

print("=" * 60)
print("  Screen Recorder — Audio Diagnostic")
print("=" * 60)

# ── 1. Python version ──────────────────────────────────────────────
check("Python version", sys.version_info >= (3, 10),
      f"Found: {sys.version.split()[0]}  (need 3.10+)")

# ── 2. sounddevice import ─────────────────────────────────────────
try:
    import sounddevice as sd
    check("sounddevice import", True, f"v{sd.__version__}")
except Exception as e:
    check("sounddevice import", False, str(e))
    print("\nRun:  pip install sounddevice")
    sys.exit(1)

# ── 3. PortAudio DLL loads ────────────────────────────────────────
try:
    devs = sd.query_devices()
    check("PortAudio DLL", True, f"{len(devs)} audio devices found")
except Exception as e:
    check("PortAudio DLL", False, str(e))
    print("\nPortAudio could not load. Reinstall sounddevice:\n  pip install --force-reinstall sounddevice")
    sys.exit(1)

# ── 4. scipy ─────────────────────────────────────────────────────
try:
    import scipy.io.wavfile
    import scipy
    check("scipy import", True, f"v{scipy.__version__}")
except Exception as e:
    check("scipy import", False, str(e))

# ── 5. numpy ─────────────────────────────────────────────────────
try:
    import numpy as np
    check("numpy import", True, f"v{np.__version__}")
except Exception as e:
    check("numpy import", False, str(e))

# ── 6. Windows Microphone Privacy ────────────────────────────────
try:
    import winreg
    _PATH = (r"SOFTWARE\Microsoft\Windows\CurrentVersion"
             r"\CapabilityAccessManager\ConsentStore\microphone")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PATH) as k:
        val, _ = winreg.QueryValueEx(k, "Value")
    ok = str(val).lower() != "deny"
    check("Windows Mic Privacy", ok,
          f"Registry value = '{val}'"
          + ("" if ok else
             "\nFix: Settings → Privacy & Security → Microphone"
             "\n     Turn ON 'Let desktop apps access your microphone'"))
except Exception as e:
    check("Windows Mic Privacy", True,
          f"Registry unreadable ({e}) — assuming allowed")

# ── 7. List all input devices ─────────────────────────────────────
print("\n--- Input Devices ---")
input_devs = [(i, d) for i, d in enumerate(sd.query_devices())
              if d['max_input_channels'] > 0]
if input_devs:
    for i, d in input_devs:
        print(f"  [{i:2d}] {d['name'][:52]}  "
              f"(ch={d['max_input_channels']}, "
              f"sr={int(d['default_samplerate'])})")
else:
    print("  (none found — no microphone detected)")

# ── 8. List loopback / stereo mix devices ────────────────────────
print("\n--- System Audio Loopback Devices ---")
loopback_found = False
try:
    hostapis = sd.query_hostapis()
    wasapi = next((i for i, h in enumerate(hostapis)
                   if 'WASAPI' in h['name']), None)
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0:
            n = d['name'].lower()
            is_lb = (wasapi is not None
                     and d.get('hostapi') == wasapi
                     and 'loopback' in n)
            is_sm = any(k in n for k in ('stereo mix', 'what u hear'))
            if is_lb or is_sm:
                print(f"  [{i:2d}] {d['name'][:52]}")
                loopback_found = True
except Exception as e:
    print(f"  Error: {e}")
if not loopback_found:
    print("  (none — system audio won't be captured)")
    print("  Tip: Right-click speaker → Sounds → Recording tab")
    print("       Right-click blank area → Show Disabled Devices")
    print("       Enable 'Stereo Mix' if listed")

# ── 9. Try opening mic for 1 second (try default then first real device) ──
print("\n--- Microphone Live Test (1 second) ---")
try:
    import numpy as np, time as _t

    buf = []
    def _cb(indata, frames, t, s):
        buf.append(indata.copy())

    # Find a working input device (device=None fails on some systems)
    mic_dev = None
    try:
        sd.query_devices(kind='input')   # test if default query works
    except Exception:
        for i, d in enumerate(sd.query_devices()):
            if d.get('max_input_channels', 0) > 0:
                mic_dev = i
                break

    opened = False
    for rate in [44100, 48000]:
        try:
            with sd.InputStream(device=mic_dev, channels=1, samplerate=rate,
                                dtype='float32', callback=_cb):
                print(f"         (recording at {rate} Hz for 1 second — speak now!)")
                _t.sleep(1.0)
            opened = True
            break
        except Exception as e:
            buf.clear()
            last_err = str(e)

    if not opened:
        check("Mic opens and captures", False, last_err)
    else:
        audio = np.concatenate(buf) if buf else np.zeros((1,1))
        peak  = float(np.abs(audio).max())
        rms   = float(np.sqrt(np.mean(audio**2)))
        check("Mic opens and captures", True,
              f"Peak={peak:.4f}  RMS={rms:.4f}"
              + ("  << sound detected!" if rms > 0.001 else
                 "  << silent (mic open but quiet — try speaking next time)"))
except Exception as e:
    check("Mic opens and captures", False, str(e))

# ── Summary ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"  ALL {total} checks PASSED — audio should work fine.")
else:
    print(f"  {passed}/{total} checks passed — see FAIL items above.")
print("=" * 60)
input("\nPress Enter to close...")
