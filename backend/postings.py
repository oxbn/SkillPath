import collections
import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POSTINGS_DIR = BASE_DIR / "data" / "postings"
# Skills are extracted once at fetch time and kept here. Analysis reads only these, so it never
# has to parse the tens of megabytes of posting text sitting in POSTINGS_DIR.
INDEX_DIR = BASE_DIR / "data" / "index"
BOARDS_PATH = BASE_DIR / "data" / "boards.json"
SKILLS_PATH = BASE_DIR / "data" / "skills.json"

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"

# Public endpoints, but identifying the client is basic courtesy when fetching 30-odd boards.
USER_AGENT = "SkillPath (+https://github.com/oxbn/SkillPath)"

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


def normalize_plain_text(text):
    """Collapse whitespace per line, so plain-text sources match what strip_html produces."""
    paragraphs = (" ".join(line.split()) for line in (text or "").split("\n"))
    return "\n".join(paragraph for paragraph in paragraphs if paragraph)


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_greenhouse(board):
    """These boards are public; no auth required."""
    jobs = fetch_json(GREENHOUSE_URL.format(board=board))["jobs"]

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


def fetch_ashby(board):
    """Ashby, where a lot of companies went after leaving Greenhouse.

    It returns `descriptionPlain`, so there is no markup to strip, and it carries no company
    name — the board token stands in for one.
    """
    jobs = fetch_json(ASHBY_URL.format(board=board)).get("jobs", [])

    return [
        {
            "source": "ashby",
            "board": board,
            "id": str(job.get("id") or ""),
            "company": board,
            "title": (job.get("title") or "").strip(),
            "location": job.get("location") or "",
            "url": job.get("jobUrl") or "",
            "updated_at": job.get("publishedAt") or "",
            "text": normalize_plain_text(job.get("descriptionPlain")),
        }
        for job in jobs
        if job.get("isListed", True)
    ]


FETCHERS = {"greenhouse": fetch_greenhouse, "ashby": fetch_ashby}


def fetch_board(board, source="greenhouse"):
    if source not in FETCHERS:
        raise ValueError(f"Unknown source {source!r}; expected one of {sorted(FETCHERS)}")

    return FETCHERS[source](board)


def load_boards():
    """The committed board list. Every token in it was probed against its API before landing."""
    with open(BOARDS_PATH, "r", encoding="utf-8") as boards_file:
        return json.load(boards_file)


def cache_path(board):
    return POSTINGS_DIR / f"{board}.json"


def index_path(board):
    return INDEX_DIR / f"{board}.json"


def cached_boards():
    # The index is what analysis reads, so a board only counts as cached once it has one.
    if not INDEX_DIR.exists():
        return []

    return sorted(path.stem for path in INDEX_DIR.glob("*.json"))


@lru_cache(maxsize=1)
def vocabulary_fingerprint():
    """Identifies the skill list an index was built against.

    Precomputed skills are only valid for the vocabulary that produced them. Adding an alias
    silently invalidates every index, and stale numbers that look plausible are worse than an
    error, so the fingerprint is stored alongside and checked on load.
    """
    return hashlib.sha256(SKILLS_PATH.read_bytes()).hexdigest()[:16]


def load_board(board, refresh=False, source="greenhouse"):
    path = cache_path(board)

    if not refresh and path.exists():
        with open(path, "r", encoding="utf-8") as cache_file:
            return json.load(cache_file)["postings"]

    postings = fetch_board(board, source)

    POSTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as cache_file:
        json.dump(
            {
                "board": board,
                "source": source,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "postings": postings,
            },
            cache_file,
            indent=2,
        )

    return postings


def load_postings(boards):
    """Full posting records, text included. Only re-extraction needs these."""
    postings = []
    for board in boards:
        postings.extend(load_board(board))

    return postings


def write_index(board, records, source="greenhouse"):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(index_path(board), "w", encoding="utf-8") as index_file:
        json.dump(
            {
                "board": board,
                "source": source,
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "vocabulary": vocabulary_fingerprint(),
                "postings": records,
            },
            index_file,
        )


class StaleIndexError(RuntimeError):
    """An index was built against a different skill list than the one now on disk."""


def load_index(boards):
    """Slim per-posting records: company, title, and the skill names found in it."""
    current = vocabulary_fingerprint()
    records = []

    for board in boards:
        path = index_path(board)
        if not path.exists():
            raise StaleIndexError(
                f"No index for {board!r}. Run: python -m backend.scripts.fetch_postings"
            )

        with open(path, "r", encoding="utf-8") as index_file:
            index = json.load(index_file)

        if index.get("vocabulary") != current:
            raise StaleIndexError(
                f"Index for {board!r} was built against a different skill list. "
                f"Run: python -m backend.scripts.fetch_postings --reextract"
            )

        records.extend(index["postings"])

    return records


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
