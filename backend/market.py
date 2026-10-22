import collections
import re

from backend.skills_extractor import SKILLS_BY_NAME, extract_skills

# Words that name a legal entity rather than the company, and would match far too much.
COMPANY_STOPWORDS = {
    "inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "the",
    "labs", "lab", "technologies", "technology", "tech", "software", "systems", "group",
    "holdings", "solutions", "services", "io", "ai", "com",
}


def company_tokens(company):
    words = (word.strip(",.()&").lower() for word in company.split())
    return {word for word in words if len(word) > 2 and word not in COMPANY_STOPWORDS}


def is_self_reference(skill, company):
    """A company naming itself in its own posting is not a job requirement.

    Boilerplate stripping removes the repeated blurb, but the per-posting prose still says it.

    Matching at a word boundary rather than by equality is what catches the multi-word cases —
    Elastic/"elasticsearch", Amazon/"amazon web services aws software". The boundary is what
    keeps it safe: a plain substring test would suppress Dropbox for a company named Box.
    """
    name = skill["name"]

    return any(re.search(rf"\b{re.escape(token)}", name) for token in company_tokens(company))


def posting_skills(posting):
    """Precomputed skill names when the index supplied them, otherwise extract on the spot.

    The fallback is what keeps --keep-boilerplate and the existing tests working on raw
    posting dicts that have text but no precomputed skills.
    """
    names = posting.get("skills")
    if names is None:
        return extract_skills(posting["text"])

    return [SKILLS_BY_NAME[name] for name in dict.fromkeys(names) if name in SKILLS_BY_NAME]


def analyze(postings, requirements_only=False):
    """Rank skills by how many postings mention them at all.

    Document frequency, not total mentions: one posting saying "Python" six times must not
    outweigh six postings saying it once.
    """
    seen_postings = collections.Counter()
    seen_companies = collections.defaultdict(set)
    skills_by_name = {}
    company_postings = collections.Counter(p.get("company", "") for p in postings)
    skill_titles = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))

    for posting in postings:
        company = posting.get("company", "")

        for skill in posting_skills(posting):
            evidence = posting.get("skill_context", {}).get(skill["name"], skill.get("evidence", []))
            labels = {item["classification"] for item in evidence}
            explicit = bool(labels & {"required", "optional"})
            if requirements_only and not explicit:
                continue
            if labels and labels <= {"negated", "incidental"}:
                continue
            if is_self_reference(skill, company) and not explicit:
                continue

            skills_by_name.setdefault(skill["name"], skill)
            seen_postings[skill["name"]] += 1
            seen_companies[skill["name"]].add(company)
            skill_titles[skill["name"]][company][posting.get("title", "Untitled role")] += 1

    total = len(postings)
    total_companies = len({posting.get("company", "") for posting in postings})
    ranked = [
        {
            "name": name,
            "display_name": skills_by_name[name]["display_name"],
            "category": skills_by_name[name]["category"],
            "postings": count,
            "share": count / total if total else 0.0,
            "companies": len(seen_companies[name]),
            "company_share": len(seen_companies[name]) / total_companies if total_companies else 0.0,
            "breakdown": [
                {"name": company, "postings": sum(titles.values()),
                 "titles": [{"title": title, "postings": count}
                            for title, count in sorted(titles.items(), key=lambda item: (-item[1], item[0]))]}
                for company, titles in sorted(skill_titles[name].items(),
                                              key=lambda item: (-sum(item[1].values()), item[0]))
            ],
        }
        for name, count in seen_postings.items()
    ]
    ranked.sort(key=lambda skill: (-skill["postings"], skill["display_name"]))

    return {
        "postings": total,
        "companies": total_companies,
        "skills": ranked,
        "company_breakdown": [{"name": name, "postings": count}
                              for name, count in sorted(company_postings.items(), key=lambda item: (-item[1], item[0]))],
    }
