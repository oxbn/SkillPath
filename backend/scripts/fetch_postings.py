import argparse
import json
import sys
import time
import urllib.error

from backend.postings import (
    BOARDS_PATH,
    FETCHERS,
    INDEX_DIR,
    cache_path,
    fetch_board,
    load_board,
    load_boards,
    strip_boilerplate,
    write_index,
)
from backend.skills_extractor import extract_skills

# Thirty-odd boards in a row is enough to be worth pacing, even against public endpoints.
DELAY_SECONDS = 0.35


def build_index(board, source, postings):
    """Strip boilerplate, extract skills, and write the slim index analysis actually reads.

    Extraction happens here, once per fetch, rather than on every request. It has to run after
    boilerplate stripping, and stripping needs a company's whole posting set — which is exactly
    what we have at this point.
    """
    stripped = strip_boilerplate(postings)
    records = []
    for posting in stripped:
        skills = extract_skills(posting["text"])
        records.append({
            "company": posting["company"],
            "title": posting["title"],
            "skills": [skill["name"] for skill in skills],
            "skill_context": {skill["name"]: skill["evidence"] for skill in skills},
            "excluded_paragraphs": posting["boilerplate"],
            "exclusion_rule": posting.get("boilerplate_reason"),
        })

    write_index(board, records, source)
    return records


def describe(board, postings, records):
    skills = sum(len(record["skills"]) for record in records)
    average = skills // len(records) if records else 0
    print(f"  {board:<16} {len(postings):>5} postings  {average:>3} skills each")


def resolve(tokens, default_source):
    """Pair each requested token with its source, preferring what the board list already says."""
    known = {board["token"]: board["source"] for board in load_boards()}

    if not tokens:
        return list(known.items())

    return [(token, known.get(token, default_source)) for token in tokens]


def add_board(token, source):
    """Probe a token before committing it — roughly 40% of plausible names are dead."""
    try:
        postings = fetch_board(token, source)
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except urllib.error.URLError as error:
        return str(error.reason)

    if not postings:
        return "returned no postings"

    boards = load_boards()
    if any(board["token"] == token for board in boards):
        print(f"{token} is already in the list")
        return None

    boards.append({"token": token, "source": source})
    boards.sort(key=lambda board: (board["source"], board["token"]))
    with open(BOARDS_PATH, "w", encoding="utf-8") as boards_file:
        json.dump(boards, boards_file, indent=2)
        boards_file.write("\n")

    print(f"Added {token} ({source}, {len(postings)} postings) to {BOARDS_PATH.name}")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch job postings and precompute the skills in them."
    )
    parser.add_argument(
        "boards",
        nargs="*",
        help="board tokens to fetch. Defaults to every board in data/boards.json.",
    )
    parser.add_argument(
        "--source",
        choices=sorted(FETCHERS),
        default="greenhouse",
        help="source for tokens that are not already in the board list",
    )
    parser.add_argument("--refresh", action="store_true", help="refetch even when cached")
    parser.add_argument(
        "--reextract",
        action="store_true",
        help="rebuild indexes from cached postings, without refetching. Use after editing the "
        "skill list, which invalidates every precomputed index.",
    )
    parser.add_argument(
        "--add",
        metavar="TOKEN",
        help="validate a token against its API and append it to the board list",
    )
    args = parser.parse_args()

    if args.add:
        failure = add_board(args.add, args.source)
        if failure:
            parser.error(f"{args.add} is not a live {args.source} board: {failure}")
        return 0

    failed = []
    for index, (board, source) in enumerate(resolve(args.boards, args.source)):
        if args.reextract and not cache_path(board).exists():
            continue

        try:
            postings = load_board(board, refresh=args.refresh, source=source)
        except urllib.error.HTTPError as error:
            failed.append(board)
            print(f"  {board:<16} failed: HTTP {error.code} (is the board token right?)")
            continue
        except urllib.error.URLError as error:
            failed.append(board)
            print(f"  {board:<16} failed: {error.reason}")
            continue

        describe(board, postings, build_index(board, source, postings))

        # Only pace the network; re-extraction is local and has nothing to be polite to.
        if not args.reextract and index:
            time.sleep(DELAY_SECONDS)

    print(f"\nIndexed in {INDEX_DIR}")

    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
