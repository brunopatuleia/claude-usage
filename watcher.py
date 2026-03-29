"""
watcher.py — watches ~/.claude/projects for new JSONL entries and fires a callback.
Uses watchdog for instant file-system notifications (no polling).
"""

import threading
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent


class _Handler(FileSystemEventHandler):
    def __init__(self, callback: Callable) -> None:
        self._callback = callback
        self._lock = threading.Lock()
        self._pending = False

    def _schedule(self) -> None:
        """Debounce: fire callback at most once per 2 seconds."""
        with self._lock:
            if self._pending:
                return
            self._pending = True

        def _fire():
            import time
            time.sleep(2)
            with self._lock:
                self._pending = False
            self._callback()

        threading.Thread(target=_fire, daemon=True).start()

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".jsonl"):
            self._schedule()

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".jsonl"):
            self._schedule()


class ProjectWatcher:
    def __init__(self, claude_dir: Path, on_change: Callable) -> None:
        self._dir = claude_dir / "projects"
        self._on_change = on_change
        self._observer: Observer | None = None

    def start(self) -> None:
        if not self._dir.exists():
            return
        handler = _Handler(self._on_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._dir), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
