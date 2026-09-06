"""Disposable / temporary email domain filtering."""

from __future__ import annotations

from disposable_email_domains import blocklist as _BLOCKLIST


DISPOSABLE_DOMAINS: frozenset[str] = frozenset(_BLOCKLIST)


def is_disposable_email(email: str) -> bool:
    """Return True when the address's domain is a known disposable provider."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].strip().lower()
    return domain in DISPOSABLE_DOMAINS
