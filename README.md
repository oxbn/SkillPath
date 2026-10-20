# SkillPath

**Explore the technology skills mentioned in job descriptions and across a sample of employers.**

I built SkillPath to help answer which programming skills are worth learning next using job
postings as evidence. It currently extracts skills and measures their frequency across collected
postings. Comparing those results with your own skills and recommending a learning path are
not implemented yet.

SkillPath uses a local vocabulary of 8,800 tool names and aliases. Matching uses spaCy's tokenizer
and phrase matchers, with explicit rules for context and ambiguity. No generative AI service,
paid API, or API key is required. The included spaCy model is loaded locally; its tagger, parser,
and named-entity recognizer are not run during extraction.

## Capabilities

### Analyze one job description

Paste a description at `/`, pass a file to the CLI, or submit JSON to `POST /extract`.
Results include:

- Canonical skill name and category, resolving aliases such as `Postgres` to PostgreSQL.
- O*NET's hot-technology flag, occurrence count, and the wording that matched.
- Context excerpts labeled `required`, `optional`, `negated`, `incidental`, or `unknown`.
- Character offsets for the matched skill in the input text.

The web interface exposes evidence under **Matched context**. Equivalent evidence excerpts are
deduplicated without reducing occurrence counts. Long excerpts are limited to approximately
400 characters around a match. The HTTP endpoint accepts up to 50,000 characters per request.

Extraction returns matches even when their context is negated or incidental, so you can inspect
why they were found. Context labels are rules, not proof that an employer requires a skill.

### Analyze the collected market sample

The configured list contains 35 company boards: 29 Greenhouse and 6 Ashby boards. Both sources
use public endpoints without authentication. Board availability and posting counts change over time.

The market report ranks skills by **document frequency**: a posting contributes at most one
count per skill, regardless of repeated mentions. Each result reports:

| Field | Meaning |
|---|---|
| `postings` | Number of selected postings mentioning the skill after filtering |
| `share` | That number divided by all selected postings |
| `companies` | Number of distinct companies contributing those mentions |
| `company_share` | That number divided by all companies in the selected postings |

Postings without recognized skills remain in the denominator. Larger employers can dominate
posting share; company counts and company share help show how broadly a result is supported.

The market page supports:

- Case-insensitive literal title search, including names such as `C++`.
- Optional **Advanced regex** for expressions such as `engineer|data|analyst`.
- **Explicit requirements only**, which includes both required and optional skill mentions.
- The top 40 skills, with posting shares and company counts in tooltips.
- Collection details showing source, collection time, vocabulary fingerprint, and analysis version.
- Refresh progress, failed-board status, and a **Refresh now** button.

Default market reports exclude skills whose evidence is entirely negated or incidental. Unknown
mentions remain included. Requirements-only mode includes skills with at least one required or
optional context label. Both modes use the full set of selected postings as their denominator.

The sample favors technology employers using Greenhouse and Ashby. Its percentages describe
these collected postings, not the entire job market. No historical posting total or timing
measurement is presented here as a current result.

## Run with containers

The container uses Python 3.13, installs runtime dependencies, and runs as a non-root user.
A local Python environment and browser-test downloads are not needed to use it.

With Docker Engine and Compose, or Docker Desktop:

```bash
docker compose up -d --build
```

With Podman and a Compose provider:

```bash
podman compose up -d --build
```

On Fedora, install Podman and its provider with `sudo dnf install podman podman-compose`.
If Podman reports `looking up compose provider failed`, check that the provider is installed.

Open **http://localhost:8000** for single-description analysis or
**http://localhost:8000/market** for market reports. Compose binds the port to localhost.

On startup, the app checks the configured boards in the background. The first fetch may take
several minutes; single-description extraction can be used while it runs. The market page
polls refresh status and reloads the report when a refresh finishes.

The scheduler checks hourly. Raw board data older than 24 hours is fetched again, and failed
boards are retried on the next check. **Refresh now** forces a fetch. A process-local lock prevents
overlapping refreshes. Existing indexes remain available during ordinary refreshes; incompatible
indexes are rejected until rebuilt.

Postings, indexes, and refresh status persist in the named `skillpath-data` volume mounted at
`/data`. Vocabulary files remain in the image. Rebuilding the image preserves the volume.

```bash
docker compose logs -f       # follow logs; Ctrl+C stops following
docker compose down         # stop the app and keep cached data
docker compose up -d --build # restart, or rebuild after code changes
```

Use the equivalent `podman compose` commands with Podman. Adding `-v` to `compose down` deletes
the named data volume. Docker must be running for its restart policy to apply. Automatic startup
with Podman after reboot requires separate systemd/Quadlet configuration.

**Run one server process.** The scheduler, refresh lock, and report cache are in-process; multiple
Uvicorn workers or replicas are not supported by this deployment design.

## Run directly with Python

Python 3.13 is the supported target used by the container image and CI. Other Python versions
are not covered by CI. These commands assume a Unix shell and that Python 3.13 is installed.

