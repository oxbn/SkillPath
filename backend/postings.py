import collections
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POSTINGS_DIR = BASE_DIR / "data" / "postings"

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"

# Block-level tags become newlines so that paragraph structure survives stripping. Company
# boilerplate is removed per paragraph later, which needs those breaks to be intact.
BLOCK_TAGS = re.compile(
    r"</(?:p|div|li|ul|ol|h[1-6]|tr|table|section|blockquote)>|<br\s*/?>", re.IGNORECASE
)
ANY_TAG = re.compile(r"<[^>]+>")


def strip_html(content):
    # Greenhouse escapes its HTML once, so one unescape gets back to real markup. Unescaping
    # again after the tags are gone catches entities that were escaped twice at the source
    # (&amp;nbsp; survives the first pass as &nbsp;).
    markup = html.unescape(content or "")
    text = BLOCK_TAGS.sub("\n", markup)
    text = ANY_TAG.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")

    paragraphs = (" ".join(line.split()) for line in text.split("\n"))
    return "\n".join(paragraph for paragraph in paragraphs if paragraph)


def fetch_board(board):
    """These boards are public; no auth required."""
    with urllib.request.urlopen(GREENHOUSE_URL.format(board=board), timeout=60) as response:
        jobs = json.load(response)["jobs"]

    return [
        {
            "source": "greenhouse",
            "board": board,
            "id": str(job["id"]),
            "company": job.get("company_name") or board,
            "title": (job.get("title") or "").strip(),
            "location": (job.get("location") or {}).get("name") or "",
            "url": job.get("absolute_url") or "",
            "updated_at": job.get("updated_at") or "",
            "text": strip_html(job.get("content")),
        }
        for job in jobs
    ]


def cache_path(board):
    return POSTINGS_DIR / f"{board}.json"


def cached_boards():
    if not POSTINGS_DIR.exists():
        return []

    return sorted(path.stem for path in POSTINGS_DIR.glob("*.json"))


def load_board(board, refresh=False):
    path = cache_path(board)

    if not refresh and path.exists():
        with open(path, "r", encoding="utf-8") as cache_file:
            return json.load(cache_file)["postings"]

    postings = fetch_board(board)

    POSTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as cache_file:
        json.dump(
            {
                "board": board,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "postings": postings,
            },
            cache_file,
            indent=2,
        )

    return postings


def load_postings(boards, refresh=False):
    postings = []
    for board in boards:
        postings.extend(load_board(board, refresh=refresh))

    return postings


# A company's blurb, EEO statement, and benefits list appear in every one of its postings, so
# anything they mention gets counted once per posting. Figma's own name landed in 33% of a test
# corpus this way, entirely from "Figma is growing our team…".
BOILERPLATE_THRESHOLD = 0.6

# Below this many postings, "appears in most of them" is noise rather than evidence: on a
# three-posting board a single shared sentence would already cross the threshold.
MIN_POSTINGS_FOR_STRIPPING = 5


def strip_boilerplate(postings, threshold=BOILERPLATE_THRESHOLD):
    """Drop paragraphs repeated across most of a company's postings.

    Returns new postings with the survivors in "text" and whatever was dropped in
    "boilerplate", so a suspicious result can be traced back to what stripping removed.
    """
    by_company = collections.defaultdict(list)
    for posting in postings:
        by_company[posting["company"]].append(posting)

    stripped = []
    for group in by_company.values():
        if len(group) < MIN_POSTINGS_FOR_STRIPPING:
            stripped.extend({**posting, "boilerplate": []} for posting in group)
            continue

        paragraph_counts = collections.Counter()
        for posting in group:
            paragraph_counts.update(set(posting["text"].split("\n")))

        limit = threshold * len(group)
        common = {paragraph for paragraph, n in paragraph_counts.items() if n > limit}

        for posting in group:
            paragraphs = posting["text"].split("\n")
            stripped.append(
                {
                    **posting,
                    "text": "\n".join(p for p in paragraphs if p not in common),
                    "boilerplate": [p for p in paragraphs if p in common],
                }
            )

    return stripped
