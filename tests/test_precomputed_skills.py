"""analyze() has to work from precomputed index records and from raw text alike.

The raw-text path is what --keep-boilerplate uses and what every other test relies on; the
precomputed path is what makes a corpus of thousands of postings analyzable in milliseconds.
"""

from backend.market import analyze, posting_skills


def test_precomputed_names_resolve_to_full_skills():
    resolved = posting_skills({"company": "Acme", "title": "Engineer", "skills": ["python"]})

    assert [s["display_name"] for s in resolved] == ["Python"]
    assert resolved[0]["category"]


def test_extraction_is_the_fallback_when_no_skills_are_supplied():
    resolved = posting_skills({"company": "Acme", "title": "Engineer", "text": "We use Python."})

    assert [s["display_name"] for s in resolved] == ["Python"]


def test_names_no_longer_in_the_vocabulary_are_skipped():
    resolved = posting_skills({"skills": ["python", "a-skill-that-was-removed"]})

    assert [s["display_name"] for s in resolved] == ["Python"]


def test_both_paths_produce_the_same_report():
    raw = [
        {"company": "Acme", "title": "Engineer", "text": "We use Python and Docker."},
        {"company": "Beta", "title": "Analyst", "text": "We use Python."},
    ]
    precomputed = [
        {"company": "Acme", "title": "Engineer", "skills": ["python", "docker"]},
        {"company": "Beta", "title": "Analyst", "skills": ["python"]},
    ]

    assert analyze(raw) == analyze(precomputed)
