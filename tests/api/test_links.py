"""API tests against in-memory SQLite through FastAPI's TestClient."""

import pytest


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_link_returns_a_slug(client):
    response = client.post("/api/links", json={"url": "https://example.com/long/path"})
    assert response.status_code == 201
    body = response.json()
    assert body["target_url"] == "https://example.com/long/path"
    assert body["hits"] == 0
    assert body["slug"]


def test_create_link_normalises_a_missing_scheme(client):
    response = client.post("/api/links", json={"url": "example.com"})
    assert response.status_code == 201
    assert response.json()["target_url"] == "https://example.com"


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "not a url", ""])
def test_create_link_rejects_bad_input(client, bad):
    assert client.post("/api/links", json={"url": bad}).status_code == 400


def test_follow_redirects_to_the_target(client):
    slug = client.post("/api/links", json={"url": "https://example.com"}).json()["slug"]
    response = client.get(f"/{slug}", follow_redirects=False)
    # 307, not 301: a permanent redirect gets cached and then never comes back
    # to be counted.
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com"


def test_following_a_link_counts_a_hit(client):
    slug = client.post("/api/links", json={"url": "https://example.com"}).json()["slug"]
    for _ in range(3):
        client.get(f"/{slug}", follow_redirects=False)
    assert client.get(f"/api/links/{slug}").json()["hits"] == 3


def test_unknown_slug_is_404(client):
    assert client.get("/nosuchx", follow_redirects=False).status_code == 404
    assert client.get("/api/links/nosuchx").status_code == 404


def test_index_lists_created_links(client):
    slug = client.post("/api/links", json={"url": "https://example.com"}).json()["slug"]
    page = client.get("/")
    assert page.status_code == 200
    assert slug in page.text


def test_index_form_creates_a_link(client):
    page = client.post("/", data={"url": "example.org"}, follow_redirects=False)
    assert page.status_code == 200
    assert "example.org" in page.text


def test_index_form_reports_bad_input(client):
    page = client.post("/", data={"url": "javascript:alert(1)"}, follow_redirects=False)
    assert page.status_code == 200
    assert "valid http or https URL" in page.text
