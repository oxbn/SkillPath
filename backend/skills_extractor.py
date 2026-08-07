import json

import spacy
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span
from spacy.util import filter_spans
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SKILLS_PATH = BASE_DIR / "data" / "skills.json"

nlp = spacy.load("en_core_web_sm")

with open(SKILLS_PATH, "r", encoding="utf-8") as skills_file:
    SKILLS = json.load(skills_file)

# Most surface forms match case-insensitively. Ones that collide with ordinary words ("Go",
# "bootstrap", the alias "Excel") go to a second matcher that respects the original casing.
# The choice is per pattern, not per skill: "Microsoft Excel" is safe folded, "Excel" is not.
skill_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
cased_skill_matcher = PhraseMatcher(nlp.vocab, attr="ORTH")

skills_by_match_id = {}
for skill in SKILLS:
    match_id = nlp.vocab.strings[skill["name"]]

    for pattern in skill["patterns"]:
        matcher = cased_skill_matcher if pattern["case_sensitive"] else skill_matcher
        matcher.add(skill["name"], [nlp.make_doc(pattern["text"])])

    skills_by_match_id[match_id] = skill


def extract_skills(job_text):
    # make_doc runs the tokenizer only; PhraseMatcher never needs the tagger or parser.
    doc = nlp.make_doc(job_text)
    matches = [*skill_matcher(doc), *cased_skill_matcher(doc)]

    # Overlapping matches are resolved longest-first, so "Microsoft SQL Server" wins over
    # the bare "SQL" inside it, and "C++" wins over the "C" its first token would match.
    spans = [Span(doc, start, end, label=match_id) for match_id, start, end in matches]

    # Fresh dicts, never the SKILLS entries themselves: those are module-level and shared, so
    # annotating them would leak one document's counts into every later call.
    matched_skills = {}
    for span in filter_spans(spans):
        skill = skills_by_match_id[span.label]
        match = matched_skills.get(skill["name"])

        if match is None:
            match = {
                "name": skill["name"],
                "display_name": skill["display_name"],
                "category": skill["category"],
                "hot_technology": skill["hot_technology"],
                "mentions": [],
                "count": 0,
            }
            matched_skills[skill["name"]] = match

        match["count"] += 1
        # Distinct surface forms, first-seen casing. Folding here keeps ["Python", "python"]
        # from reading as two different ways the skill was written.
        if span.text.lower() not in [mention.lower() for mention in match["mentions"]]:
            match["mentions"].append(span.text)

    return sorted(
        matched_skills.values(),
        key=lambda skill: (-skill["count"], skill["display_name"]),
    )
