import tkinter as tk


class RegionSelector:
    """
    Full-screen transparent overlay.
    The user drags to select a rectangle; on release the on_select callback
    is called with a mss-compatible region dict, or None on cancel / too small.
    """

    def __init__(self, on_select, master=None):
        self.on_select = on_select
        self._master = master
        self._root = None
        self._rect = None
        self._start_x = self._start_y = 0

    def show(self):
        self._root = tk.Toplevel(self._master)
        root = self._root

        # Cover entire virtual screen
        vx = root.winfo_vrootx()
        vy = root.winfo_vrooty()
        vw = root.winfo_screenwidth()
        vh = root.winfo_screenheight()
        root.geometry(f"{vw}x{vh}+{vx}+{vy}")

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.25)
        root.configure(bg="black")

        self._canvas = tk.Canvas(
            root, cursor="crosshair", bg="black",
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Instruction label
        self._label = tk.Label(
            self._canvas,
            text="Drag to select region  •  Esc to cancel",
            font=("Segoe UI", 13, "bold"),
            fg="white", bg="#1e1e2e",
            padx=12, pady=6,
        )
        self._canvas.create_window(vw // 2, 40, window=self._label)

        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",        self._on_drag)
        self._canvas.bind("<ButtonRelease-1>",  self._on_release)
        root.bind("<Escape>",                   self._on_cancel)

        root.focus_force()

    # ── Mouse handlers ─────────────────────────────────────────────────────────

    def _on_press(self, e):
        self._start_x, self._start_y = e.x, e.y
        if self._rect:
            self._canvas.delete(self._rect)
        self._rect = self._canvas.create_rectangle(
            e.x, e.y, e.x, e.y,
            outline="#f38ba8", width=2, fill="",
            dash=(4, 2),
        )

    def _on_drag(self, e):
        if self._rect:
            self._canvas.coords(self._rect, self._start_x, self._start_y, e.x, e.y)
            # Size hint
            w = abs(e.x - self._start_x)
            h = abs(e.y - self._start_y)
            self._label.config(text=f"{w} × {h}  •  Esc to cancel")

    def _on_release(self, e):
        x1 = min(self._start_x, e.x)
        y1 = min(self._start_y, e.y)
        x2 = max(self._start_x, e.x)
        y2 = max(self._start_y, e.y)
        self._root.destroy()

        if (x2 - x1) > 20 and (y2 - y1) > 20:
            self.on_select({
                "top":    y1,
                "left":   x1,
                "width":  x2 - x1,
                "height": y2 - y1,
            })
        else:
            self.on_select(None)

    def _on_cancel(self, _e):
        self._root.destroy()
        self.on_select(None)
