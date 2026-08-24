"""Shared test fixtures.

The client fixture points the application at a throwaway database and hands
back a TestClient. TestClient calls the ASGI app in process: there is no
uvicorn to start, no port to bind and nothing to poll, which is most of the
reason the suite finishes in well under a second.
"""

import os

# Set before app import: the application builds its own engine from
# DATABASE_URL at startup, and without this a plain `pytest` run would leave a
# stray snip.db file behind. The tests themselves use the engines built below.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base, get_session, make_engine  # noqa: E402
from app.main import app  # noqa: E402


def _client_for(url: str) -> TestClient:
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    client.__dict__["_snip_engine"] = engine
    return client


@pytest.fixture
def client():
    """A client backed by in-memory SQLite. Used by tests/api."""
    c = _client_for("sqlite://")
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def pg_client():
    """A client backed by the real Postgres named in DATABASE_URL.

    Skips when DATABASE_URL is unset or still pointing at SQLite, so
    tests/integration is a no-op locally and only does real work in the CI job
    that declares the postgres service.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        pytest.skip("DATABASE_URL does not point at Postgres")
    c = _client_for(url)
    yield c
    app.dependency_overrides.clear()
