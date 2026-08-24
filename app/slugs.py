"""Slug generation and URL validation.

Pure functions with no I/O, which is what makes them the fastest tests in the
suite: tests/unit exercises this module without a database, a client or a
server.
"""

import re
import secrets
from urllib.parse import urlparse

# Deliberately missing l, I, O, 0 and 1. A short link gets read aloud and
# typed by hand, so the ambiguous characters are more trouble than the extra
# entropy is worth.
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"

SLUG_LENGTH = 7
SLUG_PATTERN = re.compile(rf"^[{ALPHABET}]{{1,32}}$")

# Paths the application serves itself. A link may not claim one of these or it
# would shadow a real route.
RESERVED_SLUGS = frozenset({"api", "healthz", "static", "admin", "favicon.ico"})

ALLOWED_SCHEMES = frozenset({"http", "https"})

# "scheme:" at the start of a string, per RFC 3986. Matching this rather than
# "://" matters: 'javascript:alert(1)' has a scheme but no slashes, and
# treating it as a bare hostname would turn it into a valid-looking
# 'https://javascript:alert(1)' and smuggle it past the scheme allowlist.
SCHEME_PREFIX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


def generate_slug(length: int = SLUG_LENGTH) -> str:
    """Return a random slug. Uses secrets, not random: a guessable slug leaks
    every link anyone has ever shortened."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_slug(slug: str) -> bool:
    """True if the slug is well formed and does not collide with a route."""
    if slug in RESERVED_SLUGS:
        return False
    return bool(SLUG_PATTERN.match(slug))


def normalise_url(raw: str) -> str:
    """Tidy user input into something storable.

    People paste 'example.com' far more often than 'https://example.com', so a
    missing scheme is assumed to be https rather than rejected.
    """
    url = raw.strip()
    if not url:
        return ""
    if SCHEME_PREFIX.match(url):
        return url
    return f"https://{url}"


def is_valid_url(url: str) -> bool:
    """True if the URL is one we are willing to redirect to.

    The scheme allowlist is the security-relevant line in this file: without
    it, 'javascript:alert(1)' would be stored and later handed straight back
    to a browser.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    host = parsed.netloc
    return bool(host) and not any(c.isspace() for c in host)
