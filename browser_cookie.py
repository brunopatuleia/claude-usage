"""
browser_cookie.py — auto-extracts the claude.ai sessionKey from Chrome/Edge.

Chrome/Edge encrypt cookies with AES-GCM using a key protected by Windows DPAPI.
This module decrypts it transparently — no user action needed.
"""

import base64
import ctypes
import json
import os
import shutil
import sqlite3
import struct
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


# ── AES-GCM cookie decryption ─────────────────────────────────────────────────

def _decrypt_cookie(encrypted_value: bytes, aes_key: bytes) -> Optional[str]:
    try:
        if encrypted_value[:3] == b"v10" or encrypted_value[:3] == b"v11":
            # Chrome 80+ format: v10/v11 + 12-byte nonce + ciphertext
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            return AESGCM(aes_key).decrypt(nonce, ciphertext, None).decode("utf-8")
        else:
            # Older DPAPI-only format
            return _dpapi_decrypt(encrypted_value).decode("utf-8")
    except Exception:
        return None


def _get_aes_key(user_data_dir: Path) -> Optional[bytes]:
    local_state_file = user_data_dir / "Local State"
    if not local_state_file.exists():
        return None
    try:
        local_state = json.loads(local_state_file.read_text(encoding="utf-8"))
        b64_key = local_state["os_crypt"]["encrypted_key"]
        encrypted_key = base64.b64decode(b64_key)[5:]  # strip 'DPAPI' prefix
        return _dpapi_decrypt(encrypted_key)
    except Exception:
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

BROWSER_DIRS = [
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
]


def get_session_key() -> Optional[str]:
    """
    Automatically extracts the claude.ai sessionKey cookie from Chrome/Edge/Brave.
    Returns None if not found or not logged in.
    """
    for user_data in BROWSER_DIRS:
        if not user_data.exists():
            continue

        aes_key = _get_aes_key(user_data)

        # Search all profiles (Default, Profile 1, Profile 2, …)
        for cookies_path in sorted(user_data.glob("*/Network/Cookies")):
            tmp = tempfile.mktemp(suffix=".db")
            try:
                shutil.copy2(cookies_path, tmp)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT name, encrypted_value FROM cookies "
                    "WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey'"
                ).fetchall()
                con.close()

                for name, enc_val in rows:
                    if aes_key:
                        val = _decrypt_cookie(bytes(enc_val), aes_key)
                    else:
                        try:
                            val = _dpapi_decrypt(bytes(enc_val)).decode("utf-8")
                        except Exception:
                            val = None
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
