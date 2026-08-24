"""snip : a very small URL shortener.

Five routes, one table, no framework magic beyond FastAPI's dependency
injection. The point of the project is the pipeline that builds it, so the
application stays small enough to read in one sitting.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import slugs
from app.db import get_session, init_db
from app.models import Link

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="snip", description="A very small URL shortener", lifespan=lifespan)

# Attempts to find a free slug before giving up. Collisions are vanishingly
# rare at this alphabet and length, but "vanishingly rare" is not "never", and
# the retry is what tests/unit checks.
MAX_SLUG_ATTEMPTS = 5

# The modern FastAPI spelling of a dependency. Declaring it once as a type
# alias keeps Depends() out of the argument defaults, which is both current
# style and what stops ruff's B008 firing on every route.
SessionDep = Annotated[Session, Depends(get_session)]


class CreateLink(BaseModel):
    url: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe. Cloud Run uses it, and so does the deploy job when it
    verifies a release rather than assuming one."""
    return {"status": "ok"}


def _create_link(session: Session, raw_url: str) -> Link:
    url = slugs.normalise_url(raw_url)
    if not slugs.is_valid_url(url):
        raise HTTPException(status_code=400, detail="A valid http or https URL is required")

    for _ in range(MAX_SLUG_ATTEMPTS):
        candidate = slugs.generate_slug()
        if not slugs.is_valid_slug(candidate):
            continue
        link = Link(slug=candidate, target_url=url)
        session.add(link)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        return link

    raise HTTPException(status_code=500, detail="Could not allocate a free slug")


@app.post("/api/links", status_code=201)
def create_link(payload: CreateLink, session: SessionDep) -> dict[str, object]:
    return _create_link(session, payload.url).as_dict()


@app.get("/api/links/{slug}")
def link_stats(slug: str, session: SessionDep) -> dict[str, object]:
    link = session.scalar(select(Link).where(Link.slug == slug))
    if link is None:
        raise HTTPException(status_code=404, detail="No such link")
    return link.as_dict()


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: SessionDep) -> HTMLResponse:
    recent = session.scalars(select(Link).order_by(Link.id.desc()).limit(10)).all()
    return TEMPLATES.TemplateResponse(request, "index.html", {"links": recent})


@app.post("/", response_class=HTMLResponse)
def index_submit(
    request: Request,
    url: Annotated[str, Form()],
    session: SessionDep,
) -> HTMLResponse:
    created = None
    error = None
    try:
        created = _create_link(session, url)
    except HTTPException as exc:
        error = exc.detail
    recent = session.scalars(select(Link).order_by(Link.id.desc()).limit(10)).all()
    return TEMPLATES.TemplateResponse(
        request, "index.html", {"links": recent, "created": created, "error": error}
    )


@app.get("/{slug}")
def follow(slug: str, session: SessionDep) -> RedirectResponse:
    link = session.scalar(select(Link).where(Link.slug == slug))
    if link is None:
        raise HTTPException(status_code=404, detail="No such link")
    link.hits += 1
    session.commit()
    # 307 rather than 301: a permanent redirect is cached by the browser, and
    # a cached redirect never comes back to be counted.
    return RedirectResponse(url=link.target_url, status_code=307)
