"""
main.py — Claude Code Usage Tray
Entry point: starts the system-tray icon and background refresh loop.

Usage:
    python main.py

Requires:
    pip install pystray pillow customtkinter
"""

import sys
import math
import threading
import time

import pystray
from PIL import Image, ImageDraw, ImageFont

import config
import reader
import claude_api
from ui import StatsWindow, SettingsWindow


# ── Icon generation ──────────────────────────────────────────────────────────

_BRAND  = (204, 120,  92)   # Anthropic terra-cotta
_FG     = (255, 255, 255)

# Color thresholds per user spec
_GREEN  = ( 76, 175,  80)   #  0 – 50 %
_YELLOW = (255, 213,  79)   # 51 – 75 %
_ORANGE = (255, 138,  61)   # 76 – 85 %
_RED    = (229,  57,  53)   # 86 – 100%


def _pct_color(pct: float) -> tuple:
    if pct > 85:
        return _RED
    if pct > 75:
        return _ORANGE
    if pct > 50:
        return _YELLOW
    return _GREEN


# Render at high resolution so Windows scales it sharply to tray size
_ICON_SIZE = 256


def _make_icon(pct: float | None = None) -> Image.Image:
    """
    Renders a 256×256 icon — Windows scales it down cleanly to ~20px tray size.
    - No pct: Anthropic brand circle with 'C'
    - With pct: bold percentage number on a colored rounded-rect background
    """
    S = _ICON_SIZE
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = S // 16
    radius = S // 5

    if pct is None:
        # Brand logo
        draw.rounded_rectangle([(pad, pad), (S - pad, S - pad)],
                                radius=radius, fill=_BRAND)
        _draw_centered(draw, "C", S, _FG, int(S * 0.52))
    else:
        bg = _pct_color(pct)
        draw.rounded_rectangle([(pad, pad), (S - pad, S - pad)],
                                radius=radius, fill=bg)

        label = f"{int(pct)}%"
        # Fit font size to label length
        font_size = int(S * 0.44) if len(label) <= 3 else int(S * 0.34)
        _draw_centered(draw, label, S, _FG, font_size)

    return img


def _draw_centered(draw: ImageDraw.ImageDraw, text: str,
                   size: int, color: tuple, font_size: int) -> None:
    font = None
    for name in ("arialbd.ttf", "Arial Bold.ttf", "arial.ttf",
                 "segoeui.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) // 2 - bbox[0],
               (size - th) // 2 - bbox[1]),
              text, font=font, fill=color)


def _build_tooltip(local: dict, plan: dict) -> str:
    lines = ["Claude Code Usage"]

    if plan.get("logged_in") and not plan.get("error"):
        s_pct = plan.get("session_pct", 0)
        w_pct = plan.get("weekly_pct", 0)
        reset  = plan.get("session_resets_in", "")
        lines.append(f"Session: {s_pct:.0f}% used{f'  (resets in {reset})' if reset else ''}")
        lines.append(f"Weekly:  {w_pct:.0f}% used")
    else:
        today = local.get("today", {})
        msgs   = today.get("total_messages", 0)
        tokens = today.get("total_tokens", 0)
        lines.append(f"Today: {msgs} messages · {reader.fmt_tokens(tokens)} tokens")

    updated = local.get("fetched_at", "")
    if updated:
        lines.append(f"Updated: {updated[11:16]}")
    return "\n".join(lines)


# ── App state ────────────────────────────────────────────────────────────────

class TrayApp:
    def __init__(self) -> None:
        self.settings  = config.load()
        self.local_data: dict = {}
        self.plan_data:  dict = {}
        self._tray: pystray.Icon | None = None
        self._stats_win: StatsWindow | None = None
        self._lock = threading.Lock()

        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    # ── Data fetch ───────────────────────────────────────────────────────────

    def _fetch_and_update(self) -> None:
        claude_dir = config.get_claude_dir(self.settings)
        try:
            local = reader.fetch_usage(claude_dir)
        except Exception as exc:
            local = {"error": str(exc), "today": {}, "alltime": {}, "daily": []}

        try:
            plan = claude_api.fetch_plan_usage()
        except Exception as exc:
            plan = {"logged_in": False, "error": str(exc)}

        with self._lock:
            self.local_data = local
            self.plan_data  = plan

        self._update_tray_icon()

        if self._stats_win is not None:
            self._stats_win.update_data(local, plan)

    def _refresh_loop(self) -> None:
        while True:
            interval = self.settings.get("refresh_interval_minutes", 3) * 60
            time.sleep(interval)
            self._fetch_and_update()

    # ── Tray icon ────────────────────────────────────────────────────────────

    def _update_tray_icon(self) -> None:
        if self._tray is None:
            return
        with self._lock:
            plan  = self.plan_data
            local = self.local_data

        if plan.get("logged_in") and not plan.get("error"):
            pct = plan.get("session_pct")
        else:
            pct = None

        self._tray.icon  = _make_icon(pct)
        self._tray.title = _build_tooltip(local, plan)

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Claude Code Usage", self._on_open_stats, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh now",  self._on_refresh),
            pystray.MenuItem("Settings",     self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit",         self._on_exit),
        )

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_open_stats(self, icon=None, item=None) -> None:
        threading.Thread(target=self._show_stats, daemon=True).start()

    def _show_stats(self) -> None:
        with self._lock:
            local = self.local_data
            plan  = self.plan_data

        self._stats_win = StatsWindow(
            settings=self.settings,
            local_data=local,
            plan_data=plan,
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
        self._tray = pystray.Icon(
            name="claude-tray",
            icon=_make_icon(None),
            title="Claude Code Usage",
            menu=self._build_menu(),
        )
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        self._tray.run()


def main() -> None:
    TrayApp().run()


if __name__ == "__main__":
    main()
