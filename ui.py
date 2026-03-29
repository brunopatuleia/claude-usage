"""
ui.py — Stats window and Settings window (customtkinter)
"""

import tkinter as tk
import customtkinter as ctk
import webbrowser
from typing import Callable

import config
from reader import shorten_model, fmt_tokens

ANTHROPIC_CONSOLE_URL = "https://console.anthropic.com/"

# ── Theme setup ──────────────────────────────────────────────────────────────

BRAND = "#CC785C"        # Anthropic terra-cotta
BRAND_HOVER = "#B8664A"

def _apply_appearance(settings: dict) -> None:
    theme = settings.get("theme", "dark")
    ctk.set_appearance_mode(theme)
    ctk.set_default_color_theme("blue")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_label(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=BRAND)


def _value_label(parent, text: str, size: int = 22) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=size, weight="bold"))


def _sub_label(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11),
                        text_color="gray")


def _card(parent) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, corner_radius=10)


def _divider(parent) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, height=1, fg_color="gray30", corner_radius=0)


# ── Stats Window ─────────────────────────────────────────────────────────────

class StatsWindow:
    def __init__(self, settings: dict, local_data: dict, plan_data: dict,
                 on_settings: Callable, on_refresh: Callable) -> None:
        self.settings = settings
        self.data = local_data
        self.plan = plan_data
        self.on_settings = on_settings
        self.on_refresh = on_refresh
        self._win: ctk.CTk | None = None

    def show(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.lift()
            self._win.focus_force()
            return
        self._build()

    def update_data(self, local_data: dict, plan_data: dict) -> None:
        self.data = local_data
        self.plan = plan_data
        if self._win and self._win.winfo_exists():
            self._win.destroy()
            self._build()

    def _build(self) -> None:
        _apply_appearance(self.settings)

        win = ctk.CTk()
        win.title("Claude Code Usage")
        win.geometry("440x580")
        win.resizable(False, False)
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"440x580+{(sw-440)//2}+{(sh-580)//2}")
        self._win = win

        scroll = ctk.CTkScrollableFrame(win, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        # ── Header
        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 4))

        ctk.CTkLabel(hdr, text="Claude Code Usage",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="↻", width=36, height=32,
                      fg_color=BRAND, hover_color=BRAND_HOVER,
                      command=self._do_refresh).pack(side="right", padx=(4, 0))
        ctk.CTkButton(btn_frame, text="⚙", width=36, height=32,
                      fg_color="gray30", hover_color="gray40",
                      command=self._open_settings).pack(side="right")

        fetched = self.data.get("fetched_at", "")
        if fetched:
            _sub_label(scroll, f"Last updated: {fetched[11:16]}").pack(
                anchor="w", padx=16, pady=(0, 10))

        # ── Plan usage card (shown when logged in)
        plan = self.plan
        if plan.get("logged_in") and not plan.get("error"):
            pc = _card(scroll)
            pc.pack(fill="x", padx=16, pady=(0, 12))
            _section_label(pc, "PLAN USAGE").pack(anchor="w", padx=14, pady=(12, 8))

            for label, pct, reset_lbl in [
                ("Current session", plan.get("session_pct", 0), plan.get("session_resets_in", "")),
                ("Weekly (all models)", plan.get("weekly_pct", 0), plan.get("weekly_resets_at", "")),
            ]:
                row = ctk.CTkFrame(pc, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=(0, 8))
                top = ctk.CTkFrame(row, fg_color="transparent")
                top.pack(fill="x")
                ctk.CTkLabel(top, text=label,
                             font=ctk.CTkFont(size=12)).pack(side="left")
                pct_color = ("#f38b8b" if pct >= 80 else
                             "#f9e24f" if pct >= 55 else "#a6e3a1")
                ctk.CTkLabel(top, text=f"{pct:.0f}% used",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=pct_color).pack(side="right")
                bar_color = ("#f38b8b" if pct >= 80 else
                             "#f9e24f" if pct >= 55 else "#a6e3a1")
                ctk.CTkProgressBar(row, progress_color=bar_color,
                                   height=8, corner_radius=4).pack(
                    fill="x", pady=(4, 0)
                ).set(min(pct / 100, 1.0))
                if reset_lbl:
                    _sub_label(row, f"Resets: {reset_lbl}").pack(anchor="w", pady=(2, 0))

            # Extra usage / balance
            extra = plan.get("extra_spent_usd", 0)
            limit = plan.get("extra_limit_usd", 0)
            bal   = plan.get("balance_usd", 0)
            if bal or limit:
                _divider(pc).pack(fill="x", padx=14, pady=6)
                b_row = ctk.CTkFrame(pc, fg_color="transparent")
                b_row.pack(fill="x", padx=14, pady=(0, 12))
                if bal:
                    col = ctk.CTkFrame(b_row, fg_color="transparent")
                    col.pack(side="left", padx=(0, 24))
                    _value_label(col, f"${bal:.2f}", size=18).pack(anchor="w")
                    _sub_label(col, "Balance").pack(anchor="w")
                if limit:
                    col2 = ctk.CTkFrame(b_row, fg_color="transparent")
                    col2.pack(side="left")
                    _value_label(col2, f"${extra:.2f} / ${limit:.0f}", size=18).pack(anchor="w")
                    _sub_label(col2, "Extra usage").pack(anchor="w")

        # ── Login banner (shown when not authenticated)
        if not plan.get("logged_in"):
            banner = ctk.CTkFrame(scroll, corner_radius=10, fg_color=("#fff3e0", "#3a2a1a"))
            banner.pack(fill="x", padx=16, pady=(0, 12))
            inner = ctk.CTkFrame(banner, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(inner, text="See live session & weekly usage",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=BRAND).pack(anchor="w")
            err = plan.get("error", "")
            msg = err if err else "Paste your claude.ai sessionKey cookie in Settings to see plan usage %."
            ctk.CTkLabel(inner, text=msg,
                         font=ctk.CTkFont(size=11), text_color="gray",
                         wraplength=340, justify="left").pack(anchor="w", pady=(2, 8))
            btn_row = ctk.CTkFrame(inner, fg_color="transparent")
            btn_row.pack(anchor="w")
            ctk.CTkButton(btn_row, text="Open claude.ai", width=140, height=30,
                          fg_color=BRAND, hover_color=BRAND_HOVER,
                          font=ctk.CTkFont(size=12),
                          command=lambda: webbrowser.open("https://claude.ai")).pack(side="left")
            ctk.CTkButton(btn_row, text="Add Session Key", width=130, height=30,
                          fg_color="gray30", hover_color="gray40",
                          font=ctk.CTkFont(size=12),
                          command=self._open_settings).pack(side="left", padx=(8, 0))

        # ── Today card
        today = self.data.get("today", {})
        tc = _card(scroll)
        tc.pack(fill="x", padx=16, pady=(0, 12))

        _section_label(tc, "TODAY").pack(anchor="w", padx=14, pady=(12, 8))

        stats_row = ctk.CTkFrame(tc, fg_color="transparent")
        stats_row.pack(fill="x", padx=14, pady=(0, 4))

        for val, lbl in [
            (str(today.get("total_messages", 0)), "Messages"),
            (str(today.get("total_sessions", 0)), "Sessions"),
            (fmt_tokens(today.get("total_tokens", 0)), "Tokens"),
        ]:
            col = ctk.CTkFrame(stats_row, fg_color="transparent")
            col.pack(side="left", padx=(0, 24))
            _value_label(col, val).pack(anchor="w")
            _sub_label(col, lbl).pack(anchor="w")

        # Per-model today
        today_models = today.get("model_usage", {})
        if today_models:
            _divider(tc).pack(fill="x", padx=14, pady=8)
            _sub_label(tc, "Per model").pack(anchor="w", padx=14, pady=(0, 6))
            for model, mu in today_models.items():
                row = ctk.CTkFrame(tc, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=(0, 4))
                tok = mu.get("input_tokens", 0) + mu.get("output_tokens", 0)
                cache = mu.get("cache_read_input_tokens", 0)
                ctk.CTkLabel(row, text=shorten_model(model),
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=BRAND).pack(side="left")
                _sub_label(row, f"  {mu.get('message_count',0)} msgs · "
                               f"{fmt_tokens(tok)} tokens · "
                               f"{fmt_tokens(cache)} cached").pack(side="left")
            ctk.CTkFrame(tc, height=10, fg_color="transparent").pack()

        # ── All-time card
        alltime = self.data.get("alltime", {})
        ac = _card(scroll)
        ac.pack(fill="x", padx=16, pady=(0, 12))

        _section_label(ac, "ALL TIME").pack(anchor="w", padx=14, pady=(12, 8))

        at_row = ctk.CTkFrame(ac, fg_color="transparent")
        at_row.pack(fill="x", padx=14, pady=(0, 4))
        for val, lbl in [
            (str(alltime.get("total_sessions", 0)), "Sessions"),
            (fmt_tokens(alltime.get("total_messages", 0)), "Messages"),
        ]:
            col = ctk.CTkFrame(at_row, fg_color="transparent")
            col.pack(side="left", padx=(0, 24))
            _value_label(col, val).pack(anchor="w")
            _sub_label(col, lbl).pack(anchor="w")

        at_models = alltime.get("model_usage", {})
        if at_models:
            _divider(ac).pack(fill="x", padx=14, pady=8)
            _sub_label(ac, "Per model").pack(anchor="w", padx=14, pady=(0, 6))
            for model, mu in at_models.items():
                if not isinstance(mu, dict):
                    continue
                in_t = mu.get("inputTokens") or mu.get("input_tokens", 0)
                out_t = mu.get("outputTokens") or mu.get("output_tokens", 0)
                cache_r = mu.get("cacheReadInputTokens") or mu.get("cache_read_input_tokens", 0)
                row = ctk.CTkFrame(ac, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=(0, 4))
                ctk.CTkLabel(row, text=shorten_model(model),
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=BRAND).pack(side="left")
                _sub_label(row, f"  ↑{fmt_tokens(in_t)} ↓{fmt_tokens(out_t)} "
                               f"⚡{fmt_tokens(cache_r)} cached").pack(side="left")
            ctk.CTkFrame(ac, height=10, fg_color="transparent").pack()

        # ── Daily activity chart
        daily = self.data.get("daily", [])
        if daily:
            dc = _card(scroll)
            dc.pack(fill="x", padx=16, pady=(0, 16))
            _section_label(dc, "RECENT ACTIVITY").pack(anchor="w", padx=14, pady=(12, 8))
            self._draw_chart(dc, daily)
            ctk.CTkFrame(dc, height=10, fg_color="transparent").pack()

        win.mainloop()

    def _draw_chart(self, parent, daily: list) -> None:
        mode = ctk.get_appearance_mode()
        bar_color = BRAND
        label_color = "#888888"
        bg = "#2b2b2b" if mode == "Dark" else "#ebebeb"

        canvas = tk.Canvas(parent, height=70, bg=bg, highlightthickness=0)
        canvas.pack(fill="x", padx=14, pady=(0, 4))

        canvas.update_idletasks()
        w = canvas.winfo_width() or 380
        n = len(daily)
        max_msgs = max((d["messageCount"] for d in daily), default=1) or 1
        bar_w = max(4, (w - n * 3) // n)

        for i, day in enumerate(daily):
            x0 = i * (bar_w + 3)
            x1 = x0 + bar_w
            frac = day["messageCount"] / max_msgs
            bar_h = max(3, int(frac * 48))
            canvas.create_rectangle(x0, 52 - bar_h, x1, 52,
                                    fill=bar_color, outline="")
            if i == n - 1 or i == 0:
                canvas.create_text(x0, 64, text=day["date"][5:],
                                   fill=label_color, font=("Segoe UI", 7), anchor="w")

    def _open_settings(self) -> None:
        if self._win:
            self._win.destroy()
            self._win = None
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
        _apply_appearance(self.settings)

        win = ctk.CTk()
        win.title("Settings — Claude Tray")
        win.geometry("460x560")
        win.resizable(False, False)
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"460x560+{(sw-460)//2}+{(sh-560)//2}")

        outer = ctk.CTkScrollableFrame(win, corner_radius=0)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        ctk.CTkLabel(outer, text="Settings",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(
                         anchor="w", padx=20, pady=(20, 16))

        # ── General card
        gen = _card(outer)
        gen.pack(fill="x", padx=16, pady=(0, 12))
        _section_label(gen, "GENERAL").pack(anchor="w", padx=14, pady=(12, 10))

        # Refresh interval
        ri_row = ctk.CTkFrame(gen, fg_color="transparent")
        ri_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(ri_row, text="Refresh interval (minutes)").pack(side="left")
        self._interval_var = tk.IntVar(value=self.settings.get("refresh_interval_minutes", 3))
        ctk.CTkEntry(ri_row, textvariable=self._interval_var,
                     width=60, justify="center").pack(side="right")

        # Theme
        theme_row = ctk.CTkFrame(gen, fg_color="transparent")
        theme_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(theme_row, text="Theme").pack(side="left")
        self._theme_var = tk.StringVar(value=self.settings.get("theme", "dark").capitalize())
        ctk.CTkOptionMenu(theme_row, variable=self._theme_var,
                          values=["Dark", "Light", "System"],
                          fg_color=BRAND, button_color=BRAND_HOVER,
                          width=100).pack(side="right")

        # Start minimized
        self._minimized_var = tk.BooleanVar(value=self.settings.get("start_minimized", True))
        ctk.CTkCheckBox(gen, text="Start minimized to tray",
                        variable=self._minimized_var,
                        fg_color=BRAND, hover_color=BRAND_HOVER).pack(
                            anchor="w", padx=14, pady=(0, 10))

        # Notifications
        self._notif_var = tk.BooleanVar(value=self.settings.get("show_notifications", True))
        ctk.CTkCheckBox(gen, text="Show refresh notifications",
                        variable=self._notif_var,
                        fg_color=BRAND, hover_color=BRAND_HOVER).pack(
                            anchor="w", padx=14, pady=(0, 12))

        # ── Data source card
        ds = _card(outer)
        ds.pack(fill="x", padx=16, pady=(0, 12))
        _section_label(ds, "DATA SOURCE").pack(anchor="w", padx=14, pady=(12, 10))

        ctk.CTkLabel(ds, text="Claude data directory",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=14)
        dir_row = ctk.CTkFrame(ds, fg_color="transparent")
        dir_row.pack(fill="x", padx=14, pady=(4, 2))
        self._dir_var = tk.StringVar(value=self.settings.get("claude_dir", ""))
        ctk.CTkEntry(dir_row, textvariable=self._dir_var,
                     placeholder_text="Auto-detect (~/.claude)").pack(
                         side="left", fill="x", expand=True)
        ctk.CTkButton(dir_row, text="Browse", width=80,
                      fg_color=BRAND, hover_color=BRAND_HOVER,
                      command=self._browse).pack(side="right", padx=(8, 0))
        _sub_label(ds, "Leave blank to use the default ~/.claude directory").pack(
            anchor="w", padx=14, pady=(0, 12))

        # ── Session key card
        cred = _card(outer)
        cred.pack(fill="x", padx=16, pady=(0, 12))
        _section_label(cred, "CLAUDE.AI SESSION").pack(anchor="w", padx=14, pady=(12, 10))

        ctk.CTkLabel(cred, text="Session Key",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=14)
        self._sessionkey_var = tk.StringVar(value=self.settings.get("session_key", ""))
        self._sk_entry = ctk.CTkEntry(cred, textvariable=self._sessionkey_var,
                                      placeholder_text="Paste your sessionKey cookie here",
                                      show="•")
        self._sk_entry.pack(fill="x", padx=14, pady=(4, 2))

        btn_row_sk = ctk.CTkFrame(cred, fg_color="transparent")
        btn_row_sk.pack(fill="x", padx=14, pady=(4, 4))
        ctk.CTkButton(btn_row_sk, text="Show / Hide", width=100, height=26,
                      fg_color="gray30", hover_color="gray40",
                      font=ctk.CTkFont(size=11),
                      command=self._toggle_sk_vis).pack(side="left")
        ctk.CTkButton(btn_row_sk, text="Open claude.ai", width=120, height=26,
                      fg_color=BRAND, hover_color=BRAND_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: webbrowser.open("https://claude.ai")).pack(side="left", padx=(8, 0))

        instructions = (
            "How to get your Session Key:\n"
            "1. Open claude.ai in your browser and log in\n"
            "2. Press F12 → Application → Cookies → claude.ai\n"
            "3. Copy the value of the  sessionKey  cookie\n"
            "4. Paste it above and click Save"
        )
        ctk.CTkLabel(cred, text=instructions, font=ctk.CTkFont(size=11),
                     text_color="gray", justify="left",
                     wraplength=400).pack(anchor="w", padx=14, pady=(6, 12))

        # ── Buttons
        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 20))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="gray30", hover_color="gray40",
                      command=lambda: self._cancel(win)).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Save", width=100,
                      fg_color=BRAND, hover_color=BRAND_HOVER,
                      command=lambda: self._save(win)).pack(side="right")

        win.mainloop()

    def _toggle_sk_vis(self) -> None:
        self._show_sk = not getattr(self, "_show_sk", False)
        self._sk_entry.configure(show="" if self._show_sk else "•")

    def _browse(self) -> None:
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Select Claude data directory")
        if d:
            self._dir_var.set(d)

    def _save(self, win: ctk.CTk) -> None:
        updated = dict(self.settings)
        try:
            interval = max(1, min(60, int(self._interval_var.get())))
        except (ValueError, tk.TclError):
            interval = 3
        updated["refresh_interval_minutes"] = interval
        updated["claude_dir"] = self._dir_var.get().strip()
        updated["theme"] = self._theme_var.get().lower()
        updated["start_minimized"] = self._minimized_var.get()
        updated["show_notifications"] = self._notif_var.get()
        updated["session_key"] = self._sessionkey_var.get().strip()
        config.save(updated)
        win.destroy()
        self.on_save(updated)

    def _cancel(self, win: ctk.CTk) -> None:
        win.destroy()
        self.on_cancel()
