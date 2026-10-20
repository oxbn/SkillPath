from contextlib import asynccontextmanager
from typing import Literal

from backend.refresh import Refresher
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend.market import analyze
from backend.postings import StaleIndexError, cached_boards, index_path, load_index
from backend.skills_extractor import extract_skills
from backend.title_filter import TitleFilterError, filter_titles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

refresher = Refresher()


@asynccontextmanager
async def lifespan(app):
    refresher.start()
    try:
        yield
    finally:
        # Network requests have a bounded timeout; finish the current board on shutdown.
        import asyncio
        await asyncio.to_thread(refresher.stop)


app = FastAPI(title="SkillPath", lifespan=lifespan)


@app.get("/api/refresh")
def refresh_status():
    return refresher.status()


@app.post("/api/refresh", status_code=202)
def refresh_market(request: Request):
    # Browser requests must originate from this app (also prevents cross-site triggers).
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Refresh must be requested from this app.")
    started = refresher.start_refresh(force=True)
    return {"started": started, **refresher.status()}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Neither page takes server-side data: they are shells the browser hydrates from /extract
# and /api/market.
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class Evidence(BaseModel):
    text: str
    start: int
    end: int
    classification: Literal["required", "optional", "negated", "incidental", "unknown"]


class Skill(BaseModel):
    name: str
    display_name: str
    category: str
    hot_technology: bool
    mentions: list[str]
    count: int
    evidence: list[Evidence]


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
    company_share: float


class CorpusBoard(BaseModel):
    board: str
    source: str
    fetched_at: str | None
    built_at: str
    vocabulary: str
    analysis_version: str


class MarketResponse(BaseModel):
    postings: int
    companies: int
    boards: list[str]
    skills: list[MarketSkill]
    corpus: list[CorpusBoard]
    title: str | None
    regex: bool
    requirements_only: bool


# The corpus only changes when the cache is refetched, so re-analyzing it on every request
# is pure waste. `built` is in the key rather than unused: without it a refetch would keep
# serving the previous report forever, since boards and title alone would be unchanged.
@lru_cache(maxsize=16)
def market_report(boards, title, built, regex_mode=False, requirements_only=False):
    postings, metadata = load_index(list(boards), include_metadata=True)
    postings = filter_titles(postings, title, regex_mode)
    return {**analyze(postings, requirements_only), "corpus": metadata}


def corpus_version(boards):
    """Changes whenever any index is rewritten, which is what makes the cache key honest."""
    return tuple(index_path(board).stat().st_mtime_ns for board in boards)


@app.get("/market", include_in_schema=False)
def read_market_page(request: Request):
    return templates.TemplateResponse(request, "market.html")


@app.get("/api/market")
def read_market(
    title: str | None = Query(default=None, max_length=200),
    regex: bool = False,
    requirements_only: bool = False,
) -> MarketResponse:
    boards = tuple(cached_boards())
    if not boards:
        raise HTTPException(
            status_code=404,
            detail="Preparing market data. The first fetch takes a few minutes; this page will update automatically.",
        )

    try:
        report = market_report(boards, title, corpus_version(boards), regex, requirements_only)
    except TitleFilterError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except StaleIndexError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return MarketResponse(boards=list(boards), title=title, regex=regex,
                          requirements_only=requirements_only, **report)
