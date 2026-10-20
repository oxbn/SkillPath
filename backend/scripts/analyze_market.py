import argparse
import json
import sys

from backend.market import analyze
from backend.postings import StaleIndexError, cached_boards, load_index, load_postings
from backend.title_filter import TitleFilterError, filter_titles


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
        help="only include titles containing this text (case-insensitive)",
    )
    parser.add_argument("--regex", action="store_true", help="interpret --title as a bounded regex")
    parser.add_argument("--requirements-only", action="store_true", help="count only explicit required/optional skills")
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
        if args.keep_boilerplate:
            postings, metadata = load_postings(boards), []
        else:
            postings, metadata = load_index(boards, include_metadata=True)
    except StaleIndexError as error:
        parser.error(str(error))

    if args.title:
        try:
            postings = filter_titles(postings, args.title, args.regex)
        except TitleFilterError as error:
            parser.error(str(error))
        if not postings:
            parser.error(f"no posting titles matched {args.title!r}")

    report = analyze(postings, args.requirements_only)
    report.update(corpus=metadata, title=args.title, regex=args.regex,
                  requirements_only=args.requirements_only, keep_boilerplate=args.keep_boilerplate)

    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print_report(report, args.limit)


if __name__ == "__main__":
    main()
