import collections

from backend.skills_extractor import extract_skills


def is_self_reference(skill, company):
    """A company naming itself in its own posting is not a job requirement.

    Figma's postings mention Figma constantly, which put it in 33% of a test corpus purely
    from its own marketing copy. Boilerplate stripping removes the repeated blurb, but the
    per-posting prose still says it.
    """
    company_words = {word.strip(",.").lower() for word in company.split()}
    return skill["name"] == company.lower() or skill["name"] in company_words


def analyze(postings):
    """Rank skills by how many postings mention them at all.

    Document frequency, not total mentions: one posting saying "Python" six times must not
    outweigh six postings saying it once.
    """
    seen_postings = collections.Counter()
    seen_companies = collections.defaultdict(set)
    skills_by_name = {}

    for posting in postings:
        company = posting.get("company", "")

        for skill in extract_skills(posting["text"]):
            if is_self_reference(skill, company):
                continue

            skills_by_name.setdefault(skill["name"], skill)
            seen_postings[skill["name"]] += 1
            seen_companies[skill["name"]].add(company)

    total = len(postings)
    ranked = [
        {
            "name": name,
            "display_name": skills_by_name[name]["display_name"],
            "category": skills_by_name[name]["category"],
            "postings": count,
            "share": count / total if total else 0.0,
            "companies": len(seen_companies[name]),
        }
        for name, count in seen_postings.items()
    ]
    ranked.sort(key=lambda skill: (-skill["postings"], skill["display_name"]))

    return {
        "postings": total,
        "companies": len({posting.get("company", "") for posting in postings}),
        "skills": ranked,
    }