```bash
python3.13 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

The web app starts background collection automatically. Add `--reload` for local development.
Runtime dependencies include FastAPI, Jinja2, Uvicorn, spaCy, its English model, and `regex`.
Direct dependencies are pinned; pip resolves their transitive dependencies.

By default, generated caches live under `backend/data/`. Set `SKILLPATH_CACHE_DIR` before starting
the process to store them elsewhere; this setting also applies to the CLI tools.

## Command-line tools

### Analyze one description

```bash
venv/bin/python -m backend.scripts.try_extractor job-description.txt
echo "Experience with Postgres and k8s." | venv/bin/python -m backend.scripts.try_extractor
venv/bin/python -m backend.scripts.try_extractor job-description.txt --json
```

The tool accepts a file, stdin, or a built-in sample if neither supplies text. The default table
shows skill names, categories, counts, and aliases. `--json` includes the full evidence and labels.

### Collect and analyze postings

```bash
venv/bin/python -m backend.scripts.fetch_postings
venv/bin/python -m backend.scripts.analyze_market --title engineer
venv/bin/python -m backend.scripts.analyze_market --title 'data|analyst' --regex --requirements-only
venv/bin/python -m backend.scripts.analyze_market --json
```

With no board arguments, the fetcher uses `backend/data/boards.json`; the analyzer uses every
cached index. Pass board tokens to either command to select specific boards.

| Fetch option | Behavior |
|---|---|
| `--refresh` | Fetch again even when raw postings are cached |
| `--reextract` | Rebuild indexes from cached postings, skipping boards without a raw cache |
| `--source greenhouse` or `--source ashby` | Source for tokens absent from the configured list |
| `--add TOKEN` | Probe the board and add it to the configuration if it returns postings |

For example, replace `BOARD_TOKEN` with the token from a real board URL:

```bash
venv/bin/python -m backend.scripts.fetch_postings --add BOARD_TOKEN --source ashby
```

| Analysis option | Behavior |
|---|---|
| `--title TEXT` | Case-insensitive literal title search |
| `--regex` | Interpret `--title` as a regex |
| `--requirements-only` | Count only skills labeled required or optional |
| `--limit N` | Number of rows in the text report; defaults to 30 |
| `--keep-boilerplate` | Analyze raw cached text without boilerplate stripping |
| `--json` | Emit all ranked skills, collection metadata, and filter settings |

Title filters are limited to 200 characters. Advanced regex matching has a 100ms budget across
the selected corpus. Invalid or timed-out filters fail with a clear error. The CLI treats a title
filter matching no postings as an error; the HTTP API returns an empty report instead.

`--keep-boilerplate` re-extracts skills and still applies the market context and self-reference
rules. Its JSON report has an empty `corpus` metadata list because it bypasses the indexes.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Single-description page |
| GET | `/market` | Market page |
| POST | `/extract` | Extract skills from `{"text": "..."}` |
| GET | `/api/market` | Rank skills across cached indexes |
| GET | `/api/refresh` | Read refresh state |
| POST | `/api/refresh` | Request an immediate refresh; returns HTTP 202 |

`GET /api/market` accepts `title`, `regex` (default `false`), and `requirements_only`
(default `false`). Responses include posting/company totals, board tokens, ranked skills,
per-board collection metadata, and the selected filters.

```bash
curl -X POST http://localhost:8000/extract \
  -H 'Content-Type: application/json' \
  -d '{"text":"Python required. Docker is a plus."}'

curl 'http://localhost:8000/api/market?title=engineer&requirements_only=true'
```

Market requests return HTTP 404 when no indexes are available, HTTP 409 for stale or unreadable
indexes, and HTTP 422 for invalid filters. FastAPI also returns 422 for invalid request bodies.
Refresh status includes whether a refresh is running, the last successful update when available,
and failed board tokens. Browser refresh requests with a foreign `Origin` are rejected.

Interactive API documentation is available at `/docs`. There is no authentication system; the
provided deployment is intended for personal use on localhost.

## Matching and data pipeline

```text
Greenhouse / Ashby → normalized raw cache → conservative boilerplate filtering
    → skill extraction and context labels → per-board JSON index → market aggregation
