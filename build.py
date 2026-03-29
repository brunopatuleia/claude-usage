"""
build.py — packages the app into a single Windows .exe using PyInstaller.

Usage:
    pip install pyinstaller
    python build.py
"""

import subprocess
import sys

CMD = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",                  # no console window
    "--name", "ClaudeUsageTray",
    "--icon", "assets/icon.ico",   # optional, add your own icon
    "--add-data", "assets;assets",
    "main.py",
]

# Remove --add-data if assets folder doesn't exist
import os
if not os.path.exists("assets"):
    CMD = [c for c in CMD if "assets" not in c]

if __name__ == "__main__":
    print("Building ClaudeUsageTray.exe ...")
    result = subprocess.run(CMD)
    if result.returncode == 0:
        print("\nDone! Output: dist/ClaudeUsageTray.exe")
    else:
        sys.exit(result.returncode)
