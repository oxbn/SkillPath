"""Background refresh for the single-process personal server."""
import json
import logging
import threading
import time
from datetime import datetime, timezone

from backend.postings import (
    CACHE_DIR, atomic_json, cache_path, index_path, load_board, load_boards,
    vocabulary_fingerprint,
)
from backend.scripts.fetch_postings import build_index

logger = logging.getLogger(__name__)


class Refresher:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = None
        self.scheduler = None
        self.running = False
        self.state_path = CACHE_DIR / "refresh.json"
        try:
            self.state = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            self.state = {"last_updated": None, "failed_boards": []}

    def status(self):
        return {**self.state, "running": self.running}

    def start_refresh(self, force=False):
        if not self.lock.acquire(blocking=False):
            return False
        self.running = True
        self.worker = threading.Thread(target=self.refresh, args=(force,), daemon=True)
        self.worker.start()
        return True

    def refresh(self, force):
        failures = []
        changed = False
        try:
            for board in load_boards():
                if self.stop_event.is_set():
                    return
                token, source = board["token"], board["source"]
                try:
                    raw = cache_path(token)
                    due = (force or token in self.state.get("failed_boards", [])
                           or not raw.exists() or time.time() - raw.stat().st_mtime >= 86400)
                    index = index_path(token)
                    stale = not index.exists()
                    if not stale:
                        try:
                            stale = json.loads(index.read_text()).get("vocabulary") != vocabulary_fingerprint()
                        except (OSError, ValueError, AttributeError):
                            stale = True
                    stale = stale or (raw.exists() and index.exists() and raw.stat().st_mtime_ns > index.stat().st_mtime_ns)
                    if due or stale:
                        postings = load_board(token, refresh=due, source=source)
                        build_index(token, source, postings)
                        changed = True
                    if due:
                        self.stop_event.wait(0.35)
                except Exception:
                    logger.exception("Refresh failed for %s", token)
                    failures.append(token)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.state = {
                "last_updated": now if changed and not failures else self.state.get("last_updated"),
                "last_attempt": now,
                "failed_boards": failures,
            }
            atomic_json(self.state_path, self.state)
        except Exception:
            logger.exception("Market refresh failed")
        finally:
            self.running = False
            self.lock.release()

    def start(self):
        def schedule():
            while not self.stop_event.is_set():
                self.start_refresh()
                # Check hourly; failed boards are retried on the next check.
                self.stop_event.wait(3600)
        self.scheduler = threading.Thread(target=schedule, daemon=True)
        self.scheduler.start()

    def stop(self):
        self.stop_event.set()
        if self.scheduler:
            self.scheduler.join()
        if self.worker:
            self.worker.join()
