import contextlib
import os
import sys
import time
import ctypes
import ctypes.wintypes as _wt
import threading
import subprocess
from datetime import datetime

import mss
import cv2
import numpy as np


# ── Win32 structures for real cursor capture ──────────────────────────────────

class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize",      _wt.DWORD),
        ("flags",       _wt.DWORD),
        ("hCursor",     _wt.HANDLE),
        ("ptScreenPos", _wt.POINT),
    ]

class _ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon",    _wt.BOOL),
        ("xHotspot", _wt.DWORD),
        ("yHotspot", _wt.DWORD),
        ("hbmMask",  _wt.HANDLE),
        ("hbmColor", _wt.HANDLE),
    ]

class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize",          ctypes.c_uint32),
        ("biWidth",         ctypes.c_int32),
        ("biHeight",        ctypes.c_int32),
        ("biPlanes",        ctypes.c_uint16),
        ("biBitCount",      ctypes.c_uint16),
        ("biCompression",   ctypes.c_uint32),
        ("biSizeImage",     ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed",       ctypes.c_uint32),
        ("biClrImportant",  ctypes.c_uint32),
    ]

class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]

_u32 = ctypes.windll.user32
_g32 = ctypes.windll.gdi32

# ── Declare argtypes so ctypes uses 64-bit HANDLE values correctly ────────────
_HANDLE  = ctypes.c_void_p
_BOOL    = _wt.BOOL
_DWORD   = _wt.DWORD
_INT     = ctypes.c_int
_UINT    = ctypes.c_uint

_u32.GetCursorPos.argtypes      = [ctypes.POINTER(_wt.POINT)]
_u32.GetCursorPos.restype       = _BOOL
_u32.GetCursorInfo.argtypes     = [ctypes.POINTER(_CURSORINFO)]
_u32.GetCursorInfo.restype      = _BOOL
_u32.GetIconInfo.argtypes       = [_HANDLE, ctypes.POINTER(_ICONINFO)]
_u32.GetIconInfo.restype        = _BOOL
_u32.GetSystemMetrics.argtypes  = [_INT]
_u32.GetSystemMetrics.restype   = _INT
_u32.GetDC.argtypes             = [_HANDLE]
_u32.GetDC.restype              = _HANDLE
_u32.ReleaseDC.argtypes         = [_HANDLE, _HANDLE]
_u32.ReleaseDC.restype          = _INT
_u32.DrawIconEx.argtypes        = [_HANDLE, _INT, _INT, _HANDLE,
                                    _INT, _INT, _UINT, _HANDLE, _UINT]
_u32.DrawIconEx.restype         = _BOOL

_g32.DeleteObject.argtypes      = [_HANDLE]
_g32.DeleteObject.restype       = _BOOL
_g32.CreateCompatibleDC.argtypes= [_HANDLE]
_g32.CreateCompatibleDC.restype = _HANDLE
_g32.DeleteDC.argtypes          = [_HANDLE]
_g32.DeleteDC.restype           = _BOOL
_g32.SelectObject.argtypes      = [_HANDLE, _HANDLE]
_g32.SelectObject.restype       = _HANDLE
_g32.CreateDIBSection.argtypes  = [_HANDLE, ctypes.c_void_p, _UINT,
                                    ctypes.POINTER(ctypes.c_void_p),
                                    _HANDLE, _DWORD]
_g32.CreateDIBSection.restype   = _HANDLE
_g32.PatBlt.argtypes            = [_HANDLE, _INT, _INT, _INT, _INT, _DWORD]
_g32.PatBlt.restype             = _BOOL
_g32.GdiFlush.argtypes          = []
_g32.GdiFlush.restype           = _BOOL


# ── Cursor helpers ────────────────────────────────────────────────────────────

