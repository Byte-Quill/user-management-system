"""Regenerate frontend/src/disposableEmails.ts from the SAME PyPI blocklist the
backend uses, so the SPA mirror can never drift from the server rule."""
from disposable_email_domains import blocklist

domains = sorted(blocklist)

header = '''/**
 * Disposable / temporary email domain blocklist.
 *
 * AUTO-GENERATED from the `disposable-email-domains` PyPI package (the same
 * community-maintained list the backend uses in `kyc/email_domains.py`).
 * Do not edit by hand — regenerate with:
 *   cd backend && .venv/bin/python scripts/gen_disposable_emails.py
 *
 * Mirrors the server-side rule so users get immediate feedback during
 * registration. The backend remains the source of truth — a direct API client
 * is still stopped there.
 *
 * Matching is done on the exact domain part of the address, case-insensitively.
 */
'''

lines = ",\n".join(f'  "{d}"' for d in domains)
body = f"export const DISPOSABLE_EMAIL_DOMAINS: ReadonlySet<string> = new Set([\n{lines},\n]);\n"

footer = '''
/** True when the address's domain is a known disposable provider. */
export function isDisposableEmail(email: string): boolean {
  const at = email.lastIndexOf("@");
  if (at < 0) return false;
  const domain = email.slice(at + 1).trim().toLowerCase();
  return DISPOSABLE_EMAIL_DOMAINS.has(domain);
}
'''

out = header + "\n" + body + footer
path = "/home/bisu/Documents/Personal Projects/user-managment/user-management-system/frontend/src/disposableEmails.ts"
with open(path, "w") as f:
    f.write(out)
print(f"wrote {len(domains)} domains -> {path}")
print(f"size: {len(out)} bytes")
