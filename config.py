"""
config.py — persistent app settings stored in ~/.claude-tray/settings.json
"""

import json
import os
from pathlib import Path
from typing import Any

DEFAULTS = {
    "refresh_interval_minutes": 3,
    "claude_dir": "",          # empty = auto-detect (~/.claude)
    "start_minimized": True,
    "show_notifications": True,
    "theme": "dark",           # "dark" | "light"
}

CONFIG_DIR = Path.home() / ".claude-tray"
CONFIG_FILE = CONFIG_DIR / "settings.json"


def load() -> dict:
    settings = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                stored = json.load(f)
            settings.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_claude_dir(settings: dict) -> Path:
    d = settings.get("claude_dir", "")
    if d:
        return Path(d)
    return Path.home() / ".claude"
