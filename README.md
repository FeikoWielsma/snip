# snip

A very small URL shortener. Paste a long URL, get a short one, follow it, and
see how many times it has been used.

The application exists to be *built and deployed*, not to be impressive. It is
the worked example for the SpiralTrain **GitLab CI/CD** course (TLG260), where
you migrate this repository to GitLab and rebuild its CI pipeline from nothing.

## Running it

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000. With no configuration it uses a local SQLite
file, so there is nothing to install and nothing to start.

## Tests

```bash
uv run pytest tests/unit tests/api    # the fast suite, well under a second
uv run pytest                         # everything; integration skips itself
```

Three suites, deliberately separated :

| Suite | Needs | What it covers |
| --- | --- | --- |
| `tests/unit` | nothing | slug generation, URL validation. Pure functions |
| `tests/api` | nothing | every route, through FastAPI's in-process test client |
| `tests/integration` | Postgres | constraints and transactions SQLite cannot prove |

`tests/integration` skips unless `DATABASE_URL` points at a real Postgres, so a
plain `pytest` run stays instant :

```bash
DATABASE_URL=postgresql+psycopg://snip:snip@localhost:5432/snip uv run pytest tests/integration
```

There is no browser anywhere in the suite, and that is on purpose. The test
client calls the ASGI application directly, so there is no server to start and
no port to wait on.

## A trap worth knowing

The health endpoint is `/api/health`, not the conventional `/healthz`. On Cloud
Run, `/healthz` is answered by Google's frontend and never reaches your
container, so a deployment check against it gets Google's 404 page back however
healthy the service is. `/health`, `/livez` and `/readiness` all pass through
normally.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./snip.db` | SQLAlchemy connection string |
| `PORT` | `8080` | Port the container listens on |

## Layout

```text
app/slugs.py      slug generation and URL validation; pure, no I/O
app/db.py         engine and session, driven by DATABASE_URL
app/models.py     the one table
app/main.py       the five routes
Dockerfile        single-stage and naive, on purpose; the course fixes it
```

## A note on the Dockerfile

It is bad. It ships the full CPython image, the build toolchain and the test
suite into production, and weighs about a gigabyte. That is deliberate :
rewriting it as a multi-stage build, and measuring what that saves, is one of
the course exercises.
