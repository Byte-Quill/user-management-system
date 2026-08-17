"""Disposable / temporary email domain filtering.

Registration is the entry point to a KYC pipeline, so accounts must be tied
to a real, lasting inbox. Disposable ("burner") email services let someone
receive the signup OTP and then vanish, defeating both identity verification
and any future account-recovery or audit contact.

The blocklist comes from the community-maintained ``disposable-email-domains``
package (~8k domains, updated upstream as new burner providers appear). It is
still fully local — no external API or network call — so the check stays fast,
deterministic, and unaffected by third-party outages. Bump the package version
in ``requirements.txt`` to pick up newly listed providers.

The server is the source of truth: the SPA mirrors this rule in
``frontend/src/validation.ts`` for immediate feedback, but a direct API
client is still stopped here.
"""

from __future__ import annotations

from disposable_email_domains import blocklist as _BLOCKLIST

# Known disposable / temporary email providers. Lowercase, bare domains
# (no scheme, no subdomain prefix). Matching is done on the exact domain
# part of the address, case-insensitively.
DISPOSABLE_DOMAINS: frozenset[str] = frozenset(_BLOCKLIST)


def is_disposable_email(email: str) -> bool:
    """Return True when the address's domain is a known disposable provider.

    Only the domain part is inspected (case-insensitively). The local part
    is irrelevant to the check. Malformed input (no ``@``) returns False —
    basic format validation is handled elsewhere, so this stays focused.
    """
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].strip().lower()
    return domain in DISPOSABLE_DOMAINS
