import os
import sys
import json


def _config_dir():
    if getattr(sys, "frozen", False):
        # Installed app — write to AppData, not Program Files
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                         "ScreenRecorder")
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(_config_dir(), "config.json")

DEFAULTS = {
    "output_dir": os.path.join(os.path.expanduser("~"), "Videos", "ScreenRecorder"),
    "fps": 30,
    "record_audio": True,
    "format": "mp4",
}


def load():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULTS.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULTS.copy()


def save(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass
