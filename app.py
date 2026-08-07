import re
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.market import analyze
from backend.postings import cached_boards, load_postings, strip_boilerplate
from backend.skills_extractor import extract_skills

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="SkillPath")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Skill(BaseModel):
    name: str
    display_name: str
    category: str
    hot_technology: bool
    mentions: list[str]
    count: int


class ExtractRequest(BaseModel):
    text: str = Field(max_length=50_000)


class ExtractResponse(BaseModel):
    skills: list[Skill]


@app.get("/", include_in_schema=False)
def read_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/extract")
def extract(request: ExtractRequest) -> ExtractResponse:
    return ExtractResponse(skills=extract_skills(request.text))


class MarketSkill(BaseModel):
    name: str
    display_name: str
    category: str
    postings: int
    share: float
    companies: int


class MarketResponse(BaseModel):
    postings: int
    companies: int
    boards: list[str]
    skills: list[MarketSkill]


# Analyzing 600+ postings takes a couple of seconds, and the corpus only changes when the
# cache is refetched, so a request-level cache keeps the page responsive.
@lru_cache(maxsize=16)
def market_report(boards, title):
    postings = load_postings(list(boards))

    if title:
        pattern = re.compile(title, re.IGNORECASE)
        postings = [posting for posting in postings if pattern.search(posting["title"])]

    return analyze(strip_boilerplate(postings))


@app.get("/market", include_in_schema=False)
def read_market_page():
    return FileResponse(STATIC_DIR / "market.html")


@app.get("/api/market")
def read_market(title: str | None = None) -> MarketResponse:
    boards = tuple(cached_boards())
    if not boards:
        raise HTTPException(
            status_code=404,
            detail="No postings cached. Run: python -m backend.scripts.fetch_postings <board>",
        )

    try:
        report = market_report(boards, title)
    except re.error as error:
        raise HTTPException(status_code=422, detail=f"Bad title filter: {error}") from error

    return MarketResponse(boards=list(boards), **report)
