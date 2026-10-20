import json
from pathlib import Path

import pytest

from backend.market import analyze
from backend.postings import strip_boilerplate
from backend.skills_extractor import extract_skills
from backend.scripts.fetch_postings import build_index

FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "context_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[f"{c['label']}-{i}" for i, c in enumerate(CASES)])
def test_labeled_context(case):
    skill = next(s for s in extract_skills(case["text"]) if s["display_name"] == case["skill"])
    assert skill["evidence"][0]["classification"] == case["label"]
    match = skill["evidence"][0]
    assert case["text"][match["start"]:match["end"]] in skill["mentions"]


def test_repeated_requirements_survive_but_company_blurb_is_audited():
    raw = [{"company": "Acme", "text": f"About us\nOur mission is great.\nRequirements:\nPython\nExperience with Docker.\nRole {i}"} for i in range(6)]
    for posting in strip_boilerplate(raw):
        assert "Python" in posting["text"]
        assert "Experience with Docker." in posting["text"]
        assert "Our mission is great." in posting["boilerplate"]
        assert "About us" in posting["text"]


def test_repetition_without_incidental_context_is_not_enough_to_remove_skills():
    raw = [{"company": "Acme", "text": f"We use Python.\nRole {i}"} for i in range(6)]
    assert all("Python" in p["text"] for p in strip_boilerplate(raw))


def test_fixed_corpus_raw_and_indexed_reports_match(monkeypatch):
    corpus = json.loads((FIXTURES / "corpus.json").read_text())
    monkeypatch.setattr("backend.scripts.fetch_postings.write_index", lambda *args: None)
    indexed = build_index("fixture", "fixture", corpus["postings"])
    raw_report = analyze(corpus["postings"])
    assert analyze(indexed) == raw_report
    assert analyze(indexed, True) == analyze(corpus["postings"], True)
    actual = {s["display_name"]: {key: s[key] for key in ("postings", "companies", "share")} for s in raw_report["skills"]}
    assert actual == corpus["expected"]


def test_requirements_only_excludes_unknown_mentions():
    raw = [{"company": "Acme", "text": "We use Python. Docker experience required."}]
    assert {s["display_name"] for s in analyze(raw, True)["skills"]} == {"Docker"}


def test_single_letter_document_references_are_not_languages():
    assert not extract_skills("See R for details in section C.")
    assert {s["display_name"] for s in extract_skills("Experience with C and R.")} == {"C", "R"}


def test_duplicate_precomputed_skills_count_once():
    report = analyze([{"company": "Acme", "skills": ["python", "python"]}])
    assert report["skills"][0]["share"] == 1


def test_long_repeated_text_has_bounded_deduplicated_evidence():
    python = next(s for s in extract_skills("Python " * 1000) if s["display_name"] == "Python")
    assert python["count"] == 1000
    assert all(len(e["text"]) <= 400 for e in python["evidence"])
    assert len(python["evidence"]) < 100


def test_duplicate_sentence_evidence_preserves_counts_and_distinct_labels():
    python = next(s for s in extract_skills("Python required. Python required. Python is a plus.") if s["display_name"] == "Python")
    assert python["count"] == 3
    assert len(python["evidence"]) == 2
    assert {e["classification"] for e in python["evidence"]} == {"required", "optional"}
