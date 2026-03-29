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


def _load_token() -> Optional[str]:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except (json.JSONDecodeError, OSError):
        return None


def _get(path: str, token: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "ClaudeUsageTray/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def fetch_plan_usage() -> dict:
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
    token = _load_token()
    if not token:
        return {"logged_in": False, "error": "No credentials found"}

    try:
        data = _get("/account_billing_data", token)
        return _parse_billing(data, token)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"logged_in": False, "error": "Token expired — please re-login in Claude Code"}
        return {"logged_in": True, "error": f"HTTP {e.code}"}
    except Exception as exc:
        # Try alternate endpoint
        try:
            data = _get("/usage_limits", token)
            return _parse_billing(data, token)
        except Exception:
            pass
        return {"logged_in": True, "error": str(exc)}


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