```

Greenhouse HTML is normalized to text while preserving paragraph boundaries. Ashby supplies
plain text. Each raw posting includes company, title, location, source identifiers, URL, dates,
and text. Indexes retain company, title, canonical skill names, context evidence, and an audit
of excluded paragraphs; reports read these indexes rather than re-extracting every description.

Matching and filtering use several safeguards:

- Per-pattern case sensitivity reduces collisions such as the verb “excel” and Microsoft Excel.
- Longest overlapping spans win, so Microsoft SQL Server does not also produce its nested SQL match.
- Common document references such as “Section C” and “see R” are suppressed, while terminal
  punctuation in language names such as “R.” is handled explicitly.
- Boilerplate removal requires at least five postings for a company. A paragraph must appear in
  more than 60% of its postings and be classified as incidental company text. Recognized section
  headings, requirement cues, required/optional sections, and unclassified text survive.
- Company-name matches are treated as possible self-references. Required or optional evidence
  preserves legitimate requirements for an employer's own product.

JSON writes use atomic replacement. The index fingerprint incorporates the vocabulary and
analysis version. Vocabulary or version changes invalidate previous indexes. The web refresher
rebuilds stale or malformed indexes from cached descriptions, fetching boards when due.
Reports are memoized using index modification times to invalidate cached results.

## Vocabulary

`backend/data/skills.json` is generated from the sources below. Of its skills, 176 are flagged "hot technology";
this is an O*NET attribute, not a demand score calculated from the collected postings.

| Source under `backend/data/` | Purpose |
|---|---|
| `raw/software_skills.csv` | 8,744 entries after deduplication and exclusions from the O*NET software data |
| `modern_skills.json` | 58 hand-maintained entries for tooling missing from the source taxonomy |
| `aliases.json` | 84 nickname mappings from canonical skill keys to alternative spellings |
| `ambiguous_names.json` | Names requiring exact capitalization |
| `excluded_names.json` | Generic category names excluded from matching |

The generated vocabulary contains 8,911 patterns across 134 categories, including 164
case-sensitive patterns. `raw/essential_skills.csv` is included as source data but is not used
by the current builder or runtime.

After editing vocabulary sources:

```bash
venv/bin/python -m backend.scripts.build_skills_data
venv/bin/python -m backend.scripts.fetch_postings --reextract
```

The builder rejects aliases targeting unknown skills. The running web app loads the vocabulary
at import time, so restart it after rebuilding. Its background refresh can rebuild indexes on
startup instead of running the second command manually.

## Project structure

```text
app.py                          FastAPI routes, response models, lifespan, report cache
backend/
  skills_extractor.py           Tokenization, phrase matching, mentions, evidence
  context.py                    Section and sentence rules for context classification
  market.py                     Document/company frequency and self-reference filtering
  postings.py                   Fetch adapters, normalization, caches, indexes, boilerplate
  refresh.py                    Background scheduler, refresh locking and status
  scripts/
    try_extractor.py            Single-description CLI
    fetch_postings.py           Board collection, index building, board validation
    analyze_market.py           Market report CLI
    build_skills_data.py        Vocabulary generation
  data/                         Vocabulary sources and configured boards
templates/                      Shared layout and two pages with page-specific JavaScript
static/                         Shared JavaScript helpers and responsive light/dark CSS
tests/                          Unit, API, fixture-based, and browser checks
.github/workflows/test.yml      Python 3.13 test workflow
Dockerfile / compose.yaml       Local container deployment and persistent data volume
```

The web app and CLI share the analysis modules. The frontend uses vanilla JavaScript and
Jinja2 templates, without a frontend framework or build step. Theme choice persists in local
storage and is applied before first paint. Results use text nodes rather than inserting
job-description HTML, and styling supports narrow screens and reduced motion.

## Development and tests

Install development dependencies in addition to the runtime packages:

```bash
venv/bin/python -m pip install -r requirements-dev.txt
venv/bin/python -m pytest
```

The default suite excludes browser tests. It covers matching regressions, labeled context
examples, source normalization, raw/index report parity, document frequency, cache invalidation,
refresh behavior, API validation, and vocabulary counts quoted in this README.

`tests/fixtures/context_cases.json` is a small labeled regression set, not an independent accuracy
benchmark. `tests/fixtures/corpus.json` provides a fixed offline corpus with expected results.
Tests use fixtures and temporary caches rather than live job-board requests.

Browser smoke tests are optional and require a separate Chromium download. They exercise
extraction, evidence display, filtering errors, refresh completion, and theme persistence against
an isolated local fixture server. To keep the browser download temporary:

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/skillpath-browsers venv/bin/python -m playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/tmp/skillpath-browsers venv/bin/python -m pytest -m browser
rm -rf -- /tmp/skillpath-browsers
```

These commands download Playwright's browser binaries into the specified directory, without
installing a system browser. The final command removes those downloads; Playwright's Python
package and the reusable tests remain in the project environment. Some Linux systems also
need browser system libraries. CI installs these with Playwright's `--with-deps` option and
runs both the default suite and the browser test on Python 3.13.

## Limitations and next steps

- Context classification is heuristic. Complex negation, unusual headings, incidental uses of
  product names, and ambiguous single letters can still be mislabeled. Unknown mentions are
  retained in the default report so the stricter mode does not silently define all results.
- Matching covers named technologies in the vocabulary, not general abilities or complete
  job requirements. New tools and aliases need maintenance; O*NET names can lag industry usage.
- Boilerplate and self-reference rules trade false positives for false negatives. Evidence and
  exclusion records help inspection, but the small fixture set does not establish real-world accuracy.
- The selected employers are not a random or geographically representative sample. Expanding
  sources and reviewing a broader employer mix remain future work.
- Tool-free postings still count in the denominator. A small share does not necessarily mean
  a skill is unimportant, and company share is not a statistically weighted market estimate.
- The app keeps the latest per-board cache rather than historical snapshots. Collection dates
  and version metadata explain a report's inputs but do not preserve past live-board content.
- Multi-process refresh coordination, authentication, user profiles, personal skill-gap analysis,
  and learning recommendations are not implemented.

## License

Apache License 2.0. See [LICENSE](LICENSE).
