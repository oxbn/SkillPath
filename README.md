# SkillPath

**Counting which skills employers actually ask for, across hundreds of job postings at once.**

## Why I built it

I wanted to know which programming skills were actually worth learning next.

The advice available online is mostly assertion — listicles, opinion threads, and surveys with a
few hundred self-selected respondents. Meanwhile the primary source is sitting in the open:
every company publishes its job openings, and those openings say exactly what that company is
willing to pay for. Reading one is easy. The problem is that one job ad tells you nothing about
a *market*, and nobody reads 1,500 of them.

So I built something that would.

## What it does

**Analyze a market.** It fetches every open posting from 35 company job boards across Greenhouse
and Ashby, reduces them to plain text, and ranks skills by how many postings mention each one.
The output gives each skill's share of the corpus, its raw posting count, and how many distinct
companies asked for it. A regular expression on job titles narrows the corpus to a slice of the
market — `engineer|data|analyst` — and re-ranks on just those roles in about 40ms.

```
7533 postings from 35 companies

  SKILL                             SHARE  POSTINGS  COMPANIES
  Python                             22%      1691         35
  Amazon Web Services AWS software   15%      1106         33
  Structured query language SQL      14%      1086         34
  Go                                 12%       921         32
  Salesforce software                10%       746         33
  Microsoft Azure software           10%       735         26
```

*Snapshot: 35 boards, fetched 2026-08-16. These boards change daily, so your own numbers will
differ.*

The company count is the column that matters. Every skill above is asked for by at least 26 of
the 35 companies, which is what separates a market signal from one employer's stack — on a
three-company corpus the same table put Scala at 18% and Apache Spark at 20%, and both were
really just Databricks.

**Analyze a single posting.** Paste a job description into the web interface, or pipe it to the
CLI, and it returns every tool the text mentions along with the exact substring that triggered
each match. If a posting says "Postgres," the result reads *PostgreSQL, via 'Postgres'*. You can
always see why something matched rather than trusting the output.

Both modes are also available as JSON over HTTP.

No AI model and no API keys. It matches against a vocabulary of ~8,800 tool names and their
nicknames, which is why it's fast enough to run over thousands of documents for free.

## The problem that turned out to be the real one

My first working version told me that 36% of postings required Microsoft Excel.

They didn't. It was matching the sentence *"a culture where everyone can excel."*

Once I started looking, the same class of error was everywhere. Every one of these was a real
false positive found in real postings:

| Text | Wrongly matched |
|---|---|
| "we will **go** over it" | Go |
| "a culture where everyone can **excel**" | Microsoft Excel — 36% of one corpus |
| "equipping AEs and **SAs**" | SAS |
| "cheaper than **SWIFT**" | Swift |
| "you will **bootstrap** projects" | Bootstrap |
| Figma's own name in Figma's job ads | Figma — 33% of one corpus |

Every one of them would have produced a confident, wrong, professional-looking number.

Finding skill names is the easy half of this problem. Rejecting the things that only *look* like
skill names is the half that decides whether the output means anything. It took four separate
mechanisms:

**1. Per-pattern case sensitivity.** Names that collide with ordinary English words match only
when capitalized. Crucially the decision is per *pattern*, not per skill: "Microsoft Excel" is
safe to match case-insensitively, but the bare alias "Excel" is not. I derived the ambiguous set
by intersecting single-token skill names against a system dictionary, which produced 164
case-sensitive patterns and is committed as `backend/data/ambiguous_names.json`. Job postings
capitalize product names roughly 99% of the time, so the recall this costs is close to nothing.

**2. Longest-match-wins.** Overlapping matches resolve to the longest span, so "Microsoft SQL
Server" beats the bare "SQL" inside it, and "C++" beats the "C" that its first token would
otherwise match on its own.

**3. Boilerplate stripping.** A company's blurb, EEO statement, and benefits list appear in
*every* one of its postings, so anything they mention gets counted once per posting — which is
how Figma reached 33%. Paragraphs appearing in more than 60% of a single company's postings are
dropped. On my corpus that removes 24% of the text. A minimum-postings threshold stops this
firing on tiny boards, where two postings sharing a line is normal rather than evidence.

**4. Self-reference filtering.** A company naming itself in its own job ad isn't stating a
requirement. Matching is done at a word boundary rather than by equality, which is what catches
Elastic writing "Elasticsearch" or Amazon writing "Amazon Web Services" — 3,911 such mentions are
filtered out of the current corpus. The boundary is the safe part: a plain substring test would
suppress **Dropbox** for a company named **Box**.

Each false positive I found is now a regression test. If any of them ever comes back, the suite
fails.

