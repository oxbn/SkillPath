import argparse
import sys
import urllib.error

from backend.postings import cache_path, cached_boards, load_board


def describe(board, postings):
    total_chars = sum(len(posting["text"]) for posting in postings)
    average = total_chars // len(postings) if postings else 0
    print(f"  {board:<16} {len(postings):>5} postings  avg {average:>6} chars")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and cache job postings from public Greenhouse boards."
    )
    parser.add_argument(
        "boards",
        nargs="*",
        help="Greenhouse board tokens, e.g. stripe databricks. Defaults to what is cached.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="refetch even when a cached copy exists",
    )
    args = parser.parse_args()

    boards = args.boards or cached_boards()
    if not boards:
        parser.error("no boards given and nothing cached yet — pass a board token to start")

    failed = []
    for board in boards:
        try:
            postings = load_board(board, refresh=args.refresh)
        except urllib.error.HTTPError as error:
            failed.append(board)
            print(f"  {board:<16} failed: HTTP {error.code} (is the board token right?)")
            continue
        except urllib.error.URLError as error:
            failed.append(board)
            print(f"  {board:<16} failed: {error.reason}")
            continue

        describe(board, postings)

    print(f"\nCached in {cache_path('').parent}")

    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
