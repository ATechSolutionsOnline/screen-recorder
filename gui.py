import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config
from recorder import ScreenRecorder, AUDIO_AVAILABLE, AUDIO_LOAD_ERROR
from region_selector import RegionSelector

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#0b0b18",
    "panel":   "#111122",
    "card":    "#16162a",
    "border":  "#232342",
    "input":   "#1c1c35",
    "hover":   "#2a2a4a",

    "red":     "#ff4757",
    "green":   "#2ed573",
    "orange":  "#ffa502",
    "blue":    "#45aaf2",
    "teal":    "#00d2c8",
    "purple":  "#a29bfe",

    "text":    "#e8eaf0",
    "dim":     "#8892a4",
    "muted":   "#232342",
}

# Resolution presets
_RES_OPTIONS = {
    "Native":    None,
    "1920×1080": (1920, 1080),
    "1280×720":  (1280, 720),
}


# ── Pill toggle ───────────────────────────────────────────────────────────────

class _Pill(tk.Label):
    """Clickable ON/OFF pill backed by a BooleanVar."""
    def __init__(self, parent, var: tk.BooleanVar, **kw):
        super().__init__(parent, font=("Segoe UI", 8, "bold"),
                         padx=8, pady=2, cursor="hand2",
                         relief=tk.FLAT, bd=0, **kw)
        self._var = var
        self._refresh()
        self.bind("<Button-1>", lambda _: self._click())
        var.trace_add("write", lambda *_: self._refresh())

    def _click(self):
        self._var.set(not self._var.get())

    def _refresh(self):
        on = self._var.get()
        self.config(
            text="ON" if on else "OFF",
            bg=C["teal"]  if on else C["muted"],
            fg="#061a18"  if on else C["dim"],
        )