## Two decisions I'd defend

**Ranking by document frequency, not mention count.** A skill's score is how many postings mention
it *at all*, not how many times the word appears. One posting saying "Python" six times must not
outweigh six postings saying it once — the first is a writing quirk, the second is demand.

**Reporting a company count next to every skill, specifically to undermine my own headline
number.** This is the decision that paid off most. On a three-company corpus the report showed
Scala at 18% and Apache Spark at 20% — but their company counts were 2 and 3, and both numbers
were really just Databricks. Widening to 35 companies dropped Scala out of the top twelve
entirely and cut Spark to 6%. The count is what made those two rows visibly untrustworthy
*before* I had the data to prove it, and a measurement that can't tell you when it's misleading
isn't worth much.

## How I know the numbers are right

Not by assertion. The parts that can be checked, are:

- **57 automated tests.** Most encode a specific false positive, so the fixes for "excel,"
  "SWIFT," and "SAs" can't silently regress. Others assert that the counts quoted in this README
  still match the actual data files — a guard added after I found the documentation had drifted
  out of sync with the vocabulary.
- **The example above is a verbatim transcript** of the command that produces it, not a
  hand-typed illustration, and it's dated — the underlying job boards change daily.
- **The matched text is always surfaced**, in both the CLI and the web UI, so any individual
  result can be traced back to the words that caused it.

## Requirements

**Python 3.13.** spaCy publishes no wheels for 3.14 and ships no source distribution, so the
install fails outright on newer Python. On Fedora: `sudo dnf install python3.13`.

## Setup

```bash
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt   # includes the en_core_web_sm model
```

## Use it

### Analyze a market

Fetch the boards, then report on them. With no arguments the fetcher works through
`backend/data/boards.json`, the committed list of 35 validated boards. No auth needed; these
endpoints are public.

```bash
venv/bin/python -m backend.scripts.fetch_postings
venv/bin/python -m backend.scripts.analyze_market --title "data|analyst"
```

Fetching takes a few minutes and is the slow part; analysis afterwards is instant, because
**skills are extracted once at fetch time**, not on every report. Each board produces two files:
the full postings under `backend/data/postings/` (~50 MB) and a slim index of company, title and
skill names under `backend/data/index/` (~1 MB). Only the index is read when analyzing, which is
why a 7,500-posting report comes back in about 40ms rather than 20 seconds.

Editing the skill list invalidates every index. Rebuilding them does **not** need the network:

```bash
venv/bin/python -m backend.scripts.fetch_postings --reextract
```

Each index records a fingerprint of the vocabulary it was built against, and loading refuses a
mismatch rather than quietly reporting stale numbers.

To add a board, `--add` validates the token against its API first — roughly 40% of plausible
company names are dead slugs — and only appends it if postings come back:

```bash
venv/bin/python -m backend.scripts.fetch_postings --add anthropic --source greenhouse
venv/bin/python -m backend.scripts.fetch_postings --add linear --source ashby
```

| Flag | |
|---|---|
| `--title REGEX` | only postings whose title matches, e.g. `"engineer\|data"` |
| `--limit N` | how many skills to show (default 30) |
| `--keep-boilerplate` | skip boilerplate stripping, to check it didn't remove something real. Re-extracts from raw text, so it is much slower than a normal run |
| `--json` | machine-readable output |

### Analyze a single posting

```bash
echo "We use Postgres, k8s, and Power BI." | venv/bin/python -m backend.scripts.try_extractor
```

```
Matched 3 skills:
  Kubernetes         via 'k8s'  (Application server software)
  Microsoft Power BI via 'Power BI'  (Business intelligence and data analysis software)
  PostgreSQL         via 'Postgres'  (Object oriented data base management software)
```

It also takes a file path, or falls back to a built-in sample. `--json` prints raw output.

### Web

```bash
venv/bin/uvicorn app:app --reload
```

- `/` — paste a job description, see its skills and the text that triggered each match
- `/market` — skill demand across every cached posting, filterable by job title
- `POST /extract` and `GET /api/market` — the same data as JSON

## Technologies

**Python 3.13**, pinned for the reason above.

**spaCy 3.8**, used deliberately sparingly. Only the tokenizer runs — no tagger, parser, or
named-entity recognition — feeding two `PhraseMatcher` instances, one matching on lowercase and
one on exact orthography for the case-sensitive patterns. That restraint is what makes extraction
~2.7ms per posting — about 23 seconds for all 7,533, paid once at fetch time rather than on every
report. There is no language model in the loop and no API key anywhere in the project.

