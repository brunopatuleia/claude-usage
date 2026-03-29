# Claude Code Usage Tray

A lightweight Windows system-tray app that shows your **Claude Code** usage statistics — updated automatically on a configurable interval.

![screenshot placeholder](assets/screenshot.png)

## Features

- **System tray icon** showing today's message count at a glance
- **Stats popup** with:
  - Today: messages, sessions, total tokens
  - Per-model breakdown (Opus / Sonnet / Haiku)
  - All-time totals
  - Recent daily activity mini-chart
- **Auto-refresh** every N minutes (configurable, default 3)
- **Settings window**: refresh interval, custom Claude directory, theme (dark/light)
- Reads data directly from `~/.claude/` — no API calls needed
- Dark and light theme

## Requirements

- Windows 10/11
- Python 3.11+
- Claude Code installed (data must exist at `%USERPROFILE%\.claude\`)

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/claude-usage-tray.git
cd claude-usage-tray

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

## Build a standalone .exe

```bash
pip install pyinstaller
python build.py
# Output: dist/ClaudeUsageTray.exe
```

To have it start with Windows, add a shortcut to `ClaudeUsageTray.exe` in:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

## Data sources

The app reads two local files written by Claude Code — no network requests are made:

| File | Used for |
|---|---|
| `~/.claude/stats-cache.json` | All-time totals & daily activity |
| `~/.claude/projects/**/*.jsonl` | Today's live token usage |

Settings are stored in `~/.claude-tray/settings.json`.

## Project structure

```
claude-usage-tray/
├── main.py        # Entry point, tray icon, refresh loop
├── reader.py      # Reads & aggregates Claude Code data files
├── ui.py          # Tkinter windows (stats + settings)
├── config.py      # Settings load/save
├── build.py       # PyInstaller build helper
└── requirements.txt
```

## Contributing

PRs welcome! Ideas for future improvements:
- [ ] macOS/Linux support
- [ ] Cost estimation (token pricing per model)
- [ ] Export usage to CSV
- [ ] Notifications when daily limits approach
- [ ] Mini sparkline in tray icon

## License

MIT
