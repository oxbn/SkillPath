import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
RAW_PATH = DATA_DIR / "raw" / "software_skills.csv"
ALIASES_PATH = DATA_DIR / "aliases.json"
AMBIGUOUS_PATH = DATA_DIR / "ambiguous_names.json"
EXCLUDED_PATH = DATA_DIR / "excluded_names.json"
MODERN_PATH = DATA_DIR / "modern_skills.json"
OUT_PATH = DATA_DIR / "skills.json"


def read_json(path):
    with open(path, "r", encoding="utf-8") as json_file:
        return json.load(json_file)


def normalize_alias(alias):
    """Aliases are plain strings, or objects when they need to opt into case sensitivity."""
    if isinstance(alias, str):
        return {"text": alias, "case_sensitive": False}

    return {"text": alias["text"], "case_sensitive": bool(alias.get("case_sensitive"))}


def build_skills():
    # Names that are also ordinary English words. Folding case on these turns "we will go over
    # it" into Go and "everyone can excel" into Microsoft Excel, so they match on exact casing
    # instead. Derived by intersecting single-token skill names with a system dictionary; see
    # ambiguous_names.json. Losing lowercase spellings of products costs almost nothing —
    # postings capitalize product names roughly 99% of the time.
    ambiguous = set(read_json(AMBIGUOUS_PATH))

    # O*NET includes rows for whole categories, not products. "Programming languages" would
    # match any posting that uses the phrase, which is noise rather than a skill.
    excluded = set(read_json(EXCLUDED_PATH))

    skills_by_key = {}

    with open(RAW_PATH, "r", newline="", encoding="utf-8") as csvfile:
        for row in csv.DictReader(csvfile):
            display_name = row["Workplace Example"].strip()
            if display_name in excluded:
                continue

            key = display_name.lower()
            skills_by_key[key] = {
                "name": key,
                "display_name": display_name,
                "category": row["Element Name"].strip(),
                "hot_technology": row["Hot Technology"] == "Y",
                "patterns": [{"text": display_name, "case_sensitive": key in ambiguous}],
            }

    # O*NET lags the industry by years: Rust, Next.js, dbt and FastAPI are absent from it at
    # any filter level, so they are maintained separately.
    for skill in read_json(MODERN_PATH):
        display_name = skill["display_name"]
        key = display_name.lower()
        skills_by_key.setdefault(
            key,
            {
                "name": key,
                "display_name": display_name,
                "category": skill["category"],
                "hot_technology": False,
                "patterns": [{"text": display_name, "case_sensitive": key in ambiguous}],
            },
        )
        skills_by_key[key]["patterns"].extend(
            {"text": alias, "case_sensitive": alias.lower() in ambiguous}
            for alias in skill.get("aliases", [])
        )

    aliases = read_json(ALIASES_PATH)
    unknown = sorted(set(aliases) - set(skills_by_key))
    if unknown:
        raise ValueError(
            f"{ALIASES_PATH.name} has keys that are not skill names: {', '.join(unknown)}"
        )

    for key, skill_aliases in aliases.items():
        skills_by_key[key]["patterns"].extend(normalize_alias(a) for a in skill_aliases)

    return sorted(skills_by_key.values(), key=lambda skill: skill["name"])


def main():
    skills = build_skills()

    with open(OUT_PATH, "w", encoding="utf-8") as outfile:
        json.dump(skills, outfile, indent=2)

    hot = sum(1 for skill in skills if skill["hot_technology"])
    cased = sum(1 for s in skills for p in s["patterns"] if p["case_sensitive"])
    print(f"Wrote {len(skills)} skills ({hot} hot, {cased} case-sensitive patterns) to {OUT_PATH}")


if __name__ == "__main__":
    main()
