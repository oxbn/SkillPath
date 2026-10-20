"""Offline server used only by browser smoke tests."""
import json
import os
from pathlib import Path

# Set by the browser fixture before this module is imported.
assert os.environ.get("SKILLPATH_CACHE_DIR"), "Browser server requires an isolated cache"

from app import app, refresher
from backend.scripts.fetch_postings import build_index

fixture = json.loads((Path(__file__).parent / "fixtures/corpus.json").read_text())
build_index("sample", "fixture", fixture["postings"])


class FakeRefresh:
    running = False
    polls = 0

    def start_refresh(self, force=False):
        self.running = True
        self.polls = 0
        return True

    def status(self):
        self.polls += 1
        if self.polls > 1:
            self.running = False
        return {"running": self.running, "last_updated": "2026-01-01T00:00:00Z", "failed_boards": []}


fake = FakeRefresh()
refresher.start = lambda: None
refresher.stop = lambda: None
refresher.start_refresh = fake.start_refresh
refresher.status = fake.status
