from backend.skills_extractor import SKILLS, extract_skills


def matched(text):
    return {skill["display_name"] for skill in extract_skills(text)}


def test_aliases_resolve_to_canonical_skills():
    found = matched("Stack: AWS, Terraform, Jenkins, Angular, Azure, Postgres, k8s, JS, Node.")

    assert "Amazon Web Services AWS software" in found
    assert "IBM Terraform" in found
    assert "Kubernetes" in found
    assert "PostgreSQL" in found
    assert "JavaScript" in found


def test_verb_go_does_not_match_the_language():
    assert "Go" not in matched("We will go over your code together.")


def test_capitalized_go_still_matches():
    assert "Go" in matched("Written in Go, Java, or Python.")


def test_cpp_does_not_leak_a_bare_c():
    found = matched("We write C++ and C# here.")

    assert found == {"C++", "C#"}


def test_standalone_c_still_matches():
    assert "C" in matched("Experience with C and Python.")


def test_nested_sql_is_suppressed():
    # "Microsoft SQL Server" contains the token SQL; only the longer match should survive.
    found = matched("Experience with Microsoft SQL Server.")

    assert "Microsoft SQL Server" in found
    assert "Structured query language SQL" not in found


def test_lowercase_acronyms_still_match():
    # php and sas are never English words, so they stay case-insensitive.
    assert "PHP" in matched("Legacy php code.")


# Each of these was a real false positive found in a corpus of Greenhouse postings.
def test_verb_excel_does_not_match_the_spreadsheet():
    assert "Microsoft Excel" not in matched("A culture where everyone can excel.")


def test_capitalized_excel_still_matches():
    assert "Microsoft Excel" in matched("Experience with CRM tools, Excel, and basic SQL.")


def test_verb_bootstrap_does_not_match_the_framework():
    assert "Bootstrap" not in matched("You will bootstrap or implement customer projects.")


def test_plural_sas_does_not_match_the_analytics_suite():
    assert "SAS" not in matched("Equipping AEs and SAs with the messaging they need.")


def test_uppercase_swift_network_does_not_match_the_language():
    assert "Swift" not in matched("Cheaper than SWIFT and other fiat rails.")


def test_titlecase_swift_still_matches():
    assert "Swift" in matched("Mobile experience: Kotlin, Java, Swift, Objective-C.")


def test_mentions_record_the_text_that_matched():
    postgres = next(s for s in extract_skills("We run Postgres here.") if s["name"] == "postgresql")

    assert postgres["mentions"] == ["Postgres"]
    assert postgres["display_name"] == "PostgreSQL"


def test_mentions_dedupe_case_insensitively():
    text = "Kubernetes, kubernetes, and KUBERNETES."
    k8s = next(s for s in extract_skills(text) if s["name"] == "kubernetes")

    assert k8s["count"] == 3
    assert k8s["mentions"] == ["Kubernetes"]


def test_count_tracks_repeats_and_orders_results():
    skills = extract_skills("Python and Docker. Python again. Python once more.")

    assert skills[0]["display_name"] == "Python"
    assert skills[0]["count"] == 3


def test_names_that_are_english_words_require_capitalization():
    """The deliberate trade-off of expanding past the 176 hot skills.

    "Python" is a dictionary word, so it matches only when capitalized. Postings capitalize
    product names almost always — lowercase spellings were ~1% of mentions in a real corpus —
    and this is what keeps "we analyze data to reduce cost" from matching two products.
    """
    assert "Python" in matched("Strong Python experience.")
    assert "Python" not in matched("a python is a snake")
    assert matched("We analyze data to reduce cost and react to changes.") == set()


def test_skills_outside_the_hot_list_are_included():
    found = matched("We use pandas, NumPy, scikit-learn, MLflow, and Kotlin.")

    assert {"pandas", "NumPy", "Scikit-learn", "Kotlin"} <= found


def test_modern_skills_absent_from_onet_are_included():
    found = matched("Stack: Rust, Next.js, dbt, FastAPI, Databricks, Vercel.")

    assert {"Rust", "Next.js", "dbt", "FastAPI", "Databricks", "Vercel"} <= found


def test_generic_onet_category_rows_are_excluded():
    found = matched("Experience with programming languages and software libraries.")

    assert "Programming languages" not in found
    assert "Software libraries" not in found


def test_hot_flag_still_distinguishes_the_original_list():
    skills = {s["display_name"]: s for s in extract_skills("We use Python and pandas.")}

    assert skills["Python"]["hot_technology"] is True
    assert skills["pandas"]["hot_technology"] is False


def test_extract_skills_does_not_mutate_the_shared_skill_table():
    """extract_skills used to return the module-level SKILLS dicts by reference."""
    extract_skills("Python and Postgres and Docker.")
    extract_skills("Python again.")

    for skill in SKILLS:
        assert "count" not in skill
        assert "mentions" not in skill
