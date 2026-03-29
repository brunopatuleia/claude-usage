"""
browser_cookie.py — auto-extracts the claude.ai sessionKey from any installed browser.

Supports: Chrome, Edge, Brave, Opera, Vivaldi (AES-GCM/DPAPI encrypted)
          Firefox (plaintext SQLite — easiest)
"""

import base64
import ctypes
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional


# ── Windows DPAPI ─────────────────────────────────────────────────────────────

class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_decrypt(data: bytes) -> bytes:
    blob_in = _BLOB(len(data),
                    ctypes.cast(ctypes.create_string_buffer(data, len(data)),
                                ctypes.POINTER(ctypes.c_ubyte)))
    blob_out = _BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out))
    if not ok:
        raise OSError("CryptUnprotectData failed")
    result = bytes(blob_out.pbData[:blob_out.cbData])
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return result


# ── Chromium cookie decryption (Chrome / Edge / Brave / Opera / Vivaldi) ──────

def _decrypt_chromium_cookie(enc: bytes, aes_key: bytes) -> Optional[str]:
    try:
        if enc[:3] in (b"v10", b"v11"):
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(aes_key).decrypt(enc[3:15], enc[15:], None).decode()
        else:
            return _dpapi_decrypt(enc).decode()
    except Exception:
        return None


def _chromium_aes_key(user_data: Path) -> Optional[bytes]:
    try:
        state = json.loads((user_data / "Local State").read_text(encoding="utf-8"))
        return _dpapi_decrypt(base64.b64decode(state["os_crypt"]["encrypted_key"])[5:])
    except Exception:
        return None


CHROMIUM_DIRS = [
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
    Path.home() / "AppData/Local/Opera Software/Opera Stable",
    Path.home() / "AppData/Roaming/Opera Software/Opera GX Stable",
    Path.home() / "AppData/Local/Vivaldi/User Data",
    Path.home() / "AppData/Local/Google/Chrome Beta/User Data",
]


def _search_chromium() -> Optional[str]:
    for user_data in CHROMIUM_DIRS:
        if not user_data.exists():
            continue
        aes_key = _chromium_aes_key(user_data)
        # Check Default + all numbered profiles
        for cookies_path in sorted(user_data.glob("*/Network/Cookies")):
            tmp = tempfile.mktemp(suffix=".db")
            try:
                shutil.copy2(cookies_path, tmp)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT encrypted_value FROM cookies "
                    "WHERE host_key LIKE '%claude.ai%' AND name='sessionKey'"
                ).fetchall()
                con.close()
                for (enc,) in rows:
                    val = _decrypt_chromium_cookie(bytes(enc), aes_key) if aes_key else None
                    if val:
                        return val
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    return None


# ── Firefox ───────────────────────────────────────────────────────────────────

FIREFOX_DIRS = [
    Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles",
    Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles".replace("Mozilla/Firefox", "Zen Browser"),
    Path.home() / "AppData/Roaming/waterfox/Profiles",
    Path.home() / "AppData/Roaming/LibreWolf/Profiles",
]


def _search_firefox() -> Optional[str]:
    for profiles_root in FIREFOX_DIRS:
        if not profiles_root.exists():
            continue
        for cookies_path in profiles_root.glob("*/cookies.sqlite"):
            tmp = tempfile.mktemp(suffix=".db")
            try:
                shutil.copy2(cookies_path, tmp)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT value FROM moz_cookies "
                    "WHERE host LIKE '%claude.ai%' AND name='sessionKey'"
                ).fetchall()
                con.close()
                for (val,) in rows:
                    if val:
                        return val
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_session_key() -> Optional[str]:
    """
    Scans all installed browsers for a valid claude.ai sessionKey cookie.
    Tries Firefox first (plaintext), then Chromium-based browsers.
    Returns None if the user isn't logged into claude.ai in any browser.
    """
    return _search_firefox() or _search_chromium()
