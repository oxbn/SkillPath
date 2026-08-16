"""Self-reference filtering, which more boards makes more important rather than less.

Each company whose own product is in the vocabulary would otherwise inflate that product's
apparent demand using nothing but its own marketing copy.
"""

import pytest

from backend.market import analyze, company_tokens, is_self_reference


def skill(name):
    return {"name": name}


@pytest.mark.parametrize(
    "company, name",
    [
        ("Figma", "figma"),
        ("MongoDB, Inc.", "mongodb"),
        ("Datadog", "datadog"),
        # The multi-word cases equality-matching used to miss entirely.
        ("Elastic", "elasticsearch"),
        ("Amazon", "amazon web services aws software"),
        ("Oracle", "oracle java"),
        ("Atlassian", "atlassian jira"),
    ],
)
def test_a_company_naming_its_own_product_is_filtered(company, name):
    assert is_self_reference(skill(name), company)


@pytest.mark.parametrize(
    "company, name",
    [
        # The reason this matches on a word boundary and not as a bare substring: "box" appears
        # inside "dropbox", and Box must not suppress a competitor's product.
        ("Box", "dropbox"),
        ("Stripe", "python"),
        ("Acme", "amazon web services aws software"),
        # Entity noise must not match half the vocabulary.
        ("The Software Group", "software libraries"),
    ],
)
def test_unrelated_skills_survive(company, name):
    assert not is_self_reference(skill(name), company)


def test_company_tokens_drop_entity_words_and_short_fragments():
    assert company_tokens("MongoDB, Inc.") == {"mongodb"}
    assert company_tokens("Elastic Technologies Ltd") == {"elastic"}


def test_self_reference_is_scoped_to_the_company_that_said_it():
    """Elastic's own ads shouldn't count Elasticsearch — but everyone else's should."""
    postings = [
        {"company": "Elastic", "title": "Engineer", "text": "Elasticsearch and Python."},
        {"company": "Acme", "title": "Engineer", "text": "Elasticsearch and Python."},
    ]

    by_name = {s["display_name"]: s for s in analyze(postings)["skills"]}

    assert by_name["Elasticsearch"]["postings"] == 1
    assert by_name["Elasticsearch"]["companies"] == 1
    assert by_name["Python"]["postings"] == 2
