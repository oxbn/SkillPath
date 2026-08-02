import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RAW_PATH = SCRIPT_DIR.parent / "data" / "raw" / "software_skills.csv"
OUT_PATH = SCRIPT_DIR.parent / "data" / "skills.json"

def build_skills():
    skills_by_key = {}

    with open(RAW_PATH, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["Hot Technology"] != "Y":
                continue

            display_name = row["Workplace Example"].strip()
            key = display_name.lower()

            skills_by_key[key] = {
                "name": key,
                "display_name": display_name,
                "category": row["Element Name"].strip(),
                "hot_technology": row["Hot Technology"] == "Y",
            }

    return sorted(skills_by_key.values(), key=lambda skill: skill["name"])


def main():
    skills = build_skills()

    with open(OUT_PATH, "w", encoding="utf-8") as outfile:
        json.dump(skills, outfile, indent=2)

    print(f"Wrote {len(skills)} skills to {OUT_PATH}")


if __name__ == "__main__":
    main()
