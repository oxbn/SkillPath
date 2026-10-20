import json
import re

import spacy
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span
from spacy.symbols import ORTH
from spacy.util import filter_spans
from pathlib import Path
from backend.context import TextContext

BASE_DIR = Path(__file__).resolve().parent
SKILLS_PATH = BASE_DIR / "data" / "skills.json"

nlp = spacy.load("en_core_web_sm")
# English tokenization treats a terminal R. as an initial; job ads also end sentences
# with the language name. Keep the punctuation separate so the vocabulary can match it.
for language in ("C", "R"):
    nlp.tokenizer.add_special_case(language + ".", [{ORTH: language}, {ORTH: "."}])

with open(SKILLS_PATH, "r", encoding="utf-8") as skills_file:
    SKILLS = json.load(skills_file)

# Most surface forms match case-insensitively. Ones that collide with ordinary words ("Go",
# "bootstrap", the alias "Excel") go to a second matcher that respects the original casing.
# The choice is per pattern, not per skill: "Microsoft Excel" is safe folded, "Excel" is not.
skill_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
cased_skill_matcher = PhraseMatcher(nlp.vocab, attr="ORTH")

skills_by_match_id = {}
# Lets a precomputed skill name from the index be resolved back to its display name and
# category without re-running the matcher.
SKILLS_BY_NAME = {}

for skill in SKILLS:
    match_id = nlp.vocab.strings[skill["name"]]

    for pattern in skill["patterns"]:
        matcher = cased_skill_matcher if pattern["case_sensitive"] else skill_matcher
        matcher.add(skill["name"], [nlp.make_doc(pattern["text"])])

    skills_by_match_id[match_id] = skill
    SKILLS_BY_NAME[skill["name"]] = skill


def extract_skills(job_text):
    # make_doc runs the tokenizer only; PhraseMatcher never needs the tagger or parser.
    doc = nlp.make_doc(job_text)
    context = TextContext(job_text)
    matches = [*skill_matcher(doc), *cased_skill_matcher(doc)]

    # Overlapping matches are resolved longest-first, so "Microsoft SQL Server" wins over
    # the bare "SQL" inside it, and "C++" wins over the "C" its first token would match.
    spans = [Span(doc, start, end, label=match_id) for match_id, start, end in matches]

    # Fresh dicts, never the SKILLS entries themselves: those are module-level and shared, so
    # annotating them would leak one document's counts into every later call.
    matched_skills = {}
    evidence_seen = {}
    for span in filter_spans(spans):
        skill = skills_by_match_id[span.label]
        evidence = context.evidence(span.start_char, span.end_char)
        if span.text in {"C", "R"} and re.search(
            r"\b(?:section|appendix|figure|option|grade|vitamin|see)\s+$",
            job_text[max(0, span.start_char - 30):span.start_char], re.I,
        ):
            continue
        match = matched_skills.get(skill["name"])

        if match is None:
            match = {
                "name": skill["name"],
                "display_name": skill["display_name"],
                "category": skill["category"],
                "hot_technology": skill["hot_technology"],
                "mentions": [],
                "count": 0,
                "evidence": [],
            }
            matched_skills[skill["name"]] = match
            evidence_seen[skill["name"]] = set()

        match["count"] += 1
        evidence_key = (evidence["text"], evidence["classification"])
        if evidence_key not in evidence_seen[skill["name"]]:
            evidence_seen[skill["name"]].add(evidence_key)
            match["evidence"].append(evidence)
        # Folding here keeps ["Python", "python"] from reading as two different ways the
        # skill was written.
        if span.text.lower() not in [mention.lower() for mention in match["mentions"]]:
            match["mentions"].append(span.text)

    return sorted(
        matched_skills.values(),
        key=lambda skill: (-skill["count"], skill["display_name"]),
    )
