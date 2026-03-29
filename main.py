"""
main.py — Claude Code Usage Tray
Entry point: starts the system-tray icon and background refresh loop.

Usage:
    python main.py

Requires:
    pip install pystray pillow
"""

import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pystray
from PIL import Image, ImageDraw, ImageFont

import config
import reader
from ui import StatsWindow, SettingsWindow


# ── Icon generation ──────────────────────────────────────────────────────────

_BRAND_BG = "#CC785C"      # Anthropic terra-cotta
_BRAND_FG = "#FFFFFF"


def _make_icon(label: str = "CC", size: int = 64) -> Image.Image:
    """Generate a square tray icon with a two-letter label."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-rect background
    r = size // 5
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)],
                            radius=r, fill=_BRAND_BG)

    # Text
    font_size = size // 3
    try:
        font = ImageFont.truetype("segoeui.ttf", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=_BRAND_FG)

    return img


def _build_tooltip(data: dict) -> str:
    today = data.get("today", {})
    msgs = today.get("total_messages", 0)
    tokens = today.get("total_tokens", 0)
    fetched = data.get("fetched_at", "")[:16]
    return (
        f"Claude Code Usage\n"
        f"Today: {msgs} messages · {reader.fmt_tokens(tokens)} tokens\n"
        f"Updated: {fetched}"
    )


# ── App state ────────────────────────────────────────────────────────────────

class TrayApp:
    def __init__(self) -> None:
        self.settings = config.load()
        self.data: dict = {}
        self._tray: pystray.Icon | None = None
        self._stats_win: StatsWindow | None = None
        self._lock = threading.Lock()

        # Initial data fetch in background so startup is instant
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    # ── Data fetch ───────────────────────────────────────────────────────────

    def _fetch_and_update(self) -> None:
        claude_dir = config.get_claude_dir(self.settings)
        try:
            data = reader.fetch_usage(claude_dir)
        except Exception as exc:
            print(f"[reader] error: {exc}", file=sys.stderr)
            data = {"error": str(exc), "today": {}, "alltime": {}, "daily": []}

        with self._lock:
            self.data = data

        self._update_tray_icon()

        if self._stats_win is not None:
            self._stats_win.update_data(data)

    def _refresh_loop(self) -> None:
        while True:
            interval = self.settings.get("refresh_interval_minutes", 3) * 60
            time.sleep(interval)
            self._fetch_and_update()

    # ── Tray icon ────────────────────────────────────────────────────────────

    def _update_tray_icon(self) -> None:
        if self._tray is None:
            return
        tooltip = _build_tooltip(self.data)
        self._tray.title = tooltip
        # Rebuild icon to show today's message count
        today_msgs = self.data.get("today", {}).get("total_messages", 0)
        label = str(today_msgs) if today_msgs < 100 else "99+"
        self._tray.icon = _make_icon(label if today_msgs > 0 else "CC")

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Claude Code Usage", self._on_open_stats, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh now", self._on_refresh),
            pystray.MenuItem("Settings", self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit),
        )

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_open_stats(self, icon=None, item=None) -> None:
        threading.Thread(target=self._show_stats, daemon=True).start()

    def _show_stats(self) -> None:
        with self._lock:
            data = self.data
        self._stats_win = StatsWindow(
            settings=self.settings,
            data=data,
            on_settings=self._on_settings,
            on_refresh=lambda: threading.Thread(
                target=self._fetch_and_update, daemon=True).start(),
        )
        self._stats_win.show()

    def _on_refresh(self, icon=None, item=None) -> None:
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _on_settings(self, icon=None, item=None) -> None:
        threading.Thread(target=self._show_settings, daemon=True).start()

    def _show_settings(self) -> None:
        def on_save(new_settings: dict) -> None:
            self.settings = new_settings
            # Restart refresh loop implicitly (loop reads self.settings each iteration)
            threading.Thread(target=self._fetch_and_update, daemon=True).start()
            if self.settings.get("show_notifications"):
                self._tray.notify(
                    "Settings saved",
                    f"Refresh every {new_settings['refresh_interval_minutes']} min",
                )

        SettingsWindow(
            settings=self.settings,
            on_save=on_save,
            on_cancel=lambda: None,
        ).show()

    def _on_exit(self, icon=None, item=None) -> None:
        if self._tray:
            self._tray.stop()

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> None:
        icon_img = _make_icon("CC")
        self._tray = pystray.Icon(
            name="claude-tray",
            icon=icon_img,
            title="Claude Code Usage",
            menu=self._build_menu(),
        )

        # Start background refresh loop
        threading.Thread(target=self._refresh_loop, daemon=True).start()

        self._tray.run()


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
