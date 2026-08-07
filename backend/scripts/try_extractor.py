import argparse
import json
import sys

from backend.skills_extractor import extract_skills

SAMPLE_JOB_TEXT = """
Data Analyst - Remote

We are looking for a data analyst to join our reporting team.

Responsibilities:
- Build and maintain dashboards in Tableau for the leadership team
- Write queries against PostgreSQL and Microsoft SQL Server
- Automate recurring reports with Python
- Keep the finance team's Microsoft Excel models up to date

Requirements:
- 3+ years of experience in analytics or business intelligence
- Comfortable with Git and reviewing pull requests on GitHub
- Familiarity with Docker and Linux is a plus
- Experience with Postgres tuning, JS charting libraries, or Excel macros welcome
- Strong communication skills and attention to detail
"""


def read_job_text(path):
    if path:
        with open(path, "r", encoding="utf-8") as job_file:
            return job_file.read()

    if not sys.stdin.isatty():
        piped_text = sys.stdin.read()
        if piped_text.strip():
            return piped_text

    return SAMPLE_JOB_TEXT


def print_skills(skills):
    if not skills:
        print("No skills matched.")
        return

    print(f"Matched {len(skills)} skills:")

    width = max(len(skill["display_name"]) for skill in skills)
    for skill in skills:
        # Only worth showing when the text said something other than the canonical name.
        via = [m for m in skill["mentions"] if m.lower() != skill["display_name"].lower()]
        detail = f" via {', '.join(repr(m) for m in via)}" if via else ""
        repeats = f" x{skill['count']}" if skill["count"] > 1 else ""
        print(f"  {skill['display_name']:<{width}}{repeats}{detail}  ({skill['category']})")


def main():
    parser = argparse.ArgumentParser(
        description="Run the skills extractor over a job description."
    )
    parser.add_argument(
        "job_file",
        nargs="?",
        help="path to a job description; reads stdin, or a built-in sample, if omitted",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print the raw extract_skills() output instead of a table",
    )
    args = parser.parse_args()

    job_text = read_job_text(args.job_file)
    skills = extract_skills(job_text)

    if args.as_json:
        json.dump(skills, sys.stdout, indent=2)
        print()
    else:
        print_skills(skills)


if __name__ == "__main__":
    main()
