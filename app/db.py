"""Database engine and session handling.

DATABASE_URL decides the backend, and defaults to a local SQLite file so the
application runs with no setup at all. In CI the integration job overrides it
to point at the Postgres service; every other job leaves it alone.
"""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./snip.db"


class Base(DeclarativeBase):
    """Base class for the ORM models."""


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None) -> Engine:
    """Build an engine for the given URL.

    SQLite needs check_same_thread disabled because the test client and the
    application can touch the connection from different threads; Postgres
    needs no such special case.

    In-memory SQLite additionally needs StaticPool. Without it every new
    connection opens its own empty database, so a row written by one request
    is invisible to the next and every test fails with "no such table".
    """
    url = url or database_url()
    kwargs: dict[str, object] = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def init_db(engine: Engine | None = None) -> None:
    """Create the tables. Enough for a teaching project; a real service would
    use Alembic migrations here."""
    from app import models  # noqa: F401  (imported for its side effect)

    Base.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency. Tests override this rather than the engine, which
    is why the routes never import an engine directly."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()
