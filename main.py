import ctypes
import os
import sys


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _app_dir():
    """Return the directory that contains our files (works frozen + dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_icon():
    ico = os.path.join(_app_dir(), "icon.ico")
    if not os.path.exists(ico) and not getattr(sys, "frozen", False):
        try:
            from create_icon import generate
            generate(ico)
        except Exception:
            pass


if __name__ == "__main__":
    _set_dpi_awareness()
    _ensure_icon()

    # Make sure our own directory is on the path (dev mode)
    src = os.path.dirname(os.path.abspath(__file__))
    if src not in sys.path:
        sys.path.insert(0, src)

    try:
        from gui import App
    except ImportError as e:
        import tkinter.messagebox as mb
        import tkinter as tk
        tk.Tk().withdraw()
        mb.showerror(
            "Missing dependency",
            f"A required package is not installed:\n\n{e}\n\n"
            "Run  install.bat  to install all dependencies.",
        )
        sys.exit(1)

    app = App()
    app.mainloop()
