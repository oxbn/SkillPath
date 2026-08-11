# SkillPath

Reads job postings and reports which skills employers actually ask for — not one posting at a
time, but across hundreds at once.

Reading a single job ad is easy; the requirements are already a bulleted list. But if you're
deciding what to learn next, one ad tells you nothing — you need the pattern across many, and
nobody reads 600 job ads. SkillPath pulls every opening from a set of company job boards, reads
them all in about two seconds, and ranks skills by how many postings mention each one.

```
626 postings from 3 companies

  SKILL                             SHARE  POSTINGS  COMPANIES
  Amazon Web Services AWS software   37%       230          3
  Python                             37%       229          3
  Microsoft Azure software           32%       201          3
  Apache Spark                       32%       200          3
  Scala                              31%       193          2
  Structured query language SQL      26%       160          3
```

No AI model and no API keys. It matches against a vocabulary of ~8,800 tool names and their
nicknames, which is why it's fast enough to run over thousands of documents for free.

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

## How it works

A [spaCy](https://spacy.io) `PhraseMatcher` scans tokenized text for known skill names. Only
the tokenizer runs — no tagger, parser, or NER — which makes extraction ~2.4ms per posting.

**The hard part isn't finding skill names, it's rejecting things that only look like them.**
Every one of these was a real false positive found in real postings:

| Text | Wrongly matched |
|---|---|
| "we will **go** over it" | Go |
| "a culture where everyone can **excel**" | Microsoft Excel — 36% of one corpus |
| "equipping AEs and **SAs**" | SAS |
| "cheaper than **SWIFT**" | Swift |
| "you will **bootstrap** projects" | Bootstrap |
| Figma's own name in Figma's job ads | Figma — 33% of one corpus |

Four mechanisms handle these:

- **Per-pattern case sensitivity.** Names that collide with English words match only when
  capitalized. The list is derived by intersecting single-token skill names with a system
  dictionary, then committed as `backend/data/ambiguous_names.json`. Postings capitalize
  product names ~99% of the time, so the recall cost is negligible.
- **Longest-match-wins.** "Microsoft SQL Server" beats the bare "SQL" inside it; "C++" beats
  the "C" its first token would match.
- **Boilerplate stripping.** Paragraphs appearing in more than 60% of one company's postings
  are dropped, which removes blurbs, EEO statements, and benefits lists — about 24% of a
  typical corpus.
- **Self-reference filtering.** A company naming itself in its own posting isn't a requirement.

Results carry the text that triggered them, so you can see *why* something matched.

## The skill list

`backend/data/skills.json` is generated — edit the sources, then rebuild:

```bash
venv/bin/python backend/scripts/build_skills_data.py
```

| Source | |
|---|---|
| `data/raw/software_skills.csv` | 8,753 entries from the US Department of Labor's [O\*NET](https://www.onetcenter.org) database; 176 are flagged "hot technology" |
| `data/modern_skills.json` | 58 hand-maintained entries O\*NET lacks entirely — Rust, Next.js, dbt, FastAPI, Databricks |
| `data/aliases.json` | 84 nickname mappings: `k8s` → Kubernetes, `Postgres` → PostgreSQL |
| `data/ambiguous_names.json` | names that require capitalization |
| `data/excluded_names.json` | O\*NET category rows like "Programming languages" that aren't products |

The build fails loudly if an alias names a skill that doesn't exist.

## Tests

```bash
venv/bin/pytest
```

## Known limitations

- **O\*NET lags the industry.** It's a government occupational taxonomy, which is why entries
  read as `ibm terraform` and `google angular`, and why Rust and Next.js need a separate file.
- **Single letters still misfire.** "Section C" and "see R for reference" match C and R.
  Distinguishing those needs surrounding context, not casing.
- **Few boards means company-shaped numbers.** With three companies cached, "Scala 31%" mostly
  means Databricks likes Scala. The report shows a company count per skill so you can spot it;
  adding 20–30 boards is the fix.
- **No path yet.** SkillPath can tell you what a market wants. Comparing that against what you
  already know, and recommending what to learn next, isn't built.