def _cursor_pos() -> tuple[int, int]:
    pt = _wt.POINT()
    _u32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _draw_cursor(frame: np.ndarray, sx: int, sy: int,
                 frame_left: int = 0, frame_top: int = 0) -> None:
    """Overlay the exact live Windows cursor onto the frame using GDI DrawIconEx."""

    # ── 1. Get current cursor ────────────────────────────────────────────────
    ci = _CURSORINFO()
    ci.cbSize = ctypes.sizeof(_CURSORINFO)
    if not _u32.GetCursorInfo(ctypes.byref(ci)):
        return
    if not (ci.flags & 1):          # CURSOR_SHOWING
        return

    # ── 2. Get hotspot ───────────────────────────────────────────────────────
    ii = _ICONINFO()
    if not _u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return
    hx = int(ii.xHotspot)
    hy = int(ii.yHotspot)
    if ii.hbmMask:  _g32.DeleteObject(ii.hbmMask)
    if ii.hbmColor: _g32.DeleteObject(ii.hbmColor)

    # ── 3. Cursor dimensions ─────────────────────────────────────────────────
    cw = _u32.GetSystemMetrics(13) or 32   # SM_CXCURSOR
    ch = _u32.GetSystemMetrics(14) or 32   # SM_CYCURSOR

    # ── 4. Where to draw in frame ────────────────────────────────────────────
    ox = sx - frame_left - hx
    oy = sy - frame_top  - hy
    fh, fw = frame.shape[:2]

    fx0 = max(ox, 0);         fy0 = max(oy, 0)
    fx1 = min(ox + cw, fw);   fy1 = min(oy + ch, fh)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    cix0 = fx0 - ox;  ciy0 = fy0 - oy

    # ── 5. Render cursor into a 32-bit DIB via DrawIconEx ────────────────────
    bmi        = _BITMAPINFO()
    bmi.bmiHeader.biSize     = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth    = cw
    bmi.bmiHeader.biHeight   = -ch     # negative → top-down rows
    bmi.bmiHeader.biPlanes   = 1
    bmi.bmiHeader.biBitCount = 32

    pbits    = ctypes.c_void_p()
    hdc_scr  = _u32.GetDC(None)
    hdc_mem  = _g32.CreateCompatibleDC(hdc_scr)
    hbm      = _g32.CreateDIBSection(hdc_mem, ctypes.byref(bmi),
                                      0, ctypes.byref(pbits), None, 0)
    if not hbm:
        _g32.DeleteDC(hdc_mem)
        _u32.ReleaseDC(None, hdc_scr)
        return

    old_bm = _g32.SelectObject(hdc_mem, hbm)

    # Black background → transparent regions stay black
    _g32.PatBlt(hdc_mem, 0, 0, cw, ch, 0x00000042)   # BLACKNESS

    # Draw the real system cursor at (0,0) in the memory DC
    _u32.DrawIconEx(hdc_mem, 0, 0, ci.hCursor, cw, ch, 0, None, 3)  # DI_NORMAL

    # Deselect and flush before reading
    _g32.SelectObject(hdc_mem, old_bm)
    _g32.GdiFlush()

    # Read pixels directly from DIB memory (BGRA, top-down)
    buf_size = cw * ch * 4
    raw_arr  = (ctypes.c_uint8 * buf_size).from_address(pbits.value)
    cursor_bgra = np.frombuffer(raw_arr, dtype=np.uint8).reshape(ch, cw, 4).copy()

    _g32.DeleteObject(hbm)
    _g32.DeleteDC(hdc_mem)
    _u32.ReleaseDC(None, hdc_scr)

    # ── 6. Alpha-blend cursor onto frame ─────────────────────────────────────
    c_crop = cursor_bgra[ciy0: ciy0 + (fy1 - fy0),
                         cix0: cix0 + (fx1 - fx0)]

    # Use alpha channel; fall back to max-RGB luminance for monochrome cursors
    a = c_crop[:, :, 3:4].astype(np.float32) / 255.0
    if a.max() < 0.01:
        a = c_crop[:, :, :3].max(axis=2, keepdims=True).astype(np.float32) / 255.0

    f_crop = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    c_bgr  = c_crop[:, :, :3].astype(np.float32)

    frame[fy0:fy1, fx0:fx1] = np.clip(
        c_bgr * a + f_crop * (1.0 - a), 0, 255
    ).astype(np.uint8)


# ── Audio availability ────────────────────────────────────────────────────────

try:
    import sounddevice as sd
    import scipy.io.wavfile as wavfile
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False


def _find_loopback_device():
    """Return device index for system-audio capture (WASAPI loopback or Stereo Mix)."""
    if not AUDIO_AVAILABLE:
        return None
    try:
        hostapis = sd.query_hostapis()
        devices  = sd.query_devices()
        wasapi   = next((i for i, h in enumerate(hostapis)
                         if 'WASAPI' in h['name']), None)
        if wasapi is not None:
            for i, d in enumerate(devices):
                if (d.get('hostapi') == wasapi
                        and d.get('max_input_channels', 0) > 0
                        and 'loopback' in d['name'].lower()):
                    return i
        for i, d in enumerate(devices):
            if d.get('max_input_channels', 0) > 0:
                n = d['name'].lower()
                if any(k in n for k in ('stereo mix', 'what u hear', 'wave out mix')):
                    return i
    except Exception:
        pass
    return None


