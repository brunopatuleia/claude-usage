"""
ui.py — Stats window and Settings window (tkinter)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable

import config
from reader import shorten_model, fmt_tokens

# ── colour palette ──────────────────────────────────────────────────────────
DARK = {
    "bg": "#1e1e2e",
    "bg2": "#2a2a3e",
    "bg3": "#313145",
    "fg": "#cdd6f4",
    "fg2": "#a6adc8",
    "accent": "#cba6f7",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "red": "#f38ba8",
    "blue": "#89b4fa",
    "border": "#45475a",
}

LIGHT = {
    "bg": "#f5f5f5",
    "bg2": "#ebebeb",
    "bg3": "#dcdcdc",
    "fg": "#1e1e2e",
    "fg2": "#555576",
    "accent": "#7c3aed",
    "green": "#16a34a",
    "yellow": "#d97706",
    "red": "#dc2626",
    "blue": "#2563eb",
    "border": "#c4c4d4",
}


def _palette(settings: dict) -> dict:
    return DARK if settings.get("theme", "dark") == "dark" else LIGHT


def _apply_theme(root: tk.Tk, c: dict) -> None:
    root.configure(bg=c["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=c["bg"], foreground=c["fg"],
                    fieldbackground=c["bg2"], bordercolor=c["border"],
                    troughcolor=c["bg2"], font=("Segoe UI", 10))
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("Accent.TLabel", background=c["bg"], foreground=c["accent"],
                    font=("Segoe UI", 10, "bold"))
    style.configure("Header.TLabel", background=c["bg"], foreground=c["fg"],
                    font=("Segoe UI", 12, "bold"))
    style.configure("Sub.TLabel", background=c["bg"], foreground=c["fg2"],
                    font=("Segoe UI", 9))
    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["bg2"])
    style.configure("TButton", background=c["bg3"], foreground=c["fg"],
                    bordercolor=c["border"], focuscolor=c["accent"],
                    font=("Segoe UI", 10))
    style.map("TButton", background=[("active", c["bg3"]), ("pressed", c["border"])])
    style.configure("TEntry", fieldbackground=c["bg2"], foreground=c["fg"],
                    insertcolor=c["fg"], bordercolor=c["border"])
    style.configure("TSpinbox", fieldbackground=c["bg2"], foreground=c["fg"],
                    arrowcolor=c["fg2"], bordercolor=c["border"])
    style.configure("TCombobox", fieldbackground=c["bg2"], foreground=c["fg"],
                    arrowcolor=c["fg2"], bordercolor=c["border"])
    style.configure("Separator.TSeparator", background=c["border"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _card(parent, c: dict) -> ttk.Frame:
    f = ttk.Frame(parent, style="Card.TFrame", padding=12)
    return f


def _lbl(parent, text, style="TLabel", **kw) -> ttk.Label:
    return ttk.Label(parent, text=text, style=style, **kw)


def _sep(parent, c: dict) -> None:
    tk.Frame(parent, height=1, bg=c["border"]).pack(fill="x", pady=6)


# ── Stats Window ─────────────────────────────────────────────────────────────

class StatsWindow:
    def __init__(self, settings: dict, data: dict, on_settings: Callable,
                 on_refresh: Callable) -> None:
        self.settings = settings
        self.data = data
        self.on_settings = on_settings
        self.on_refresh = on_refresh
        self.root: tk.Tk | None = None

    def show(self) -> None:
        if self.root and self.root.winfo_exists():
            self.root.lift()
            self.root.focus_force()
            return
        self._build()

    def update_data(self, data: dict) -> None:
        self.data = data
        if self.root and self.root.winfo_exists():
            self.root.destroy()
            self._build()

    def _build(self) -> None:
        c = _palette(self.settings)
        root = tk.Tk()
        root.title("Claude Code Usage")
        root.configure(bg=c["bg"])
        root.resizable(False, False)
        root.geometry("420x560")

        # Centre on screen
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 420) // 2
        y = (sh - 560) // 2
        root.geometry(f"420x560+{x}+{y}")

        _apply_theme(root, c)
        self.root = root

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)

        # ── Header
        hdr = ttk.Frame(outer)
        hdr.pack(fill="x", pady=(0, 10))
        _lbl(hdr, "Claude Code Usage", style="Header.TLabel").pack(side="left")
        fetched = self.data.get("fetched_at", "")
        if fetched:
            _lbl(hdr, f"  {fetched[11:16]}", style="Sub.TLabel").pack(side="left", pady=(4, 0))

        # Buttons top-right
        btn_frame = ttk.Frame(hdr)
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="⚙", width=3,
                   command=self._open_settings).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frame, text="↻", width=3,
                   command=self._do_refresh).pack(side="right")

        _sep(outer, c)

        # ── Today card
        today = self.data.get("today", {})
        tc = _card(outer, c)
        tc.pack(fill="x", pady=(0, 10))

        _lbl(tc, "TODAY", style="Accent.TLabel").grid(row=0, column=0, columnspan=4,
                                                       sticky="w", pady=(0, 8))
        cols = [
            ("Messages", str(today.get("total_messages", 0))),
            ("Sessions", str(today.get("total_sessions", 0))),
            ("Tokens", fmt_tokens(today.get("total_tokens", 0))),
        ]
        for i, (lbl, val) in enumerate(cols):
            _lbl(tc, val, font=("Segoe UI", 18, "bold"),
                 background=c["bg2"], foreground=c["fg"]).grid(
                     row=1, column=i, sticky="w", padx=(0, 20))
            _lbl(tc, lbl, style="Sub.TLabel").grid(row=2, column=i, sticky="w", padx=(0, 20))

        # Per-model today
        today_models = today.get("model_usage", {})
        if today_models:
            _sep(tc, c)
            _lbl(tc, "Per model", style="Sub.TLabel").grid(
                row=4, column=0, columnspan=4, sticky="w", pady=(0, 4))
            for row_i, (model, mu) in enumerate(today_models.items(), start=5):
                tok = mu.get("input_tokens", 0) + mu.get("output_tokens", 0)
                cache = mu.get("cache_read_input_tokens", 0)
                _lbl(tc, shorten_model(model),
                     background=c["bg2"], foreground=c["blue"]).grid(
                         row=row_i, column=0, sticky="w")
                _lbl(tc, f"{mu.get('message_count', 0)} msgs",
                     style="Sub.TLabel").grid(row=row_i, column=1, sticky="w", padx=(8, 0))
                _lbl(tc, fmt_tokens(tok) + " tokens",
                     style="Sub.TLabel").grid(row=row_i, column=2, sticky="w", padx=(8, 0))
                _lbl(tc, fmt_tokens(cache) + " cached",
                     background=c["bg2"], foreground=c["fg2"],
                     font=("Segoe UI", 9)).grid(
                         row=row_i, column=3, sticky="w", padx=(8, 0))

        _sep(outer, c)

        # ── All-time card
        alltime = self.data.get("alltime", {})
        ac = _card(outer, c)
        ac.pack(fill="x", pady=(0, 10))

        _lbl(ac, "ALL TIME", style="Accent.TLabel").grid(row=0, column=0, columnspan=4,
                                                          sticky="w", pady=(0, 8))
        at_cols = [
            ("Sessions", str(alltime.get("total_sessions", 0))),
            ("Messages", fmt_tokens(alltime.get("total_messages", 0))),
        ]
        for i, (lbl, val) in enumerate(at_cols):
            _lbl(ac, val, font=("Segoe UI", 18, "bold"),
                 background=c["bg2"], foreground=c["fg"]).grid(
                     row=1, column=i, sticky="w", padx=(0, 20))
            _lbl(ac, lbl, style="Sub.TLabel").grid(row=2, column=i, sticky="w", padx=(0, 20))

        # Per-model all-time tokens
        at_models = alltime.get("model_usage", {})
        if at_models:
            _sep(ac, c)
            _lbl(ac, "Per model", style="Sub.TLabel").grid(
                row=4, column=0, columnspan=4, sticky="w", pady=(0, 4))
            for row_i, (model, mu) in enumerate(at_models.items(), start=5):
                if isinstance(mu, dict):
                    in_t = mu.get("inputTokens") or mu.get("input_tokens", 0)
                    out_t = mu.get("outputTokens") or mu.get("output_tokens", 0)
                    cache_r = mu.get("cacheReadInputTokens") or mu.get("cache_read_input_tokens", 0)
                else:
                    continue
                _lbl(ac, shorten_model(model),
                     background=c["bg2"], foreground=c["blue"]).grid(
                         row=row_i, column=0, sticky="w")
                _lbl(ac, f"↑{fmt_tokens(in_t)}",
                     style="Sub.TLabel").grid(row=row_i, column=1, sticky="w", padx=(8, 0))
                _lbl(ac, f"↓{fmt_tokens(out_t)}",
                     style="Sub.TLabel").grid(row=row_i, column=2, sticky="w", padx=(8, 0))
                _lbl(ac, f"⚡{fmt_tokens(cache_r)} cached",
                     background=c["bg2"], foreground=c["fg2"],
                     font=("Segoe UI", 9)).grid(
                         row=row_i, column=3, sticky="w", padx=(8, 0))

        _sep(outer, c)

        # ── Recent daily activity (mini bar chart)
        daily = self.data.get("daily", [])
        if daily:
            _lbl(outer, "RECENT ACTIVITY", style="Accent.TLabel").pack(anchor="w", pady=(0, 6))
            self._draw_mini_chart(outer, daily, c)

        root.mainloop()

    def _draw_mini_chart(self, parent, daily: list, c: dict) -> None:
        canvas_h = 60
        canvas_w = 388
        cv = tk.Canvas(parent, width=canvas_w, height=canvas_h,
                       bg=c["bg"], highlightthickness=0)
        cv.pack(fill="x")

        if not daily:
            return

        max_msgs = max((d["messageCount"] for d in daily), default=1) or 1
        n = len(daily)
        bar_w = max(4, (canvas_w - n * 2) // n)
        gap = 2

        for i, day in enumerate(daily):
            x0 = i * (bar_w + gap)
            x1 = x0 + bar_w
            frac = day["messageCount"] / max_msgs
            bar_h = max(2, int(frac * (canvas_h - 14)))
            y0 = canvas_h - 12 - bar_h
            y1 = canvas_h - 12
            cv.create_rectangle(x0, y0, x1, y1, fill=c["accent"], outline="")
            if i == n - 1:
                cv.create_text(x0, canvas_h - 2, text=day["date"][5:],
                               fill=c["fg2"], font=("Segoe UI", 7), anchor="sw")

    def _open_settings(self) -> None:
        if self.root:
            self.root.destroy()
            self.root = None
        self.on_settings()

    def _do_refresh(self) -> None:
        self.on_refresh()


# ── Settings Window ───────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, settings: dict, on_save: Callable, on_cancel: Callable) -> None:
        self.settings = dict(settings)
        self.on_save = on_save
        self.on_cancel = on_cancel

    def show(self) -> None:
        c = _palette(self.settings)
        root = tk.Tk()
        root.title("Settings — Claude Tray")
        root.configure(bg=c["bg"])
        root.resizable(False, False)
        root.geometry("400x340")
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"400x340+{(sw-400)//2}+{(sh-340)//2}")
        _apply_theme(root, c)

        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)

        _lbl(outer, "Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 16))

        # Refresh interval
        ri_frame = ttk.Frame(outer)
        ri_frame.pack(fill="x", pady=6)
        _lbl(ri_frame, "Refresh interval (minutes):").pack(side="left")
        self._interval_var = tk.IntVar(value=self.settings.get("refresh_interval_minutes", 3))
        ttk.Spinbox(ri_frame, from_=1, to=60, width=6,
                    textvariable=self._interval_var).pack(side="right")

        # Claude dir
        dir_frame = ttk.Frame(outer)
        dir_frame.pack(fill="x", pady=6)
        _lbl(dir_frame, "Claude data directory:").pack(anchor="w")
        path_row = ttk.Frame(dir_frame)
        path_row.pack(fill="x", pady=(4, 0))
        self._dir_var = tk.StringVar(value=self.settings.get("claude_dir", ""))
        ttk.Entry(path_row, textvariable=self._dir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse…", width=8,
                   command=self._browse).pack(side="right", padx=(6, 0))
        _lbl(dir_frame, "Leave blank to auto-detect (~/.claude)",
             style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        # Theme
        theme_frame = ttk.Frame(outer)
        theme_frame.pack(fill="x", pady=6)
        _lbl(theme_frame, "Theme:").pack(side="left")
        self._theme_var = tk.StringVar(value=self.settings.get("theme", "dark"))
        ttk.Combobox(theme_frame, textvariable=self._theme_var,
                     values=["dark", "light"], state="readonly", width=8).pack(side="right")

        # Start minimized
        self._minimized_var = tk.BooleanVar(value=self.settings.get("start_minimized", True))
        ttk.Checkbutton(outer, text="Start minimized to tray",
                        variable=self._minimized_var).pack(anchor="w", pady=4)

        # Notifications
        self._notif_var = tk.BooleanVar(value=self.settings.get("show_notifications", True))
        ttk.Checkbutton(outer, text="Show refresh notifications",
                        variable=self._notif_var).pack(anchor="w", pady=4)

        _sep(outer, c)

        # Buttons
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel",
                   command=lambda: self._cancel(root)).pack(side="right", padx=(6, 0))
        ttk.Button(btn_row, text="Save",
                   command=lambda: self._save(root)).pack(side="right")

        root.mainloop()

    def _browse(self) -> None:
        d = filedialog.askdirectory(title="Select Claude data directory")
        if d:
            self._dir_var.set(d)

    def _save(self, root: tk.Tk) -> None:
        updated = dict(self.settings)
        updated["refresh_interval_minutes"] = max(1, min(60, self._interval_var.get()))
        updated["claude_dir"] = self._dir_var.get().strip()
        updated["theme"] = self._theme_var.get()
        updated["start_minimized"] = self._minimized_var.get()
        updated["show_notifications"] = self._notif_var.get()
        config.save(updated)
        root.destroy()
        self.on_save(updated)

    def _cancel(self, root: tk.Tk) -> None:
        root.destroy()
        self.on_cancel()
