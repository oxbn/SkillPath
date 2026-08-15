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

**Analyze a market.** Point it at a set of company job boards and it fetches every open posting,
reduces them to plain text, and ranks skills by how many postings mention each one. The output
gives each skill's share of the corpus, its raw posting count, and how many distinct companies
asked for it. A regular expression on job titles narrows the corpus to a slice of the market —
`engineer|data|analyst` — and re-ranks on just those roles.

```
1531 postings from 3 companies

  SKILL                             SHARE  POSTINGS  COMPANIES
  Python                             25%       381          3
  Amazon Web Services AWS software   23%       356          3
  Structured query language SQL      23%       345          3
  Microsoft Azure software           21%       322          3
  Apache Spark                       20%       307          3
  Scala                              18%       273          2
```

*Snapshot: the stripe, databricks and figma boards, fetched 2026-08-07. These boards change
daily, so your own numbers will differ.*

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
requirement.

Each false positive I found is now a regression test. If any of them ever comes back, the suite
fails.

## Two decisions I'd defend

**Ranking by document frequency, not mention count.** A skill's score is how many postings mention
it *at all*, not how many times the word appears. One posting saying "Python" six times must not
outweigh six postings saying it once — the first is a writing quirk, the second is demand.

**Reporting a company count next to every skill, specifically to undermine my own headline
number.** With only three boards cached, "Scala 18%" mostly means *Databricks likes Scala* — and
Scala is the one row in the table above with a company count of 2 rather than 3. I could have
left that out and the numbers would have looked stronger. The count is there because a
measurement that can't tell you when it's misleading isn't worth much.

## How I know the numbers are right

Not by assertion. The parts that can be checked, are:

- **32 automated tests.** Most encode a specific false positive, so the fixes for "excel,"
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

Fetch some boards, then report on them. Board tokens are the company's Greenhouse slug — the
`acme` in `boards.greenhouse.io/acme`. No auth needed; these endpoints are public.

```bash
venv/bin/python -m backend.scripts.fetch_postings stripe databricks figma
venv/bin/python -m backend.scripts.analyze_market --title "data|analyst"
```

Postings are cached under `backend/data/postings/` and reused until you pass `--refresh`.

| Flag | |
|---|---|
| `--title REGEX` | only postings whose title matches, e.g. `"engineer\|data"` |
| `--limit N` | how many skills to show (default 30) |
| `--keep-boilerplate` | skip boilerplate stripping, to check it didn't remove something real |
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
~2.7ms per posting, fast enough to analyze the full 1,531-posting corpus in about four seconds on
a laptop. There is no language model in the loop and no API key anywhere in the project.

**FastAPI** with Pydantic v2 response models, served by **Uvicorn**. Two pages rendered through
**Jinja2** from a shared base template, plus a JSON API exposing exactly the same data the pages
render. Expensive market reports are memoized in-process.

**A frontend with no framework and no build step** — vanilla JavaScript and hand-written CSS on a
custom-property token system, with a light-first minimal design and a dark mode toggle that
applies before first paint so the theme never flashes.

**The public Greenhouse Job Board API** for data, which requires no authentication. Postings are
cached to disk and reused until explicitly refreshed. HTML is reduced to text by a hand-written
stripper that converts block-level tags to newlines — paragraph structure has to survive, because
boilerplate detection works per paragraph — and unescapes entities twice, since Greenhouse
double-escapes some of its content.

**pytest** for the suite. Everything else is standard library: `urllib`, `csv`, `json`, `html`,
`re`, `collections`, `functools`, `argparse`.

## Architecture

```
app.py                     FastAPI: 2 page routes, 2 JSON routes, static mount
backend/
  skills_extractor.py      PhraseMatcher over the vocabulary; returns skills + matched text
  market.py                document-frequency aggregation, self-reference filtering
  postings.py              Greenhouse fetch, HTML→text, disk cache, boilerplate stripping
  scripts/                 fetch_postings, analyze_market, try_extractor, build_skills_data
  data/                    generated vocabulary + its four hand-maintained sources
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
- **Few boards means company-shaped numbers.** With three companies cached, any percentage is
  heavily influenced by one employer's hiring mix. The per-skill company count exposes this;
  adding 20–30 boards is the real fix.
- **The name is still aspirational.** SkillPath can tell you what a market wants. Comparing that
  against what you already know, and recommending what to learn next, isn't built yet.

## What I'd do next

Broadening to 20–30 boards is the highest-value change, because it converts the output from
"what these three companies want" into something that can reasonably be called a market. That
also exposes a weakness I already know about: self-reference filtering currently only catches
single-word matches, so an Amazon posting would still count "Amazon Web Services" as market
demand for AWS.

After that, the feature the name promises — take a list of what you already know, diff it against
what the market asks for, and rank the gap by how much demand each missing skill would unlock.

## Project facts

Solo project, 15 commits between 31 July and 11 August 2026. About 975 lines of Python and 850 of
front-end code, plus a generated 8,800-entry vocabulary built from public data. No AI model, no
paid APIs, and no authentication required to reproduce any result in this document.