def _open_input(device, sr_pref, channels, blocksize, callback):
    """Open sd.InputStream with sample-rate fallbacks.  Returns (stream, sr, ch)."""
    if not AUDIO_AVAILABLE:
        return None, sr_pref, channels
    try:
        info   = sd.query_devices(device) if device is not None \
                 else sd.query_devices(kind='input')
        dev_sr = int(info.get('default_samplerate', sr_pref))
        ch     = min(max(int(info.get('max_input_channels', channels)), 1), channels)
    except Exception:
        dev_sr, ch = sr_pref, channels
    for rate in dict.fromkeys([sr_pref, dev_sr, 48000, 44100]):
        try:
            s = sd.InputStream(samplerate=rate, channels=ch, dtype='float32',
                               device=device, blocksize=blocksize,
                               callback=callback)
            return s, rate, ch
        except Exception:
            continue
    return None, sr_pref, channels


def _hidden_subprocess():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


# ── Recorder ─────────────────────────────────────────────────────────────────

class ScreenRecorder:
    def __init__(self, output_dir, fps=30, region=None,
                 record_audio=True,
                 show_cursor=True, output_resolution=None):
        self.output_dir        = output_dir
        self.fps               = fps
        self.region            = region
        self.record_audio      = record_audio and AUDIO_AVAILABLE
        self.show_cursor       = show_cursor
        self.output_resolution = output_resolution  # None | (W, H)

        self._recording  = False
        self._paused     = False
        self._mic_muted  = False

        self._video_thread = None
        self._audio_thread = None

        self._temp_video  = None
        self._temp_audio  = None
        self._output_path = None

        self._frame_count = 0
        self._start_time  = 0.0
        self._elapsed     = 0.0

        self._audio_sample_rate = 44100
        self._audio_chunks: list[np.ndarray] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        os.makedirs(self.output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._temp_video  = os.path.join(self.output_dir, f"rec_{ts}_v.avi")
        self._temp_audio  = os.path.join(self.output_dir, f"rec_{ts}_a.wav")
        self._output_path = os.path.join(self.output_dir, f"rec_{ts}.mp4")

        self._frame_count  = 0
        self._elapsed      = 0.0
        self._start_time   = time.perf_counter()
        self._paused       = False
        self._mic_muted    = False
        self._recording    = True
        self._audio_chunks = []

        self._video_thread = threading.Thread(target=self._video_loop, daemon=True)
        self._video_thread.start()

        if self.record_audio:
            self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
            self._audio_thread.start()

    def stop(self):
        self._recording = False
        self._paused    = False
        if self._video_thread:
            self._video_thread.join(timeout=15)
        if self._audio_thread:
            self._audio_thread.join(timeout=15)
        return self._finalize()

    def pause(self):
        if self._recording and not self._paused:
            self._elapsed += time.perf_counter() - self._start_time
            self._paused = True

    def resume(self):
        if self._recording and self._paused:
            self._start_time = time.perf_counter()
            self._paused = False

    def toggle_mic(self) -> bool:
        self._mic_muted = not self._mic_muted
        return self._mic_muted

    @property
    def mic_muted(self) -> bool:   return self._mic_muted
    @property
    def recording(self)  -> bool:  return self._recording
    @property
    def paused(self)     -> bool:  return self._paused
    @property
    def frame_count(self) -> int:  return self._frame_count

    def elapsed_seconds(self) -> float:
        if not self._recording:
            return 0.0
        return self._elapsed + (0 if self._paused
                                else time.perf_counter() - self._start_time)

    def approx_size_mb(self) -> float:
        try:
            if self._temp_video and os.path.exists(self._temp_video):
                return os.path.getsize(self._temp_video) / (1024 * 1024)
        except OSError:
            pass
        return 0.0

    # ── Video loop ────────────────────────────────────────────────────────────

    def _video_loop(self):
        with mss.MSS() as sct:
            mon    = self.region if self.region else sct.monitors[1]
            sw, sh = mon["width"], mon["height"]

            # Determine output dimensions
            if self.output_resolution:
                ow, oh = self.output_resolution
                do_resize = (ow != sw or oh != sh)
            else:
                ow, oh    = sw, sh
                do_resize = False

            fourcc   = cv2.VideoWriter_fourcc(*"XVID")
            writer   = cv2.VideoWriter(self._temp_video, fourcc, self.fps, (ow, oh))
            interval = 1.0 / self.fps

            try:
                while self._recording:
                    if self._paused:
                        time.sleep(0.01)
                        continue
                    t0    = time.perf_counter()
                    raw   = sct.grab(mon)
                    frame = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

                    if self.show_cursor:
                        mx, my = _cursor_pos()
                        _draw_cursor(frame, mx, my,
                                     mon.get("left", 0), mon.get("top", 0))

                    if do_resize:
                        frame = cv2.resize(frame, (ow, oh),
                                           interpolation=cv2.INTER_AREA)

                    writer.write(frame)
                    self._frame_count += 1
                    gap = interval - (time.perf_counter() - t0)
                    if gap > 0:
                        time.sleep(gap)
            finally:
                writer.release()

    # ── Audio loop ────────────────────────────────────────────────────────────

    def _audio_loop(self):
        SR  = self._audio_sample_rate   # 44100
        BLK = int(SR * 0.05)

        sys_buf, mic_buf = [], []
        _sys_sr = [SR]
        _mic_sr = [SR]

        def _stereo(data):
            if data.shape[1] == 1:
                return np.repeat(data, 2, axis=1)
            return data[:, :2]

        def _sys_cb(indata, frames, t, status):
            if self._paused:
                sys_buf.append(np.zeros((frames, 2), 'float32'))
            else:
                sys_buf.append(_stereo(indata).copy())

        def _mic_cb(indata, frames, t, status):
            if self._paused or self._mic_muted:
                mic_buf.append(np.zeros((frames, 2), 'float32'))
            else:
                mic_buf.append(_stereo(indata).copy())

        streams = []

        # System audio (WASAPI loopback or Stereo Mix)
        lb = _find_loopback_device()
        if lb is not None:
            s, sr, _ = _open_input(lb, SR, 2, BLK, _sys_cb)
            if s is not None:
                _sys_sr[0] = sr
                streams.append(s)

        # Microphone (default input device)
        s, sr, _ = _open_input(None, SR, 2, BLK, _mic_cb)
        if s is not None:
            _mic_sr[0] = sr
            streams.append(s)

        if not streams:
            return

        try:
            with contextlib.ExitStack() as stack:
                for s in streams:
                    stack.enter_context(s)
                while self._recording:
                    time.sleep(0.05)
        except Exception:
            pass

        sys_audio = np.concatenate(sys_buf, axis=0) if sys_buf else None
        mic_audio = np.concatenate(mic_buf, axis=0) if mic_buf else None

        if sys_audio is None and mic_audio is None:
            return

        # Resample mic to match system audio rate if they differ
        if sys_audio is not None and mic_audio is not None \
                and _sys_sr[0] != _mic_sr[0]:
            try:
                from scipy.signal import resample as _rs
                n = int(len(mic_audio) * _sys_sr[0] / _mic_sr[0])
                mic_audio = _rs(mic_audio, n).astype('float32')
            except Exception:
                mic_audio = None

        if sys_audio is not None and mic_audio is not None:
            n = max(len(sys_audio), len(mic_audio))
            def _pad(a):
                diff = n - len(a)
                return np.vstack([a, np.zeros((diff, 2), 'float32')]) if diff > 0 else a
            mixed    = np.clip(_pad(sys_audio) + _pad(mic_audio), -1.0, 1.0)
            final_sr = _sys_sr[0]
        elif sys_audio is not None:
            mixed, final_sr = sys_audio, _sys_sr[0]
        else:
            mixed, final_sr = mic_audio, _mic_sr[0]

        audio_i16 = (mixed * 32767).astype(np.int16)
        wavfile.write(self._temp_audio, final_sr, audio_i16)

    # ── Finalize ──────────────────────────────────────────────────────────────

    def _finalize(self):
        if not (self._temp_video and os.path.exists(self._temp_video)):
            return None

        has_audio = (
            self.record_audio
            and self._temp_audio
            and os.path.exists(self._temp_audio)
            and os.path.getsize(self._temp_audio) > 44
        )

        if has_audio and self._ffmpeg_merge():
            self._cleanup(self._temp_video, self._temp_audio)
            return self._output_path

        # FFmpeg unavailable or failed — single video-only file, no stray audio
        self._cleanup(self._temp_audio)
        avi = self._output_path.replace(".mp4", ".avi")
        try:
            os.rename(self._temp_video, avi)
        except OSError:
            avi = self._temp_video
        return avi

    def _ffmpeg_merge(self) -> bool:
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            return False
        try:
            if os.path.getsize(self._temp_video) == 0:
                return False
        except OSError:
            return False

        cmd = [
            ffmpeg, "-y",
            "-i", self._temp_video,
            "-i", self._temp_audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            self._output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300,
                                    startupinfo=_hidden_subprocess())
            if result.returncode != 0:
                log = self._output_path.replace(".mp4", "_merge_error.txt")
                try:
                    with open(log, "w", encoding="utf-8") as f:
                        f.write(result.stderr.decode("utf-8", errors="replace"))
                except OSError:
                    pass
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _find_ffmpeg() -> str | None:
        import shutil
        if getattr(sys, "frozen", False):
            bundled = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
            if os.path.exists(bundled):
                return bundled
        found = shutil.which("ffmpeg")
        if found:
            return found
        winget = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Microsoft", "WinGet", "Packages",
            "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
        )
        for root, _dirs, files in os.walk(winget):
            if "ffmpeg.exe" in files:
                return os.path.join(root, "ffmpeg.exe")
        return None

    @staticmethod
    def _cleanup(*paths):
        for p in paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
