import json

import spacy
from spacy.matcher import PhraseMatcher
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SKILLS_PATH = BASE_DIR / "data" / "skills.json"

nlp = spacy.load("en_core_web_sm")

with open(SKILLS_PATH, "r", encoding="utf-8") as skills_file:
    SKILLS = json.load(skills_file)

skill_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
skills_by_match_id = {}
for skill in SKILLS:
    match_id = nlp.vocab.strings[skill["name"]]
    skill_matcher.add(skill["name"], [nlp.make_doc(skill["name"])])
    skills_by_match_id[match_id] = skill


def extract_skills(job_text):
    doc = nlp(job_text)
    matches = skill_matcher(doc)

    matched_skills = {}
    for match_id, start, end in matches:
        skill = skills_by_match_id[match_id]
        matched_skills[skill["name"]] = skill

    return list(matched_skills.values())
