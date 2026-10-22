import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as web
from backend import postings
from backend.scripts.fetch_postings import build_index


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(web.refresher, "start", lambda: None)
    monkeypatch.setattr(web.refresher, "stop", lambda: None)
    monkeypatch.setattr(web.refresher, "start_refresh", lambda force=False: False)
    monkeypatch.setattr(web.refresher, "status", lambda: {
        "running": False, "last_updated": None, "failed_boards": [],
    })
    monkeypatch.setattr(postings, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(postings, "POSTINGS_DIR", tmp_path / "raw")
    web.market_report.cache_clear()
    with TestClient(web.app) as client:
        yield client
    web.market_report.cache_clear()


@pytest.fixture
def corpus(client):
    fixture = json.loads((Path(__file__).parent / "fixtures/corpus.json").read_text())
    build_index("sample", "fixture", fixture["postings"])
    return client


def test_pages_and_static_assets(client):
    for path in ("/", "/market", "/static/app.js", "/static/style.css"):
        assert client.get(path).status_code == 200


def test_extract_validation_and_evidence(client):
    assert client.post("/extract", json={"text": "x" * 50001}).status_code == 422
    assert client.post("/extract", json={}).status_code == 422
    assert client.post("/extract", json={"text": ""}).json() == {"skills": []}
    body = client.post("/extract", json={"text": "Python is not required."}).json()
    assert body["skills"][0]["evidence"][0]["classification"] == "negated"


def test_missing_and_stale_indexes(client):
    assert client.get("/api/market").status_code == 404
    postings.atomic_json(postings.index_path("old"), {"vocabulary": "old", "postings": []})
    assert client.get("/api/market").status_code == 409


def test_filters_counts_and_provenance(corpus):
    body = corpus.get("/api/market", params={"title": "engineer"}).json()
    assert body["postings"] == 2
    assert body["corpus"][0]["analysis_version"] == postings.ANALYSIS_VERSION
    assert body["corpus"][0]["vocabulary"] == postings.vocabulary_fingerprint()
    assert body["skills"][0]["company_share"] == 1
    assert corpus.get("/api/market", params={"title": "engineer|analyst", "regex": True}).json()["postings"] == 3
    assert corpus.get("/api/market", params={"title": "engineer|analyst"}).json()["postings"] == 0
    assert corpus.get("/api/market", params={"title": "[", "regex": True}).status_code == 422
    assert corpus.get("/api/market", params={"title": "x" * 201}).status_code == 422


def test_report_cache_invalidates_when_index_changes(corpus):
    assert corpus.get("/api/market").json()["postings"] == 4
    build_index("sample", "fixture", [{"company": "Acme", "title": "Engineer", "text": "Python"}])
    assert corpus.get("/api/market").json()["postings"] == 1


def test_refresh_origin_and_duplicate_request(client):
    assert client.post("/api/refresh", headers={"origin": "https://elsewhere.example"}).status_code == 403
    response = client.post("/api/refresh", headers={"origin": "http://testserver"})
    assert response.status_code == 202
    assert response.json()["started"] is False
    assert client.get("/api/refresh").json()["running"] is False


def test_company_and_skill_details_follow_report_filters(corpus):
    report = corpus.get("/api/market", params={"title": "engineer", "requirements_only": True}).json()
    assert report["company_breakdown"] == [{"name": "Acme", "postings": 1}, {"name": "Figma", "postings": 1}]
    python = next(skill for skill in report["skills"] if skill["name"] == "python")
    assert python["breakdown"] == [
        {"name": "Acme", "postings": 1, "titles": [{"title": "Data Engineer", "postings": 1}]},
        {"name": "Figma", "postings": 1, "titles": [{"title": "Plugin Engineer", "postings": 1}]},
    ]
    figma = next(skill for skill in report["skills"] if skill["name"] == "figma")
    assert figma["breakdown"] == [{"name": "Figma", "postings": 1,
                                  "titles": [{"title": "Plugin Engineer", "postings": 1}]}]
