"""Integration tests against a real Postgres.

These are the only tests that need `services:` in the pipeline. They skip
themselves when DATABASE_URL is unset or still points at SQLite, so running
`pytest` locally stays instant and the CI job that declares the service is the
one that does the real work.

What is worth testing here is precisely what SQLite cannot tell you: that the
unique constraint is actually enforced by the server, and that a real
transaction rolls back the way the code assumes.
"""

from sqlalchemy import select, text

from app.models import Link


def test_reaches_a_real_postgres(pg_client):
    engine = pg_client.__dict__["_snip_engine"]
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
    assert "PostgreSQL" in version


def test_create_and_follow_against_postgres(pg_client):
    slug = pg_client.post("/api/links", json={"url": "https://example.com"}).json()["slug"]
    response = pg_client.get(f"/{slug}", follow_redirects=False)
    assert response.status_code == 307
    assert pg_client.get(f"/api/links/{slug}").json()["hits"] == 1


def test_slug_uniqueness_is_enforced_by_the_database(pg_client):
    engine = pg_client.__dict__["_snip_engine"]
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(Link(slug="duplicat", target_url="https://example.com"))
        session.commit()

    with Session(engine) as session:
        session.add(Link(slug="duplicat", target_url="https://example.org"))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:  # pragma: no cover - only reached if the constraint is missing
            raise AssertionError("Postgres accepted a duplicate slug")

    with Session(engine) as session:
        rows = session.scalars(select(Link).where(Link.slug == "duplicat")).all()
    assert len(rows) == 1


def test_hits_survive_a_reconnect(pg_client):
    slug = pg_client.post("/api/links", json={"url": "https://example.com"}).json()["slug"]
    pg_client.get(f"/{slug}", follow_redirects=False)

    engine = pg_client.__dict__["_snip_engine"]
    engine.dispose()
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        link = session.scalar(select(Link).where(Link.slug == slug))
    assert link is not None
    assert link.hits == 1
