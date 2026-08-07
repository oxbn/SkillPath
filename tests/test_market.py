from backend.market import analyze
from backend.postings import MIN_POSTINGS_FOR_STRIPPING, strip_boilerplate, strip_html


def posting(company, text, title="Engineer"):
    return {"company": company, "title": title, "text": text}


def test_strip_html_keeps_paragraph_breaks():
    # Greenhouse escapes its markup once, so the input arrives looking like this.
    content = "&lt;p&gt;We use Python.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;And SQL.&lt;/li&gt;&lt;/ul&gt;"

    assert strip_html(content).split("\n") == ["We use Python.", "And SQL."]


def test_strip_html_resolves_double_escaped_entities():
    assert "&nbsp;" not in strip_html("&lt;p&gt;Python&amp;nbsp;3&lt;/p&gt;")


def test_boilerplate_repeated_across_a_company_is_removed():
    postings = [
        posting("Acme", f"We are an equal opportunity employer.\nRole {n} needs Python.")
        for n in range(MIN_POSTINGS_FOR_STRIPPING + 1)
    ]

    stripped = strip_boilerplate(postings)

    assert all("equal opportunity" not in p["text"] for p in stripped)
    assert all("Python" in p["text"] for p in stripped)
    assert all("equal opportunity" in p["boilerplate"][0] for p in stripped)


def test_small_boards_are_left_alone():
    # Below the minimum, "in most postings" is noise — two postings sharing a line is normal.
    postings = [posting("Tiny", "Shared line.\nRole A.") for _ in range(2)]

    stripped = strip_boilerplate(postings)

    assert all("Shared line." in p["text"] for p in stripped)


def test_company_naming_itself_is_not_a_requirement():
    postings = [posting("Figma", "Figma is growing. This role needs Python.")]

    skills = {s["display_name"] for s in analyze(postings)["skills"]}

    assert "Figma" not in skills
    assert "Python" in skills


def test_share_is_document_frequency_not_mention_count():
    postings = [
        posting("Acme", "Python Python Python Python Python."),
        posting("Beta", "We use Docker."),
    ]

    report = analyze(postings)
    by_name = {s["display_name"]: s for s in report["skills"]}

    assert by_name["Python"]["postings"] == 1
    assert by_name["Python"]["share"] == 0.5
    assert by_name["Docker"]["share"] == 0.5


def test_company_count_exposes_single_source_skills():
    postings = [
        posting("Acme", "We use Scala."),
        posting("Acme", "More Scala."),
        posting("Beta", "We use Python."),
    ]

    by_name = {s["display_name"]: s for s in analyze(postings)["skills"]}

    assert by_name["Scala"]["postings"] == 2
    assert by_name["Scala"]["companies"] == 1
    assert analyze(postings)["companies"] == 2
