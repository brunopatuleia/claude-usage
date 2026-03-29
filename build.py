"""
build.py — full build pipeline for Claude Usage Tray

Step 1: PyInstaller  →  dist/ClaudeUsageTray.exe   (portable executable)
Step 2: Inno Setup   →  dist/ClaudeUsageTray-Setup-x.x.x.exe  (installer)

Usage:
    pip install pyinstaller
    python build.py           # builds both exe + installer (if Inno Setup found)
    python build.py --exe     # portable exe only
    python build.py --installer  # installer only (exe must already exist)
"""

import os
import shutil
import subprocess
import sys

# ── Step 1: PyInstaller ──────────────────────────────────────────────────────

PYINSTALLER_CMD = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",           # no console window on Windows
    "--name", "ClaudeUsageTray",
    "--clean",
    "main.py",
]

# Add icon if present
if os.path.exists("assets/icon.ico"):
    PYINSTALLER_CMD += ["--icon", "assets/icon.ico"]

# Add assets folder if present
if os.path.exists("assets"):
    PYINSTALLER_CMD += ["--add-data", "assets;assets"]


def build_exe() -> bool:
    print("=" * 50)
    print("Step 1/2 — Building ClaudeUsageTray.exe (PyInstaller)")
    print("=" * 50)
    result = subprocess.run(PYINSTALLER_CMD)
    if result.returncode != 0:
        print("\n[ERROR] PyInstaller failed.")
        return False
    print("\n[OK] dist/ClaudeUsageTray.exe ready.")
    return True


# ── Step 2: Inno Setup ───────────────────────────────────────────────────────

INNO_SEARCH_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    r"C:\Program Files\Inno Setup 5\ISCC.exe",
]


def find_iscc() -> str | None:
    # Check PATH first
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if iscc:
        return iscc
    for path in INNO_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    return None


def build_installer() -> bool:
    if not os.path.exists("dist/ClaudeUsageTray.exe"):
        print("[ERROR] dist/ClaudeUsageTray.exe not found — run step 1 first.")
        return False

    iscc = find_iscc()
    if not iscc:
        print("\n[SKIP] Inno Setup not found — skipping installer step.")
        print("       Install from https://jrsoftware.org/isdl.php")
        print("       Then re-run:  python build.py --installer")
        return False

    print("\n" + "=" * 50)
    print("Step 2/2 — Building installer (Inno Setup)")
    print("=" * 50)
    result = subprocess.run([iscc, "installer.iss"])
    if result.returncode != 0:
        print("\n[ERROR] Inno Setup failed.")
        return False
    print("\n[OK] Installer ready in dist/")
    return True


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    exe_only = "--exe" in args
    installer_only = "--installer" in args

    if installer_only:
        build_installer()
        return

    ok = build_exe()
    if not ok:
        sys.exit(1)

    if not exe_only:
        build_installer()

    print("\n✓ Build complete.")
    print("  Portable EXE : dist/ClaudeUsageTray.exe")
    print("  Installer    : dist/ClaudeUsageTray-Setup-*.exe  (if Inno Setup was found)")


if __name__ == "__main__":
    main()
