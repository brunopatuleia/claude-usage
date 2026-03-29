"""
reader.py — reads Claude Code usage data from ~/.claude
"""

import json
import os
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict
from typing import Dict, Optional


def get_claude_dir() -> Path:
    return Path.home() / ".claude"


def read_stats_cache(claude_dir: Path) -> dict:
    stats_file = claude_dir / "stats-cache.json"
    if stats_file.exists():
        try:
            with open(stats_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _aggregate_jsonl_files(claude_dir: Path, target_date: Optional[str] = None) -> dict:
    """
    Scan all project JSONL session files and aggregate token usage.
    If target_date is given (YYYY-MM-DD), only count messages from that date.
    Deduplicates by message ID (keeps last seen entry per ID).
    """
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return {}

    # msg_id -> latest entry (streaming sends the same ID multiple times; last has full tokens)
    message_entries: Dict[str, dict] = {}

    for jsonl_file in projects_dir.glob("**/*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get("type") != "assistant":
                        continue

                    msg = entry.get("message", {})
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue

                    if target_date:
                        ts = entry.get("timestamp", "")
                        if not ts.startswith(target_date):
                            continue

                    # Always overwrite — last occurrence has the most complete usage
                    message_entries[msg_id] = entry

        except (IOError, OSError):
            continue

    # Aggregate the final state of each message
    model_usage: Dict[str, dict] = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "message_count": 0,
    })

    for entry in message_entries.values():
        msg = entry.get("message", {})
        model = msg.get("model", "unknown")
        usage = msg.get("usage", {})

        model_usage[model]["input_tokens"] += usage.get("input_tokens", 0)
        model_usage[model]["output_tokens"] += usage.get("output_tokens", 0)
        model_usage[model]["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)
        model_usage[model]["cache_creation_input_tokens"] += usage.get("cache_creation_input_tokens", 0)
        model_usage[model]["message_count"] += 1

    return dict(model_usage)


def _count_today_sessions(claude_dir: Path, target_date: str) -> int:
    """Count distinct session IDs active today."""
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return 0

    sessions = set()
    for jsonl_file in projects_dir.glob("**/*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp", "")
                    if ts.startswith(target_date):
                        sid = entry.get("sessionId")
                        if sid:
                            sessions.add(sid)
                        break  # one match per file is enough to count the session
        except (IOError, OSError):
            continue

    return len(sessions)


def fetch_usage(claude_dir: Optional[Path] = None) -> dict:
    """
    Returns a unified dict with:
      - today:    { model_usage, total_tokens, total_messages }
      - alltime:  { model_usage, total_sessions, total_messages, first_date }
      - daily:    [ { date, messageCount, tokenCount } ]  (last 14 days)
    """
    if claude_dir is None:
        claude_dir = get_claude_dir()

    today_str = date.today().isoformat()
    stats = read_stats_cache(claude_dir)

    # Today — always read live from JSONL
    today_usage = _aggregate_jsonl_files(claude_dir, target_date=today_str)
    today_msgs = sum(v["message_count"] for v in today_usage.values())
    today_tokens = sum(
        v["input_tokens"] + v["output_tokens"]
        for v in today_usage.values()
    )
    today_sessions = _count_today_sessions(claude_dir, today_str)

    # All-time — prefer stats-cache for speed; fall back to full JSONL scan
    if stats.get("modelUsage"):
        alltime_usage = stats["modelUsage"]
        total_sessions = stats.get("totalSessions", 0)
        total_messages = stats.get("totalMessages", 0)
        first_date = stats.get("firstSessionDate", "")
    else:
        alltime_usage = _aggregate_jsonl_files(claude_dir)
        total_sessions = 0
        total_messages = sum(v["message_count"] for v in alltime_usage.values())
        first_date = ""

    # Daily activity (last 14 entries from stats-cache)
    daily = []
    for entry in stats.get("dailyActivity", [])[-14:]:
        day = entry.get("date", "")
        # find tokens for this day from dailyModelTokens
        tokens = 0
        for dt in stats.get("dailyModelTokens", []):
            if dt.get("date") == day:
                tokens = sum(dt.get("tokensByModel", {}).values())
                break
        daily.append({
            "date": day,
            "messageCount": entry.get("messageCount", 0),
            "toolCallCount": entry.get("toolCallCount", 0),
            "tokenCount": tokens,
        })

    return {
        "today": {
            "model_usage": today_usage,
            "total_tokens": today_tokens,
            "total_messages": today_msgs,
            "total_sessions": today_sessions,
        },
        "alltime": {
            "model_usage": alltime_usage,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "first_date": first_date,
        },
        "daily": daily,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def shorten_model(model: str) -> str:
    """claude-sonnet-4-6 -> Sonnet 4.6"""
    model = model.lower()
    name = model
    if "opus" in model:
        name = "Opus"
    elif "sonnet" in model:
        name = "Sonnet"
    elif "haiku" in model:
        name = "Haiku"

    # extract version number like 4-6 or 4-5
    import re
    m = re.search(r"(\d+)-(\d+)", model)
    if m:
        name += f" {m.group(1)}.{m.group(2)}"
    return name


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
