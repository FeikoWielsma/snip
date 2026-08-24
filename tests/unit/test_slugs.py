"""Unit tests for the pure functions. No database, no client, no I/O."""

import pytest

from app import slugs


def test_generated_slug_has_the_requested_length():
    assert len(slugs.generate_slug()) == slugs.SLUG_LENGTH
    assert len(slugs.generate_slug(12)) == 12


def test_generated_slug_avoids_ambiguous_characters():
    # A short link gets read aloud and typed by hand, so l/I/O/0/1 are out.
    sample = "".join(slugs.generate_slug(32) for _ in range(20))
    for ambiguous in "lIO01":
        assert ambiguous not in sample


def test_generated_slugs_differ():
    assert len({slugs.generate_slug() for _ in range(200)}) > 190


@pytest.mark.parametrize("reserved", sorted(slugs.RESERVED_SLUGS))
def test_reserved_slugs_are_rejected(reserved):
    assert not slugs.is_valid_slug(reserved)


@pytest.mark.parametrize("bad", ["", "has space", "UPPER", "sym!bol", "l" * 33])
def test_malformed_slugs_are_rejected(bad):
    assert not slugs.is_valid_slug(bad)


def test_generated_slugs_are_always_valid():
    for _ in range(100):
        assert slugs.is_valid_slug(slugs.generate_slug())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com"),
        ("  example.com  ", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("https://example.com/a/b?c=d", "https://example.com/a/b?c=d"),
        ("", ""),
    ],
)
def test_normalise_url(raw, expected):
    assert slugs.normalise_url(raw) == expected


@pytest.mark.parametrize(
    "url", ["https://example.com", "http://example.com/path", "https://sub.example.co.uk"]
)
def test_valid_urls_are_accepted(url):
    assert slugs.is_valid_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com",
        "https://",
        "",
    ],
)
def test_dangerous_or_incomplete_urls_are_rejected(url):
    # The scheme allowlist is the security-relevant assertion here: without it
    # a stored javascript: URL would be handed back to a browser.
    assert not slugs.is_valid_url(url)
