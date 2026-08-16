"""Fetcher and index behaviour. No network: responses are fixtures, caches are tmp_path."""

import json

import pytest

from backend import postings as postings_module
from backend.postings import (
    StaleIndexError,
    cached_boards,
    fetch_ashby,
    fetch_board,
    fetch_greenhouse,
    load_index,
    normalize_plain_text,
    write_index,
)

ASHBY_RESPONSE = {
    "jobs": [
        {
            "id": "abc-123",
            "title": "  Senior Data Engineer  ",
            "descriptionPlain": "We use Python.\n\n\nAnd   SQL.",
            "jobUrl": "https://jobs.ashbyhq.com/acme/abc-123",
            "location": "Remote",
            "publishedAt": "2026-08-01T00:00:00Z",
            "isListed": True,
        },
        {"id": "gone", "title": "Unlisted", "descriptionPlain": "x", "isListed": False},
    ]
}

GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 42,
            "title": " Backend Engineer ",
            "content": "&lt;p&gt;We use Python.&lt;/p&gt;",
            "company_name": "Acme",
            "location": {"name": "NYC"},
            "absolute_url": "https://boards.greenhouse.io/acme/42",
            "updated_at": "2026-08-01",
        }
    ]
}


@pytest.fixture
def no_network(monkeypatch):
    def respond(payload):
        monkeypatch.setattr(postings_module, "fetch_json", lambda url: payload)

    return respond


def test_ashby_postings_match_the_shared_posting_shape(no_network):
    no_network(ASHBY_RESPONSE)

    posting = fetch_ashby("acme")[0]

    assert posting["source"] == "ashby"
    assert posting["title"] == "Senior Data Engineer"
    assert posting["company"] == "acme"  # Ashby sends no company name; the token stands in.
    assert posting["url"] == "https://jobs.ashbyhq.com/acme/abc-123"
    # descriptionPlain needs no markup stripping, only whitespace normalising.
    assert posting["text"] == "We use Python.\nAnd SQL."


def test_ashby_skips_unlisted_jobs(no_network):
    no_network(ASHBY_RESPONSE)

    assert [posting["title"] for posting in fetch_ashby("acme")] == ["Senior Data Engineer"]


def test_greenhouse_and_ashby_produce_the_same_keys(no_network):
    no_network(GREENHOUSE_RESPONSE)
    greenhouse = fetch_greenhouse("acme")[0]
    no_network(ASHBY_RESPONSE)
    ashby = fetch_ashby("acme")[0]

    assert set(greenhouse) == set(ashby)


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="Unknown source"):
        fetch_board("acme", "monster.com")


def test_normalize_plain_text_drops_blank_lines_and_runs_of_spaces():
    assert normalize_plain_text("a  b\n\n\n  c  ") == "a b\nc"


@pytest.fixture
def temp_index(monkeypatch, tmp_path):
    monkeypatch.setattr(postings_module, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(postings_module, "index_path", lambda board: tmp_path / f"{board}.json")
    return tmp_path


def test_index_round_trips(temp_index):
    records = [{"company": "Acme", "title": "Engineer", "skills": ["python", "docker"]}]

    write_index("acme", records)

    assert load_index(["acme"]) == records
    assert cached_boards() == ["acme"]


def test_index_built_against_another_vocabulary_is_refused(temp_index):
    write_index("acme", [{"company": "Acme", "title": "Engineer", "skills": ["python"]}])

    stored = json.loads((temp_index / "acme.json").read_text(encoding="utf-8"))
    stored["vocabulary"] = "not-the-current-one"
    (temp_index / "acme.json").write_text(json.dumps(stored), encoding="utf-8")

    # Silently reporting numbers from a stale vocabulary would be worse than failing.
    with pytest.raises(StaleIndexError, match="--reextract"):
        load_index(["acme"])


def test_missing_index_names_the_command_that_builds_it(temp_index):
    with pytest.raises(StaleIndexError, match="fetch_postings"):
        load_index(["never-fetched"])