# ── Application ───────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self._cfg          = config.load()
        self._recorder     = None
        self._region       = None
        self._rec_blink_on = False

        self._setup_window()
        self._build_ui()
        self._bind_hotkeys()
        self._tick()

    # ── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title("Screen Recorder")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._center(480, 618)
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def _center(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section(self, parent, label, pady_top=8):
        """Titled section card. Returns body frame."""
        outer = tk.Frame(parent, bg=C["border"])
        outer.pack(fill=tk.X, padx=14, pady=(pady_top, 0))

        inner = tk.Frame(outer, bg=C["card"])
        inner.pack(fill=tk.BOTH, padx=1, pady=1)

        # Section label row
        hdr = tk.Frame(inner, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=label,
                 font=("Segoe UI", 7, "bold"),
                 fg=C["teal"], bg=C["panel"],
                 padx=12, pady=5).pack(side=tk.LEFT)

        body = tk.Frame(inner, bg=C["card"])
        body.pack(fill=tk.X, padx=12, pady=(6, 10))
        return body

    def _radio(self, parent, text, var, val, cmd=None):
        kw = {"command": cmd} if cmd else {}
        return tk.Radiobutton(
            parent, text=text, variable=var, value=val,
            bg=C["card"], fg=C["text"],
            selectcolor=C["input"],
            activebackground=C["card"],
            font=("Segoe UI", 10),
            relief=tk.FLAT, bd=0, **kw)

    def _btn(self, parent, text, cmd, bg, fg,
             hover=None, state=tk.NORMAL, px=16, py=9):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg,
            activebackground=hover or C["hover"],
            activeforeground=fg,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, bd=0,
            padx=px, pady=py,
            cursor="hand2", state=state)

    def _label_pill_row(self, parent, label_text, var):
        """A label + pill toggle on the same row, returns the row frame."""
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row, text=label_text,
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        _Pill(row, var).pack(side=tk.LEFT, padx=(6, 0))
        return row

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):

        # ══ CONTROLS — packed FIRST so they are always visible ══════════════
        ctrl_wrap = tk.Frame(self, bg=C["panel"])
        ctrl_wrap.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(ctrl_wrap, height=1, bg=C["border"]).pack(fill=tk.X)

        btn_row = tk.Frame(ctrl_wrap, bg=C["panel"], pady=12)
        btn_row.pack()

        self._start_btn = self._btn(
            btn_row, "▶  Start", self._start,
            C["green"], "#071608", hover="#23c45e")
        self._start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._pause_btn = self._btn(
            btn_row, "⏸  Pause", self._pause,
            C["input"], C["text"],
            state=tk.DISABLED, px=13)
        self._pause_btn.pack(side=tk.LEFT, padx=5)

        self._stop_btn = self._btn(
            btn_row, "■  Stop", self._stop,
            C["input"], C["red"],
            state=tk.DISABLED, px=13)
        self._stop_btn.pack(side=tk.LEFT, padx=5)

        self._mic_btn = self._btn(
            btn_row, "🎤  Mic", self._toggle_mic,
            C["input"], C["blue"],
            state=tk.DISABLED, px=13)
        self._mic_btn.pack(side=tk.LEFT, padx=(5, 0))

        # ══ HEADER ══════════════════════════════════════════════════════════
        hdr = tk.Frame(self, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, height=1, bg=C["border"]).pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(hdr, text="⏺  Screen Recorder",
                 font=("Segoe UI", 12, "bold"),
                 fg=C["text"], bg=C["panel"],
                 pady=10).pack(side=tk.LEFT, padx=16)

        tk.Label(hdr, text="F9  start/stop   F10  pause",
                 font=("Segoe UI", 8),
                 fg=C["dim"], bg=C["panel"]).pack(side=tk.RIGHT, padx=16)

        # ══ TIMER BLOCK ══════════════════════════════════════════════════════
        tb = tk.Frame(self, bg=C["bg"])
        tb.pack(fill=tk.X, pady=(14, 6))

        self._rec_lbl = tk.Label(tb, text="⬤  REC",
                                  font=("Segoe UI", 9, "bold"),
                                  fg=C["bg"], bg=C["bg"])
        self._rec_lbl.pack()

        self._timer_var = tk.StringVar(value="00:00:00")
        self._timer_lbl = tk.Label(tb, textvariable=self._timer_var,
                                    font=("Segoe UI Mono", 36, "bold"),
                                    fg=C["text"], bg=C["bg"])
        self._timer_lbl.pack()

        self._status_var = tk.StringVar(value="Ready to record")
        tk.Label(tb, textvariable=self._status_var,
                 font=("Segoe UI", 9),
                 fg=C["dim"], bg=C["bg"]).pack(pady=(2, 0))

        # ══ CAPTURE ══════════════════════════════════════════════════════════
        cap = self._section(self, "CAPTURE", pady_top=10)

        r_row = tk.Frame(cap, bg=C["card"])
        r_row.pack(fill=tk.X)

        self._area_var = tk.StringVar(value="fullscreen")
        self._radio(r_row, "Full Screen", self._area_var,
                    "fullscreen", self._on_area_change).pack(side=tk.LEFT)
        self._radio(r_row, "Custom Region", self._area_var,
                    "custom", self._on_area_change).pack(side=tk.LEFT, padx=(12, 0))

        self._region_btn = tk.Button(
            r_row, text="Select…", command=self._select_region,
            bg=C["input"], fg=C["blue"],
            activebackground=C["hover"], activeforeground=C["blue"],
            font=("Segoe UI", 9), relief=tk.FLAT, bd=0,
            padx=9, pady=3, cursor="hand2", state=tk.DISABLED)
        self._region_btn.pack(side=tk.RIGHT)

        self._region_lbl = tk.Label(cap, text="",
                                     font=("Segoe UI", 8),
                                     fg=C["teal"], bg=C["card"])
        self._region_lbl.pack(anchor=tk.W, pady=(2, 0))

        # ══ AUDIO ══════════════════════════════════════════════════════════
        aud = self._section(self, "AUDIO")

        aud_top = tk.Frame(aud, bg=C["card"])
        aud_top.pack(fill=tk.X)

        self._audio_enable_var = tk.BooleanVar(
            value=self._cfg.get("record_audio", True) and AUDIO_AVAILABLE)

        tk.Label(aud_top, text="System Audio + Mic",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        tk.Label(aud_top, text="  Audio",
                 font=("Segoe UI", 9), fg=C["dim"],
                 bg=C["card"]).pack(side=tk.LEFT, padx=(12, 3))
        _Pill(aud_top, self._audio_enable_var).pack(side=tk.LEFT)

        if not AUDIO_AVAILABLE:
            err_short = (AUDIO_LOAD_ERROR or "sounddevice not installed")[:72]
            tk.Label(aud, text=f"⚠  {err_short}",
                     font=("Segoe UI", 8),
                     fg=C["orange"], bg=C["card"]).pack(anchor=tk.W, pady=(3, 0))

        # ══ OPTIONS ══════════════════════════════════════════════════════════
        opt = self._section(self, "OPTIONS")

        # Row 1 — FPS · Resolution
        row1 = tk.Frame(opt, bg=C["card"])
        row1.pack(fill=tk.X, pady=(0, 6))

        tk.Label(row1, text="FPS",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        self._fps_var = tk.StringVar(value=str(self._cfg.get("fps", 30)))
        ttk.Combobox(row1, textvariable=self._fps_var,
                     values=["10", "15", "24", "30", "60"],
                     width=4, state="readonly").pack(side=tk.LEFT, padx=(4, 16))

        tk.Label(row1, text="Resolution",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        res_saved = self._cfg.get("output_resolution", "Native")
        if res_saved not in _RES_OPTIONS:
            res_saved = "Native"
        self._res_var = tk.StringVar(value=res_saved)
        ttk.Combobox(row1, textvariable=self._res_var,
                     values=list(_RES_OPTIONS.keys()),
                     width=10, state="readonly").pack(side=tk.LEFT, padx=(4, 0))

        # Row 2 — Cursor · Countdown toggles
        row2 = tk.Frame(opt, bg=C["card"])
        row2.pack(fill=tk.X, pady=(0, 6))

        self._cursor_var = tk.BooleanVar(value=self._cfg.get("show_cursor", True))
        tk.Label(row2, text="🖱  Show Cursor",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        _Pill(row2, self._cursor_var).pack(side=tk.LEFT, padx=(5, 20))

        self._countdown_var = tk.BooleanVar(value=self._cfg.get("countdown", True))
        tk.Label(row2, text="⏱  3s Countdown",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        _Pill(row2, self._countdown_var).pack(side=tk.LEFT, padx=5)

        # Row 3 — Hide window toggle
        row3 = tk.Frame(opt, bg=C["card"])
        row3.pack(fill=tk.X)

        self._hide_var = tk.BooleanVar(value=self._cfg.get("hide_on_record", True))
        tk.Label(row3, text="👁  Hide window while recording",
                 font=("Segoe UI", 9), fg=C["text"],
                 bg=C["card"]).pack(side=tk.LEFT)
        _Pill(row3, self._hide_var).pack(side=tk.LEFT, padx=5)

        # ══ OUTPUT ═══════════════════════════════════════════════════════════
        out = self._section(self, "OUTPUT")

        out_row = tk.Frame(out, bg=C["card"])
        out_row.pack(fill=tk.X)

        self._out_var = tk.StringVar(value=self._cfg.get("output_dir", ""))
        tk.Entry(out_row, textvariable=self._out_var,
                 bg=C["input"], fg=C["text"],
                 insertbackground=C["text"],
                 relief=tk.FLAT, font=("Segoe UI", 9)
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        tk.Button(out_row, text="📁", command=self._browse_output,
                  bg=C["input"], fg=C["text"],
                  activebackground=C["hover"], activeforeground=C["text"],
                  font=("Segoe UI", 10), relief=tk.FLAT, bd=0,
                  padx=7, pady=3, cursor="hand2"
                  ).pack(side=tk.LEFT, padx=(4, 0))

        tk.Button(out_row, text="Open", command=self._open_folder,
                  bg=C["input"], fg=C["dim"],
                  activebackground=C["hover"], activeforeground=C["text"],
                  font=("Segoe UI", 9), relief=tk.FLAT, bd=0,
                  padx=7, pady=3, cursor="hand2"
                  ).pack(side=tk.LEFT, padx=(4, 0))

    # ── Hotkeys ───────────────────────────────────────────────────────────────

    def _bind_hotkeys(self):
        self.bind_all("<F9>",  lambda _: self._hotkey_startstop())
        self.bind_all("<F10>", lambda _: self._pause())

    def _hotkey_startstop(self):
        if self._recorder and self._recorder.recording:
            self._stop()
        else:
            self._start()

    # ── Capture area ──────────────────────────────────────────────────────────

    def _on_area_change(self):
        custom = self._area_var.get() == "custom"
        self._region_btn.config(state=tk.NORMAL if custom else tk.DISABLED)
        if not custom:
            self._region = None
            self._region_lbl.config(text="")

    def _select_region(self):
        self.withdraw()
        self.after(250, lambda: RegionSelector(self._on_region_selected, master=self).show())

    def _on_region_selected(self, region):
        self.deiconify()
        if region:
            self._region = region
            self._region_lbl.config(
                text=f"  {region['width']} × {region['height']}"
                     f"  at  ({region['left']}, {region['top']})")
        else:
            self._area_var.set("fullscreen")
            self._region = None
            self._region_lbl.config(text="")
            self._region_btn.config(state=tk.DISABLED)

    # ── Output folder ─────────────────────────────────────────────────────────

    def _browse_output(self):
        path = filedialog.askdirectory(initialdir=self._out_var.get())
        if path:
            self._out_var.set(path)

    def _open_folder(self):
        p = self._out_var.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            messagebox.showinfo("Not Found",
                                "Folder will be created when recording starts.")

    # ── Recording control ─────────────────────────────────────────────────────

    def _start(self):
        if self._recorder and self._recorder.recording:
            return
        if self._area_var.get() == "custom" and not self._region:
            messagebox.showwarning("No Region",
                                   "Please select a recording region first.")
            return
        out = self._out_var.get().strip()
        if not out:
            messagebox.showwarning("No Output Folder",
                                   "Please choose an output folder.")
            return
        self._start_btn.config(state=tk.DISABLED)
        if self._countdown_var.get():
            self._do_countdown(3)
        else:
            self._begin_recording()

    def _do_countdown(self, n):
        if n > 0:
            self._timer_var.set(f"  {n}  ")
            self._status_var.set("Get ready…")
            self.after(1000, lambda: self._do_countdown(n - 1))
        else:
            self._timer_var.set("00:00:00")
            self._begin_recording()

    def _begin_recording(self):
        region     = self._region if self._area_var.get() == "custom" else None
        output_res = _RES_OPTIONS.get(self._res_var.get())

        self._recorder = ScreenRecorder(
            output_dir        = self._out_var.get().strip(),
            fps               = int(self._fps_var.get()),
            region            = region,
            record_audio      = self._audio_enable_var.get(),
            show_cursor       = self._cursor_var.get(),
            output_resolution = output_res,
        )
        self._recorder.start()

        self._pause_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.NORMAL)
        if self._audio_enable_var.get() and AUDIO_AVAILABLE:
            self._mic_btn.config(state=tk.NORMAL, fg=C["blue"])

        if self._hide_var.get():
            self.iconify()
        self._save_config()

    def _pause(self):
        if not self._recorder:
            return
        if self._recorder.paused:
            self._recorder.resume()
            self._pause_btn.config(text="⏸  Pause", fg=C["text"])
            self._status_var.set("Recording…")
            if self._hide_var.get():
                self.iconify()
        else:
            self._recorder.pause()
            self._pause_btn.config(text="▶  Resume", fg=C["orange"])
            self._status_var.set("Paused")
            self.deiconify()
            self.lift()

    def _stop(self):
        if not self._recorder:
            return
        self.deiconify()
        self.lift()
        self._status_var.set("Saving…")
        self._start_btn.config(state=tk.DISABLED)
        self._pause_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.DISABLED)
        self._mic_btn.config(state=tk.DISABLED)
        rec = self._recorder   # capture ref before thread
        def _do_stop():
            path = rec.stop()
            warn = rec._audio_warn
            self.after(0, lambda: self._on_saved(path, warn))
        threading.Thread(target=_do_stop, daemon=True).start()

    def _toggle_mic(self):
        if not self._recorder:
            return
        muted = self._recorder.toggle_mic()
        self._mic_btn.config(
            text="🔇  Muted" if muted else "🎤  Mic",
            fg=C["red"]     if muted else C["blue"])
        self._status_var.set(
            "Mic muted" if muted
            else ("Paused" if self._recorder.paused else "Recording…"))

    def _on_saved(self, path, audio_warn=None):
        self._recorder = None
        self._start_btn.config(state=tk.NORMAL)
        self._pause_btn.config(state=tk.DISABLED, text="⏸  Pause", fg=C["text"])
        self._stop_btn.config(state=tk.DISABLED)
        self._mic_btn.config(state=tk.DISABLED, text="🎤  Mic", fg=C["blue"])
        self._timer_var.set("00:00:00")
        self._set_rec("off")

        if path and os.path.exists(path):
            mb = os.path.getsize(path) / 1e6
            self._status_var.set(
                f"Saved  ·  {os.path.basename(path)}  ({mb:.1f} MB)")
            if audio_warn:
                messagebox.showwarning("Audio Notice", audio_warn)
            if messagebox.askyesno("Recording Saved",
                                   f"File saved:\n{path}\n"
                                   f"Size: {mb:.1f} MB\n\nOpen folder?"):
                os.startfile(os.path.dirname(path))
        else:
            self._status_var.set("Save failed — check output folder")
            if audio_warn:
                messagebox.showwarning("Audio Notice", audio_warn)
            messagebox.showerror("Save Error", "Could not save the recording.")

    # ── Timer / REC blink ─────────────────────────────────────────────────────

    def _tick(self):
        if self._recorder and self._recorder.recording:
            secs     = int(self._recorder.elapsed_seconds())
            h, m, s  = secs // 3600, (secs % 3600) // 60, secs % 60
            self._timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            frames   = self._recorder.frame_count
            size_mb  = self._recorder.approx_size_mb()
            if self._recorder.paused:
                self._set_rec("pause")
            else:
                self._set_rec("blink")
                self._status_var.set(
                    f"Recording  ·  {frames} frames  ·  {size_mb:.1f} MB")
        self.after(500, self._tick)

    def _set_rec(self, mode):
        if mode == "off":
            self._rec_lbl.config(fg=C["bg"])
            self._timer_lbl.config(fg=C["text"])
            self.title("Screen Recorder")
        elif mode == "pause":
            self._rec_lbl.config(fg=C["orange"])
            self._timer_lbl.config(fg=C["orange"])
            self.title("⏸  PAUSED — Screen Recorder")
        elif mode == "blink":
            self._rec_blink_on = not self._rec_blink_on
            self._rec_lbl.config(fg=C["red"] if self._rec_blink_on else C["bg"])
            self._timer_lbl.config(fg=C["red"])
            self.title("⬤  REC — Screen Recorder")

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self._recorder and self._recorder.recording:
            self.deiconify()
            if messagebox.askyesno("Quit",
                                   "Recording in progress. Stop and quit?"):
                threading.Thread(
                    target=self._recorder.stop, daemon=True).start()
                self.destroy()
        else:
            self.destroy()

    def _save_config(self):
        self._cfg.update({
            "output_dir":        self._out_var.get(),
            "fps":               int(self._fps_var.get()),
            "record_audio":      self._audio_enable_var.get(),
            "countdown":         self._countdown_var.get(),
            "hide_on_record":    self._hide_var.get(),
            "show_cursor":       self._cursor_var.get(),
            "output_resolution": self._res_var.get(),
        })
        config.save(self._cfg)
