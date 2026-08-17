# Production Security Audit & Remediation — 2026-08-16

Companion to [issue #18](https://github.com/Byte-Quill/user-management-system/issues/18).

## Scope

- **Backend:** Django 6 + DRF + SimpleJWT (`backend/config/`, `backend/kyc/`), gunicorn, WhiteNoise
- **Frontend:** React 19 + TS + Vite SPA (`frontend/src/`), served by nginx
- **Infra/config:** `backend/docker-compose.yml`, `backend/docker-compose.tls.yml`, `backend/Caddyfile`, `backend/Dockerfile`, `frontend/nginx.conf`, `frontend/Dockerfile`, CI, dependency manifests

## OWASP Top 10 (2021) mapping

| Category | Status | Notes |
|---|---|---|
| A01 Broken Access Control | ✅ Verified | Owner-scoped querysets (404 not 403), role permissions, `select_for_update` on submit/review |
| A02 Cryptographic Failures | ✅ Verified | PBKDF2_sha256 1.2M iters, HttpOnly SameSite refresh cookie (path=/api/), rotation+blacklist, Secure cookies/HSTS under TLS, strong `SECRET_KEY` mandatory |
| A03 Injection | ✅ Verified | ORM parameterization; no raw SQL; magic-byte upload validation + ext allowlist |
| A04 Insecure Design | ✅ Verified | Login/refresh/logout/Google Origin checks (CSRF), rate limiting (edge + app), redacted access logs |
| A05 Security Misconfiguration | ✅ Fixed this PR | Base compose bound to loopback only; TLS profile documented as the only remote posture; `check --deploy` clean |
| A06 Vulnerable Components | ✅ Verified | `pip-audit` clean, `npm audit --omit=dev` clean, pinned deps, Dependabot |
| A07 Auth Failures | ✅ Verified | Generic login errors (no enumeration), per-IP + per-credential login throttles, MFA out of scope |
| A08 Software/Data Integrity | ✅ Verified | Signed download tokens (1h), immutable audit log, pinned deps |
| A09 Logging/Monitoring | ✅ Verified | Request-ID middleware, JSON logging, query strings redacted from nginx logs |
| A10 SSRF | ✅ Verified | No server-side URL fetching in app code (allauth token verification only, 5s timeout) |

## Findings & remediation

### MEDIUM — Base compose stack exposed plain HTTP on all interfaces

**Before:** `docker-compose.yml` published `8080:80` (all interfaces) with
`DJANGO_SECURE_SSL_REDIRECT=false` — if a host firewall was misconfigured,
cleartext session cookies and KYC PII were reachable on the network.

**After:**
- Base stack binds to `127.0.0.1:8080` only (loopback). Nothing beyond
  localhost can reach it without TLS.
- The TLS profile (`docker-compose.tls.yml`, Caddy edge) remains the only
  documented remote-access path and already binds nginx to `127.0.0.1`.
- **New:** the TLS profile sets `DJANGO_NUM_PROXIES=2` (Caddy → nginx →
  backend). Both proxies append to `X-Forwarded-For`, so with the old
  default of 1, IP-keyed rate limits would have keyed on nginx's Docker IP
  instead of the real client IP — a throttling bypass.

**Files:** `backend/docker-compose.yml`, `backend/docker-compose.tls.yml`, `README.md`

### Test gap — refresh-token reuse after logout/rotation

**Before:** no test proved that a captured refresh token stops working after
logout (blacklist) or after rotation (`BLACKLIST_AFTER_ROTATION`).

**After:** two new tests in `backend/kyc/tests.py`:
- `test_blacklisted_refresh_token_cannot_be_reused` — replays a pre-logout
  token directly in the body; must be rejected with 401.
- `test_rotated_refresh_token_is_blacklisted` — after a rotation, the
  pre-rotation token (body replay) must be rejected with 401.

### Verified already-fixed (no action needed, do not regress)

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

### Accepted risk / noted (tracked, not blocking)

- Register endpoint returns 400 for duplicate email (account enumeration,
  INFO). Deliberately left as-is: a uniform response would break the SPA's
  per-field error UX, and the register throttle (5/h) bounds probing.
- `nanoid` GHSA-2v37-7h3g-55p8 (high, no fix) via postcss/vite/tailwind —
  dev-only dependency, not in the production bundle.
- MFA not implemented; access tokens live 1h; refresh tokens are not revoked
  on password change (no password-change endpoint exists yet).

## Validation

| Check | Result |
|---|---|
| Backend test suite (`manage.py test kyc`) | ✅ 52 tests passing (573s) |
| `ruff check` | ✅ clean |
| `python manage.py check --deploy` (prod env) | ✅ clean |
| `npm run build` (tsc + vite) | ✅ clean |
| `pip-audit` | ✅ no known vulnerabilities |
| `npm audit --omit=dev` | ✅ 0 vulnerabilities |
| Compose YAML parse | ✅ both files valid |
