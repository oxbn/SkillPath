"""The README quotes counts from the data files. They drifted once; this keeps them honest.

Only the vocabulary counts are checked. The corpus numbers in the headline example come from
`backend/data/postings/`, which is gitignored and may not exist at all on a fresh clone, so
they are labelled as a dated snapshot in the README instead of being asserted here.
"""

import csv

from backend.scripts.build_skills_data import (
    ALIASES_PATH,
    EXCLUDED_PATH,
    MODERN_PATH,
    RAW_PATH,
    read_json,
)
from backend.skills_extractor import SKILLS

README = RAW_PATH.parents[3] / "README.md"


def readme_text():
    return README.read_text(encoding="utf-8")


def onet_skill_count():
    """Unique O*NET tools, deduplicated the same way build_skills_data does."""
    excluded = set(read_json(EXCLUDED_PATH))

    with open(RAW_PATH, "r", newline="", encoding="utf-8") as csvfile:
        names = {
            row["Workplace Example"].strip().lower()
            for row in csv.DictReader(csvfile)
            if row["Workplace Example"].strip() not in excluded
        }

    return len(names)


def assert_quoted(text, phrase, figure):
    assert phrase in text, (
        f"README.md no longer says {phrase!r}. The {figure} changed, or the sentence was "
        f"reworded — update README.md to match the data files (or this test, if the wording "
        f"moved on)."
    )


def test_readme_quotes_the_real_vocabulary_size():
    text = readme_text()

    assert_quoted(text, f"{len(SKILLS):,} tool names", "total skill count")
    assert_quoted(text, f"{onet_skill_count():,} entries", "O*NET entry count")


def test_readme_quotes_the_real_hot_technology_count():
    hot = sum(1 for skill in SKILLS if skill["hot_technology"])

    assert_quoted(readme_text(), f'{hot} are flagged "hot technology"', "hot technology count")


def test_readme_quotes_the_real_supplementary_file_sizes():
    text = readme_text()

    assert_quoted(text, f"{len(read_json(MODERN_PATH))} hand-maintained", "modern skills count")
    assert_quoted(text, f"{len(read_json(ALIASES_PATH))} nickname mappings", "alias count")
