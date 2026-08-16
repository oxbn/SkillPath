import argparse
import json
import re
import sys

from backend.market import analyze
from backend.postings import StaleIndexError, cached_boards, load_index, load_postings


def print_report(report, limit):
    print(
        f"{report['postings']} postings from {report['companies']} "
        f"{'company' if report['companies'] == 1 else 'companies'}\n"
    )

    skills = report["skills"][:limit]
    if not skills:
        print("No skills matched.")
        return

    width = max(len(skill["display_name"]) for skill in skills)
    print(f"  {'SKILL':<{width}}  SHARE  POSTINGS  COMPANIES")
    for skill in skills:
        print(
            f"  {skill['display_name']:<{width}}  {skill['share']:>4.0%}  "
            f"{skill['postings']:>8}  {skill['companies']:>9}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Report which skills a market of job postings asks for."
    )
    parser.add_argument(
        "boards",
        nargs="*",
        help="cached Greenhouse board tokens to analyze. Defaults to everything cached.",
    )
    parser.add_argument(
        "--title",
        help="only include postings whose title matches this (case-insensitive regex)",
    )
    parser.add_argument("--limit", type=int, default=30, help="how many skills to show")
    parser.add_argument(
        "--keep-boilerplate",
        action="store_true",
        help="skip boilerplate stripping, to check whether it removed something real",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    boards = args.boards or cached_boards()
    if not boards:
        parser.error("nothing cached yet — run backend.scripts.fetch_postings first")

    # The index already has boilerplate stripped and skills extracted, so it is both the fast
    # path and the normal one. --keep-boilerplate exists to check that stripping didn't remove
    # something real, which means going back to the raw text and re-extracting.
    try:
        postings = load_postings(boards) if args.keep_boilerplate else load_index(boards)
    except StaleIndexError as error:
        parser.error(str(error))

    if args.title:
        pattern = re.compile(args.title, re.IGNORECASE)
        postings = [p for p in postings if pattern.search(p["title"])]
        if not postings:
            parser.error(f"no posting titles matched {args.title!r}")

    report = analyze(postings)

    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print_report(report, args.limit)


if __name__ == "__main__":
    main()
