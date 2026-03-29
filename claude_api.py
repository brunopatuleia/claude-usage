"""
claude_api.py — fetches live plan usage from claude.ai.

Auth strategy (in priority order):
  1. sessionKey manually set in app settings
  2. sessionKey auto-extracted from any installed browser (Chrome, Edge, Firefox, etc.)

The plan usage data (session %, weekly %) aggregates ALL platforms — web, mobile,
CLI on every machine — because it's server-side account-level data.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

API_BASE = "https://claude.ai/api"
TRAY_CONFIG_FILE = Path.home() / ".claude-tray" / "settings.json"

_CLI_HEADERS = {
    "User-Agent": "claude-cli/1.0",
    "Accept": "application/json",
    "anthropic-client-platform": "claude_cli",
    "anthropic-version": "2023-06-01",
}


# ── Auth ──────────────────────────────────────────────────────────────────────

def _load_session_key() -> Optional[str]:
    # 1. Manual config
    if TRAY_CONFIG_FILE.exists():
        try:
            cfg = json.loads(TRAY_CONFIG_FILE.read_text(encoding="utf-8"))
            sk = cfg.get("session_key", "").strip()
            if sk:
                return sk
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Auto-extract from any installed browser
    try:
        import browser_cookie
        return browser_cookie.get_session_key()
    except Exception:
        return None


def _headers(session_key: str) -> dict:
    return {
        **_CLI_HEADERS,
        "Cookie": f"sessionKey={session_key}",
    }


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(path: str, session_key: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}", headers=_headers(session_key))
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch_plan_usage(session_key: Optional[str] = None) -> dict:
    """
    Returns aggregated plan usage across ALL platforms.
    Keys: logged_in, session_pct, session_resets_in,
          weekly_pct, weekly_resets_at,
          extra_spent_usd, extra_limit_usd, balance_usd,
          subscription_type, error
    """
    sk = session_key or _load_session_key()
    if not sk:
        return {"logged_in": False,
                "error": "Not connected — log into claude.ai in any browser"}

    try:
        # Step 1: get org ID from bootstrap
        bootstrap = _get("/bootstrap", sk)
        account = bootstrap.get("account") or {}
        memberships = account.get("memberships") or []

        org_id = None
        for m in memberships:
            org = m.get("organization") or {}
            if org.get("id"):
                org_id = org["id"]
                break

        if not org_id:
            # Fallback: try account id directly
            org_id = account.get("id")

        if not org_id:
            return {"logged_in": True,
                    "error": "Could not determine org ID from account"}

        # Step 2: fetch usage limits for this org
        usage = _get(f"/organizations/{org_id}/usage", sk)
        return _parse_usage(usage)

    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"logged_in": False,
                    "error": "Session expired — re-login to claude.ai in your browser"}
        body = e.read(200).decode(errors="ignore")
        return {"logged_in": False, "error": f"HTTP {e.code}: {body[:80]}"}
    except Exception as exc:
        return {"logged_in": False, "error": str(exc)}


def _parse_usage(data: dict) -> dict:
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

    # Try multiple response shapes
    limits = (data.get("usage_limits") or data.get("usageLimits")
              or data.get("rate_limits") or data)

    session = (limits.get("current_session") or limits.get("currentSession")
               or limits.get("session") or {})
    weekly = (limits.get("weekly") or limits.get("allModels")
              or limits.get("all_models") or {})
    billing = data.get("billing") or data.get("account") or data

    result["session_pct"] = _to_pct(
        session.get("percent_used") or session.get("percentUsed") or
        session.get("usage_percent") or 0)
    result["session_resets_in"] = (
        session.get("resets_in") or session.get("resetsIn") or
        session.get("reset_time") or "")
    result["weekly_pct"] = _to_pct(
        weekly.get("percent_used") or weekly.get("percentUsed") or
        weekly.get("usage_percent") or 0)
    result["weekly_resets_at"] = (
        weekly.get("resets_at") or weekly.get("resetsAt") or "")
    result["extra_spent_usd"] = float(
        billing.get("extra_usage_spent") or billing.get("extraUsageSpent") or 0)
    result["extra_limit_usd"] = float(
        billing.get("extra_usage_limit") or billing.get("monthlySpendLimit") or
        billing.get("monthly_spend_limit") or 0)
    result["balance_usd"] = float(
        billing.get("balance") or billing.get("current_balance") or 0)
    result["subscription_type"] = (
        billing.get("subscription_type") or billing.get("subscriptionType") or "")

    return result


def _to_pct(val) -> float:
    if val is None:
        return 0.0
    f = float(val)
    return f * 100 if f <= 1.0 else f
