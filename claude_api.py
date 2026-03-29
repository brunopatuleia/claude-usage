"""
claude_api.py — fetches live plan usage from Claude.ai using the stored OAuth token.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"
API_BASE = "https://claude.ai/api"


TRAY_CONFIG_FILE = Path.home() / ".claude-tray" / "settings.json"


def _load_session_key() -> Optional[str]:
    """
    Returns the claude.ai sessionKey. Priority:
    1. Manually configured in settings
    2. Auto-extracted from Chrome/Edge browser cookies
    """
    # 1. Manual config
    if TRAY_CONFIG_FILE.exists():
        try:
            with open(TRAY_CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            sk = cfg.get("session_key", "").strip()
            if sk:
                return sk
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Auto-extract from browser
    try:
        import browser_cookie
        sk = browser_cookie.get_session_key()
        if sk:
            return sk
    except Exception:
        pass

    return None


def _get(path: str, session_key: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Cookie": f"sessionKey={session_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://claude.ai/",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def fetch_plan_usage(session_key: Optional[str] = None) -> dict:
    """
    Returns a dict with:
      - logged_in: bool
      - session_pct: float (0–100), current session % used
      - session_resets_in: str  (e.g. "1h 13m")
      - weekly_pct: float (0–100), weekly % used
      - weekly_resets_at: str
      - extra_spent_usd: float
      - extra_limit_usd: float
      - balance_usd: float
      - subscription_type: str
      - error: str | None
    """
    sk = session_key or _load_session_key()
    if not sk:
        return {"logged_in": False, "error": "No session key — paste it in Settings"}

    try:
        data = _get("/account", sk)
        return _parse_billing(data, sk)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"logged_in": False, "error": "Session expired — update the key in Settings"}
        return {"logged_in": False, "error": f"HTTP {e.code}"}
    except Exception as exc:
        return {"logged_in": False, "error": str(exc)}


def _parse_billing(data: dict, token: str) -> dict:
    result = {
        "logged_in": True,
        "error": None,
        "session_pct": 0.0,
        "session_resets_in": "",
        "weekly_pct": 0.0,
        "weekly_resets_at": "",
        "extra_spent_usd": 0.0,
        "extra_limit_usd": 0.0,
        "balance_usd": 0.0,
        "subscription_type": "",
    }

    # Try common response shapes
    # Shape 1: { usage_limits: { current_session: {...}, weekly: {...} } }
    limits = data.get("usage_limits") or data.get("usageLimits") or data
    session = limits.get("current_session") or limits.get("currentSession") or {}
    weekly = limits.get("weekly") or limits.get("allModels") or {}
    billing = data.get("billing") or data.get("account") or data

    result["session_pct"] = _to_pct(session.get("percent_used") or
                                    session.get("percentUsed") or
                                    session.get("usage_percent", 0))
    result["session_resets_in"] = (session.get("resets_in") or
                                   session.get("resetsIn") or
                                   session.get("reset_time") or "")
    result["weekly_pct"] = _to_pct(weekly.get("percent_used") or
                                   weekly.get("percentUsed") or
                                   weekly.get("usage_percent", 0))
    result["weekly_resets_at"] = (weekly.get("resets_at") or
                                  weekly.get("resetsAt") or "")
    result["extra_spent_usd"] = float(billing.get("extra_usage_spent") or
                                      billing.get("extraUsageSpent") or 0)
    result["extra_limit_usd"] = float(billing.get("extra_usage_limit") or
                                      billing.get("monthlySpendLimit") or
                                      billing.get("monthly_spend_limit") or 0)
    result["balance_usd"] = float(billing.get("balance") or
                                  billing.get("current_balance") or 0)
    result["subscription_type"] = (billing.get("subscription_type") or
                                   billing.get("subscriptionType") or "")
    return result


def _to_pct(val) -> float:
    if val is None:
        return 0.0
    f = float(val)
    return f * 100 if f <= 1.0 else f
