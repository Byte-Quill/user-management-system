# Production Security Audit & Remediation

Original audit: **2026-08-16**, companion to
[issue #18](https://github.com/Byte-Quill/user-management-system/issues/18).
This document is kept current — last updated **2026-08-17** to reflect the
system as it stands today (all original findings resolved or re-verified).

## Scope

- **Backend:** Django 6 + DRF + SimpleJWT (`backend/config/`, `backend/kyc/`), gunicorn, WhiteNoise
- **Frontend:** React 19 + TS + Vite SPA (`frontend/src/`), served by nginx
- **Infra/config:** `backend/docker-compose.yml`, `backend/docker-compose.tls.yml`, `backend/Caddyfile`, `backend/Dockerfile`, `frontend/nginx.conf`, `frontend/Dockerfile`, CI, dependency manifests

## OWASP Top 10 (2021) mapping

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | ✅ Verified | Owner-scoped querysets (404 not 403), ownership compared by `applicant_id` (not email — safe for phone-only accounts), role permissions, `select_for_update` on submit/review |
| A02 Cryptographic Failures | ✅ Verified | PBKDF2_sha256 1.2M iterations, OTP codes stored as HMAC-SHA256 keyed with `SECRET_KEY`, HttpOnly SameSite refresh cookie (path=/api/), rotation+blacklist, Secure cookies/HSTS under TLS, strong `SECRET_KEY` mandatory |
| A03 Injection | ✅ Verified | ORM parameterization; no raw SQL; magic-byte upload validation + ext allowlist |
| A04 Insecure Design | ✅ Verified | Origin checks on login/refresh/logout/Google (CSRF), rate limiting (edge + app), redacted access logs, generic OTP responses (no enumeration) |
| A05 Security Misconfiguration | ✅ Fixed | Base compose bound to loopback only; TLS profile documented as the only remote posture; `check --deploy` clean |
| A06 Vulnerable Components | ✅ Verified | `pip-audit` clean, `npm audit --omit=dev` clean, pinned deps, Dependabot |
| A07 Auth Failures | ✅ Verified | Generic login errors (no enumeration), per-IP + per-credential login throttles, hard email-OTP verification, MFA out of scope |
| A08 Software/Data Integrity | ✅ Verified | Signed download tokens (15 min), immutable audit log, pinned deps |
| A09 Logging/Monitoring | ✅ Verified | Request-ID middleware, JSON logging, query strings redacted from nginx logs |
| A10 SSRF | ✅ Verified | No server-side URL fetching in app code (allauth token verification only, 5s timeout) |

## Findings & remediation

### FIXED — Login CSRF (originally MEDIUM)

`CookieTokenObtainPairView` had no `Origin` check while refresh/logout did.
With HTTPS deploys (`SameSite=None` + `Secure`), a cross-site form POST could
have logged a victim into an attacker account, causing KYC PII to be uploaded
into the attacker's account. **Fixed:** the login view now calls
`origin_allowed()` before issuing tokens (`kyc/auth_views.py`), matching
refresh, logout, and Google Sign-In.

### FIXED — Logout CSRF (originally LOW)

`LogoutView` had no `Origin` check, allowing a forced logout/blacklist of a
victim's refresh token. **Fixed:** `origin_allowed()` is now enforced on
logout as well.

### FIXED — Base compose stack exposed plain HTTP on all interfaces (originally MEDIUM)

**Before:** `docker-compose.yml` published `8080:80` (all interfaces) with
`DJANGO_SECURE_SSL_REDIRECT=false` — if a host firewall was misconfigured,
cleartext session cookies and KYC PII were reachable on the network.

**After:**
- Base stack binds to `127.0.0.1:8080` only (loopback). Nothing beyond
  localhost can reach it without TLS.
- The TLS profile (`docker-compose.tls.yml`, Caddy edge) remains the only
  documented remote-access path and already binds nginx to `127.0.0.1`.
- The TLS profile sets `DJANGO_NUM_PROXIES=2` (Caddy → nginx → backend).
  Both proxies append to `X-Forwarded-For`, so with the old default of 1,
  IP-keyed rate limits would have keyed on nginx's Docker IP instead of the
  real client IP — a throttling bypass.

### FIXED — Signed download token lifetime

Download tokens were documented as 1-hour; the implementation uses
`DOWNLOAD_TOKEN_MAX_AGE = 900` (15 minutes). Documentation now matches the
code — shorter-lived tokens reduce exposure in nginx access logs and browser
history.

### FIXED — Test gap: refresh-token reuse after logout/rotation

Two tests in `backend/kyc/tests.py` prove captured refresh tokens stop
working:
- `test_blacklisted_refresh_token_cannot_be_reused` — replays a pre-logout
  token directly in the body; rejected with 401.
- `test_rotated_refresh_token_is_blacklisted` — after a rotation, the
  pre-rotation token (body replay) is rejected with 401.

### Verified controls (do not regress)

- Login/refresh/logout/Google Origin checks with tests
- Redacted nginx `log_format` (no query strings)
- `/admin/` edge rate limiting (auth zone)
- Mandatory `DJANGO_SECRET_KEY` / `POSTGRES_PASSWORD` env vars
- Attachment `Content-Disposition` on document downloads
- `seed_demo` refuses to run with `DJANGO_DEBUG=false` without `--force`
- Per-IP + per-credential login throttles; `Retry-After` on 429s
- XFF spoof test (`test_throttle_ident_uses_last_xff_entry`)
- Download token expiry test
- Concurrency tests for submit/review (`select_for_update`)
- Email OTP: HMAC-keyed codes, 10-min TTL, 5 attempts, atomic single-use
  consumption, generic 200 responses, 5/hour request throttle, 60s resend
  cooldown
- Registration: disposable/temp-mail domains rejected
  (`disposable-email-domains` blocklist), phone numbers validated and
  normalized to E.164 via libphonenumber (`phonenumbers`)
- Email-send outage resilience: registration/resend/reset-request degrade to
  recoverable states instead of 500s

### Accepted risk / noted (tracked, not blocking)

- Register endpoint returns 400 for duplicate email (account enumeration,
  INFO). Deliberately left as-is: a uniform response would break the SPA's
  per-field error UX, and the register throttle (5/h) bounds probing.
- MFA not implemented; access tokens live 1h; refresh tokens are not revoked
  on password reset (bounded by token TTLs).
- `nanoid` GHSA-2v37-7h3g-55p8 previously flagged via postcss/vite/tailwind
  dev-deps: resolved by the lockfile bump to nanoid 3.3.18; `npm audit
  --omit=dev` reports 0 vulnerabilities.

## Validation (2026-08-17)

| Check | Result |
|---|---|
| Backend test suite (`manage.py test kyc`) | ✅ 82 tests passing |
| `ruff check` | ✅ clean |
| `python manage.py check --deploy` (prod env) | ✅ clean |
| `npm run build` (tsc + vite) | ✅ clean |
| `pip-audit` | ✅ no known vulnerabilities |
| `npm audit --omit=dev` | ✅ 0 vulnerabilities |
| Compose YAML parse | ✅ both files valid |