**FastAPI** with Pydantic v2 response models, served by **Uvicorn**. Two pages rendered through
**Jinja2** from a shared base template, plus a JSON API exposing exactly the same data the pages
render. Expensive market reports are memoized in-process.

**A frontend with no framework and no build step** — vanilla JavaScript and hand-written CSS on a
custom-property token system, with a light-first minimal design and a dark mode toggle that
applies before first paint so the theme never flashes.

**The public Greenhouse and Ashby job board APIs** for data, neither of which requires
authentication. Both are mapped onto one posting shape so nothing downstream knows the
difference. Greenhouse returns HTML, reduced to text by a hand-written stripper that converts
block-level tags to newlines — paragraph structure has to survive, because boilerplate detection
works per paragraph — and unescapes entities twice, since Greenhouse double-escapes some of its
content. Ashby returns `descriptionPlain` and needs no stripping at all. Postings are cached to
disk and reused until explicitly refreshed.

**pytest** for the suite. Everything else is standard library: `urllib`, `csv`, `json`, `html`,
`re`, `collections`, `functools`, `argparse`.

## Architecture

```
app.py                     FastAPI: 2 page routes, 2 JSON routes, static mount
backend/
  skills_extractor.py      PhraseMatcher over the vocabulary; returns skills + matched text
  market.py                document-frequency aggregation, self-reference filtering
  postings.py              Greenhouse/Ashby fetch, HTML→text, disk cache, boilerplate
                           stripping, index read/write + vocabulary fingerprint
  scripts/                 fetch_postings, analyze_market, try_extractor, build_skills_data
  data/                    boards.json, generated vocabulary + its hand-maintained sources
templates/                 shared base template + the two pages
static/                    stylesheet, shared JavaScript
tests/
```

The layering is strict. Nothing in `backend/` knows about HTTP; the command-line tools and the
web app are equal consumers of the same three modules. That's what made it possible to rebuild
the entire web interface later without touching a line of the analysis code.

## The skill list

`backend/data/skills.json` is generated — edit the sources, then rebuild:

```bash
venv/bin/python backend/scripts/build_skills_data.py
```

| Source | |
|---|---|
| `data/raw/software_skills.csv` | 8,744 entries from the US Department of Labor's [O\*NET](https://www.onetcenter.org) database; 176 are flagged "hot technology" |
| `data/modern_skills.json` | 58 hand-maintained entries for tools O\*NET lacks or lags on — Rust, Next.js, dbt, FastAPI, Databricks |
| `data/aliases.json` | 84 nickname mappings: `k8s` → Kubernetes, `Postgres` → PostgreSQL |
| `data/ambiguous_names.json` | names that require capitalization |
| `data/excluded_names.json` | O\*NET category rows like "Programming languages" that aren't products |

The build fails loudly if an alias names a skill that doesn't exist.

## Tests

```bash
venv/bin/pytest
```

## Limitations

Stated plainly, because they shape what the numbers actually mean:

- **O\*NET lags the industry.** It's a government occupational taxonomy, which is why some
  entries read as `ibm terraform` and `google angular`, and why modern tooling needs a separate
  hand-maintained file.
- **Single letters still misfire.** "Section C" and "see R for reference" match C and R.
  Distinguishing those needs surrounding context, not capitalization — it's the one
  false-positive class my four mechanisms don't solve.
- **Still only 35 companies, and they are not a random sample.** The list skews to US technology
  firms that publish on Greenhouse or Ashby, so the numbers describe that slice and not "the job
  market". The per-skill company count is there so you can see how broadly any figure is
  supported.
- **Some companies write tool-free job ads.** Cursor's 114 postings average 0.7 recognised skills
  each because they are written in aspirational language rather than lists of technologies. Those
  postings still count toward the denominator, which is honest but dilutes every share.
- **The name is still aspirational.** SkillPath can tell you what a market wants. Comparing that
  against what you already know, and recommending what to learn next, isn't built yet.

## What I'd do next

Widening the board list further, and away from US technology companies in particular. 35 boards
was enough to kill the worst single-company distortions, but the sample still describes one slice
of one industry. Adding more sources — Workable and SmartRecruiters both publish open endpoints —
would reach smaller and non-US employers that Greenhouse and Ashby miss.

After that, the feature the name promises — take a list of what you already know, diff it against
what the market asks for, and rank the gap by how much demand each missing skill would unlock.

## Project facts

Solo project, started 31 July 2026. About 1,460 lines of Python and 850 of front-end code, plus a
generated 8,800-entry vocabulary built from public data and a corpus of 7,533 job postings from
35 companies. No AI model, no paid APIs, and no authentication required to reproduce any result
in this document.
