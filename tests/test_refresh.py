import json
import threading

from backend import refresh
from backend.postings import atomic_json


def setup_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(refresh, "load_boards", lambda: [{"token": "test", "source": "ashby"}])
    monkeypatch.setattr(refresh, "cache_path", lambda board: tmp_path / "raw.json")
    monkeypatch.setattr(refresh, "index_path", lambda board: tmp_path / "index.json")
    return refresh.Refresher()


def test_first_fetch_and_no_duplicate_refresh(monkeypatch, tmp_path):
    service = setup_refresh(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def load(board, refresh, source):
        calls.append((board, refresh, source))
        entered.set()
        release.wait(5)
        return []

    monkeypatch.setattr(refresh, "load_board", load)
    monkeypatch.setattr(refresh, "build_index", lambda *args: None)
    assert service.start_refresh()
    try:
        assert entered.wait(5)
        assert not service.start_refresh(force=True)
    finally:
        release.set()
        service.worker.join(5)
    assert calls == [("test", True, "ashby")]
    assert service.status()["last_updated"]
    assert not service.status()["running"]


def test_failure_keeps_previous_index_and_success_time(monkeypatch, tmp_path):
    service = setup_refresh(monkeypatch, tmp_path)
    service.state["last_updated"] = "previous"
    index = tmp_path / "index.json"
    atomic_json(index, {"vocabulary": refresh.vocabulary_fingerprint(), "postings": ["old"]})

    def fail(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(refresh, "load_board", fail)
    service.lock.acquire()
    service.refresh(True)
    assert json.loads(index.read_text())["postings"] == ["old"]
    assert service.status()["failed_boards"] == ["test"]
    assert service.status()["last_updated"] == "previous"


def test_stale_vocabulary_rebuilds_without_network(monkeypatch, tmp_path):
    service = setup_refresh(monkeypatch, tmp_path)
    atomic_json(tmp_path / "raw.json", {"postings": []})
    atomic_json(tmp_path / "index.json", {"vocabulary": "old"})
    calls = []
    monkeypatch.setattr(refresh, "load_board", lambda board, refresh, source: calls.append(refresh) or [])
    monkeypatch.setattr(refresh, "build_index", lambda *args: None)
    service.lock.acquire()
    service.refresh(False)
    assert calls == [False]
    assert not service.status()["failed_boards"]


def test_corrupt_index_is_rebuilt_from_cache(monkeypatch, tmp_path):
    service = setup_refresh(monkeypatch, tmp_path)
    atomic_json(tmp_path / "raw.json", {"postings": []})
    (tmp_path / "index.json").write_text("broken json")
    calls = []
    monkeypatch.setattr(refresh, "load_board", lambda board, refresh, source: calls.append(refresh) or [])
    monkeypatch.setattr(refresh, "build_index", lambda *args: None)
    service.lock.acquire()
    service.refresh(False)
    assert calls == [False]
    assert not service.status()["failed_boards"]
