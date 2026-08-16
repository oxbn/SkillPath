import re
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend.market import analyze
from backend.postings import cached_boards, load_postings, strip_boilerplate
from backend.skills_extractor import extract_skills

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SkillPath")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Neither page takes server-side data: they are shells the browser hydrates from /extract
# and /api/market.
templates = Jinja2Templates(directory=BASE_DIR / "templates")


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
def read_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


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


# The corpus only changes when the cache is refetched, so re-analyzing it on every request
# is pure waste.
@lru_cache(maxsize=16)
def market_report(boards, title):
    postings = load_postings(list(boards))

    if title:
        pattern = re.compile(title, re.IGNORECASE)
        postings = [posting for posting in postings if pattern.search(posting["title"])]

    return analyze(strip_boilerplate(postings))


@app.get("/market", include_in_schema=False)
def read_market_page(request: Request):
    return templates.TemplateResponse(request, "market.html")


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
