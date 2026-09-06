# Architecture

Production-grade architecture reference for the KYC Application Verification
System. For local setup, environment variables, and the API/endpoint runbook,
see the [README](README.md); for security audit history, see
[docs/security-audit-2026-08-16.md](docs/security-audit-2026-08-16.md).

## Table of contents

1. [System overview](#1-system-overview)
2. [Technology stack](#2-technology-stack)
3. [Deployment topology](#3-deployment-topology)
4. [Backend architecture](#4-backend-architecture)
5. [Domain workflows](#5-domain-workflows)
6. [Cross-cutting concerns](#6-cross-cutting-concerns)
7. [Frontend architecture](#7-frontend-architecture)
8. [Validation contract](#8-validation-contract)
9. [Security architecture](#9-security-architecture)
10. [Testing & CI](#10-testing--ci)
11. [Deployment & operations](#11-deployment--operations)
12. [Key architecture decisions](#12-key-architecture-decisions)
13. [Extension guide](#13-extension-guide)

---

## 1. System overview

A KYC (Know Your Customer) platform where **applicants** submit identity
applications with supporting documents, **reviewers** decide on them through a
governed workflow, **super admins** manage accounts and roles, and the **CEO**
consumes operational analytics. It is a self-contained, zero-vendor stack:
every runtime dependency (app server, database, cache, edge, email relay) is
self-hosted or free-tier.

### 1.1 System context

```
 ┌────────────┐   HTTPS    ┌───────────────────────────────┐
 │  Applicant │───────────▶│                               │
 ├────────────┤            │     KYC Verification System   │
 │  Reviewer  │───────────▶│  SPA · API · Postgres · Mail  │
 ├────────────┤            │                               │
 │ Super Admin│───────────▶│  Also federates with:         │
 ├────────────┤            │   · Google (Sign-In / OIDC)   │
 │    CEO     │───────────▶│   · Resend (transactional     │
 └────────────┘            │     email relay over SMTP)    │
                           └───────────────────────────────┘
```

### 1.2 Core capabilities

| Capability | Description |
| --- | --- |
| Identity & access | Email **or** phone login, Google Sign-In, hard email verification (OTP), password reset, JWT session with rotation |
| KYC applications | Draft → submit → review lifecycle with per-decision audit trail and document evidence |
| Document evidence | Magic-byte-validated uploads (JPG/PNG/PDF, 5 MB) served via expiring signed URLs |
| Review workflow | Role-gated queue, decision with mandatory notes on reject/resubmission, self-review blocked |
| User management | Super-admin console: create users, reset passwords, activate/deactivate, role changes (last active super admin protected) |
| Analytics | CEO dashboard: KPIs, approval rate, pipeline distribution, 30-day email activity |
| Governance | Full `AuditLog` of state-changing actions; transactional `EmailLog` |

### 1.3 Design principles

1. **Layered backend** — `views/` (HTTP) → `serializers/` (validation & IO
   shapes) → `models/` (persistence); cross-cutting concerns isolated in
   `common/`, pure business logic in `services/`. Adding a feature touches one
   module per layer, never a 500-line file.
2. **Domain-oriented modules** — backend and frontend are partitioned along
   the same business domains (auth, applications, review, users, analytics),
   so a full-stack change moves through mirrored structures.
3. **Backend-authoritative, frontend-first validation** — the SPA mirrors
   every backend rule so users never see a server-side form error, and a
   contract test makes silent drift between the layers impossible (§8).
4. **Zero-breakage public APIs** — `kyc/models/__init__.py`,
   `serializers/__init__.py`, and `views/__init__.py` re-export all public
   names; `from kyc.models import KYCApplication` keeps working everywhere
   (admin, commands, tests, migrations). The app label stays `kyc`, so no
   migrations were rewritten.
5. **Fail-closed by default** — throttles, OTP verification, upload sniffing,
   and permission checks are all written to reject on uncertainty.
6. **Explicit dependency flow (frontend)** — `app/` may import `features/`;
   `features/` may import `lib/`, `components/`, `data/`; shared code never
   imports feature code. The `@/` alias keeps imports stable at any depth.

---

## 2. Technology stack

### 2.1 Backend

| Concern | Choice | Rationale |
| --- | --- | --- |
| Runtime | Python ≥ 3.12, Django 6 | LTS-grade framework; built-in auth, migrations, security middleware |
| API | Django REST Framework 3.18 | Serializer/viewset conventions, BrowsableAPI-free pure JSON mode |
| Sessions | SimpleJWT 5.5 | Access/refresh tokens with rotation + server-side blacklist |
| Identity federation | django-allauth 65.x | Google OIDC credential exchange |
| Database | PostgreSQL (psycopg 3) | Relational integrity, GIN/trigram search indexes, single service for data + cache |
| Cache / counters | Django DB cache via `kyc.common.cache.LightweightDatabaseCache` | Atomic upsert cache on Postgres — rate limiting without a Redis service |
| Password hashing | Argon2id (argon2-cffi) | Memory-hard; PBKDF2/Scrypt retained in the hasher stack so legacy hashes verify and transparently upgrade on login |
| Email | Django SMTP backend → Resend relay | `smtp.resend.com` with API-key auth; swappable via `EMAIL_HOST` |
| Phone handling | `phonenumbers` (libphonenumber port) | Canonical E.164 normalisation shared conceptually with the SPA |
| Blocklist data | `disposable-email-domains` | Community-maintained burner-domain list, mirrored to the SPA by a generator script |
| Static files | WhiteNoise | Hashed assets served by gunicorn — no separate static host |
| Lint / format | Ruff (`pyproject.toml`) | One tool for pycodestyle, pyflakes, isort, bugbear, comprehensions |
| App server | Gunicorn | WSGI, non-root Docker user, `entrypoint.sh` bootstraps migrate/cache/static |

### 2.2 Frontend

| Concern | Choice | Rationale |
| --- | --- | --- |
| Framework | React 19 + TypeScript (strict) | Type-safe SPA; `noUnusedLocals`, `noUnusedParameters`, `exactOptional`-style strictness on |
| Build | Vite 8 | Fast dev server, route-level code splitting, hashed production assets |
| Styling | Tailwind CSS 4 | Utility classes compiled at build; no runtime CSS-in-JS |
| Routing | react-router v8 | Direct package import (no legacy `react-router-dom` shim) |
| Google Sign-In | `@react-oauth/google` | Official credential flow, provider mounted once in `app/App.tsx` |
| Phone input | `react-international-phone` + `libphonenumber-js/max` | Country-aware entry; validation uses the strict per-country metadata build |
| Tests | Bun test | Zero-config runner; 38 tests including the drift-guard contract suite |
| Package manager | Bun 1.4 | Lockfile-pinned CI installs (`--frozen-lockfile`) |

### 2.3 Shared

| Concern | Choice | Rationale |
| --- | --- | --- |
| Validation contract | `manage.py validation_contract` → `backend-contract.json` → `contract.test.ts` | Backend emits its rules; the SPA mirror is tested against them (§8) |
| CI | GitHub Actions | Postgres service container, ruff + pip-audit + Django checks; bun test + audit + build |
| Deployment | docker-compose (optional TLS profile) | Postgres 18 + backend + nginx; Caddy edge for ACME certificates |

---

## 3. Deployment topology

### 3.1 Container topology (base compose stack)

```
                    ┌──────────────────────────────┐
                    │        Host (port 8080)      │
                    │  bound to 127.0.0.1 (HTTP)   │
                    └──────────────┬───────────────┘
             ┌─────────────────────┼──────────────────────┐
             │                     ▼                      │
             │            ┌──────────────────┐            │
             │            │   nginx (web)    │            │
             │            │ · SPA static /   │            │
             │            │   hashed assets  │            │
             │            │ · gzip, security │            │
             │            │   headers, cache │            │
             │            │ · limit_req zones│            │
             │            └───┬──────────┬───┘            │
             │     /api,/media│          │ static         │
             │                ▼          │                │
             │      ┌──────────────────┐ │                │
             │      │ backend (gunicorn│ │                │
             │      │ + WhiteNoise)    │ │                │
             │      │ entrypoint:      │ │                │
             │      │  migrate →       │ │                │
             │      │  createcachetable│ │                │
             │      │  → collectstatic │ │                │
             │      └───┬──────────┬───┘ │                │
             │          ▼          ▼     │                │
             │  ┌────────────┐ ┌──────────────┐           │
             │  │ PostgreSQL │ │ media_data   │           │
             │  │ 18-alpine  │ │ volume       │           │
             │  │ app tables │ │ KYC document │           │
             │  │ + cache tbl│ │ files (PII)  │           │
             │  └────────────┘ └──────────────┘           │
             └─────────────────────────────────────────────┘
                        outbound: SMTP (Resend) · Google tokeninfo
```

### 3.2 TLS profile (production edge)

With `--profile tls`, a **Caddy** container terminates 443 with automatic
ACME certificates and proxies to nginx. The chain becomes
`Client → Caddy → nginx → gunicorn`, and the compose overlay sets:

- `DJANGO_SECURE_SSL_REDIRECT=true`, Secure cookies, HSTS (1 year, preload)
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://$SITE_ADDRESS`
- `DJANGO_NUM_PROXIES=2` — IP-keyed throttles read the second-to-last
  `X-Forwarded-For` entry so Caddy+nginx do not collapse all clients into
  nginx's Docker IP

Same-origin by construction: nginx serves the SPA and proxies `/api` and
`/media`, so cookies are first-party and no CORS configuration is required.
Cross-origin deploys (SPA on a CDN) are supported via `CORS_ALLOWED_ORIGINS`
with `re.fullmatch` origin matching.

---

## 4. Backend architecture

### 4.1 Layering and dependency rules

```
            HTTP
             │
   ┌─────────▼──────────┐   config/urls.py routes by prefix:
   │  views/            │   /api/auth/*  /api/applications/*  /api/users/*
   │  auth · applications│  /api/review-queue  /api/analytics  /api/documents
   │  review · users ·   │
   │  analytics          │
   └─────────┬───────────┘
             │ constructs & validates I/O
   ┌─────────▼───────────┐
   │  serializers/       │  fields.py = shared validators (names, phone,
   │  auth · users ·     │  DOB, passwords); auth/users/applications shapes
   │  applications       │
   └─────────┬───────────┘
             │ persists / queries
   ┌─────────▼───────────┐     ┌──────────────────────────────┐
   │  models/            │◀────│  services/  (otp: issue,     │
   │  user · application │     │  request, verify — pure      │
   │  document · audit · │     │  business logic, no HTTP)    │
   │  email_log · email_otp    └──────────────────────────────┘
   └─────────┬───────────┘
             │
   ┌─────────▼──────────────────────────────────────────────┐
   │  common/  middleware · cache · throttles · permissions │
   │  tokens · validators · backends · email_domains ·      │
   │  health · logging                                      │
   └────────────────────────────────────────────────────────┘
```

**Enforced rule:** `views → serializers → models`; any layer may use
`common`/`services`; `common` and `services` never import `views`. This keeps
business rules testable without HTTP and prevents controller creep.

### 4.2 Module responsibilities

| Module | Responsibility |
| --- | --- |
| `common/backends.py` | Authentication backend accepting email **or** phone (with legacy digits-only fallback) |
| `common/cache.py` | `LightweightDatabaseCache` — Postgres-backed cache; replaces the stock backend's per-write full-table scan with one indexed upsert + periodic expiry sweep |
| `common/email_domains.py` | Disposable/temp-mail domain blocklist (package-generated) |
| `common/health.py` | `/healthz` liveness and `/readyz` database readiness probes |
| `common/logging.py` | Log configuration with request-ID correlation |
| `common/middleware.py` | `RequestIDMiddleware` — honours inbound `X-Request-ID` (validated) or mints one; exposed via `get_request_id()` and log filter |
| `common/permissions.py` | `IsReviewer`, `IsSuperAdmin`, `IsCEO`, `IsOwnerOrReviewer` |
| `common/throttles.py` | Atomic fixed-window counters (§6.3) and all scoped throttle classes |
| `common/tokens.py` | HMAC `TimestampSigner` helpers for 15-minute document download tokens |
| `common/validators.py` | Upload content sniffing: extension + magic bytes + size |
| `models/user.py` | Custom `User`: auto-generated public ID as `username`, nullable-unique email/phone, role enum, trigram GIN search indexes |
| `models/application.py` | `KYCApplication` status machine + `apply_review()` guarded transition |
| `models/document.py` | `Document` file model; `post_delete` signal removes the file (PII) on transaction commit |
| `models/audit.py` | `AuditLog` + `log_action()` helper (indexed by actor/time/object) |
| `models/email_log.py` | `EmailLog` for delivery analytics |
| `models/email_otp.py` | `EmailOTP`: HMAC-hashed codes, purpose-scoped, attempt-counted |
| `services/otp.py` | Issue/request/verify lifecycle: code generation, hashing, cooldowns, single-use consumption |
| `views/auth.py` | Register + OTP verify/resend, password reset, cookie JWT login/refresh/logout, Google exchange, `/auth/me/` |
| `views/applications.py` | Applicant CRUD + submit + document upload/delete + signed download + review action |
| `views/review.py` | Reviewer queue listing |
| `views/users.py` | `/auth/me/` profile + super-admin user management (create, password reset, activate, role) |
| `views/analytics.py` | CEO KPIs, approval rate, pipeline counts, email activity |
| `management/commands/` | `seed_demo` (debug-gated demo data), `validation_contract` (§8) |

### 4.3 Request lifecycle

```
client
  │ 1 nginx: TLS? (profile) · gzip · limit_req/limit_conn · security headers
  ▼
  2 gunicorn → Django
  │ 3 RequestIDMiddleware      assign/propagate X-Request-ID
  │ 4 security middleware      SSL redirect, HSTS, CSP, X-Frame, nosniff
  │ 5 CSRF / session / allauth framework checks
  │ 6 CORS (cross-origin deploys; re.fullmatch origin match)
  │ 7 DRF authentication       Bearer access token (stateless JWT)
  │ 8 throttling               scoped rate counters (Postgres cache, atomic)
  │ 9 permission classes       role / ownership gate
  │ 10 serializer validation   typed, bounded input (mirrors SPA rules)
  │ 11 view logic              select_for_update on transitions; AuditLog on writes
  ▼
  12 JSON response · error envelope · Retry-After on 429 · X-Request-ID header
```

### 4.4 Data model

```
┌──────────────────────────┐       ┌───────────────────────────────┐
│ User                     │ 1   * │ KYCApplication                │
│──────────────────────────│──────▶│───────────────────────────────│
│ id (PK)                  │       │ id (PK)                       │
│ username  = public ID    │       │ applicant_id (FK → user)      │
│ email (uniq, null)       │       │ full_name, date_of_birth,     │
│ phone (uniq, null, E.164)│       │ gender, nationality,          │
│ first/middle/last name   │       │ address_line1/2, city, state, │
│ role (4 enum)            │       │ postal_code, country, phone   │
│ is_active, is_staff …    │       │ id_type, id_number, id_expiry │
│ password (Argon2id)      │       │ status (enum, idx)            │
│ date_of_birth, nationality,      │ reviewer_id (FK, null)        │
│ address fields (profile) │       │ decided_at, review_notes      │
│ GIN trigram: names, email│       │ created_at, updated_at        │
└────────┬─────────────────┘       │ idx(applicant,status)         │
         │ 1                       │ idx(status,-created_at)       │
         │                         └──────┬────────────────────────┘
         │ 1     ┌────────────────────────┘ *
         ├──────▶┌───────────────────────────┐
         │       │ Document                  │
         │       │ application_id (FK)       │
         │       │ file → media/documents/…  │
         │       │ doc_type, original_name,  │
         │       │ size_bytes, content_type  │
         │       │ uploaded_at               │
         │       └───────────────────────────┘
         │ *
         ├──────▶┌───────────────────────────┐   ┌───────────────────────────┐
         │       │ EmailOTP                  │   │ AuditLog                  │
         │       │ user_id (FK)              │   │ actor_id (FK, null)       │
         │       │ purpose (signup/reset)    │   │ action (enum), object     │
         │       │ code_hash (HMAC-SHA256)   │   │ type/id, metadata (JSON)  │
         │       │ expires_at, attempts,     │   │ ip, request_id, outcome   │
         │       │ consumed_at               │   │ created_at (idx)          │
         │       │ idx(user, purpose)        │   └───────────────────────────┘
         │       └───────────────────────────┘
         │ *
         └──────▶┌───────────────────────────┐
                 │ EmailLog                  │
                 │ purpose, recipient,       │
                 │ subject, status, error,   │
                 │ created_at (idx desc)     │
                 └───────────────────────────┘
```

Integrity highlights: exactly one identity channel is required at signup
(email XOR phone, but at least one); phone is stored canonical E.164 unique;
public user IDs are generated server-side (`PHIN-XXXXXXXX` style) and never
user-chosen; trigram GIN indexes power admin user search.

### 4.5 Application state machine

```
                    ┌─────────┐  submit (owner, ≥1 doc,
                    │  DRAFT  │  valid non-expired ID) ─────────┐
                    └────┬────┘                                 │
      edit/delete docs   │                                      ▼
      allowed ◀──────────┘                            ┌────────────────────┐
                                                      │     SUBMITTED      │◀────┐
             ┌────────────────────────────────────┐   └─────────┬──────────┘     │
             │ reviewer decision (row-locked,     │             │                │
             │ self-review blocked, notes req.)   │   resubmission_requested    │
             ▼                    ▼               ▼             │   (editable    │
      ┌──────────┐        ┌──────────┐   ┌───────────────────┐    │    again —     │
      │ APPROVED │        │ REJECTED │   │ RESUBMISSION_     │────┘    like draft)│
      └──────────┘        └──────────┘   │ REQUESTED         │                    │
         final               final       └───────────────────┘                    │
                                                                                  │
                                          approve / reject / request_resubmission ┘
```

Transitions are enforced in `KYCApplication.apply_review()` under
`select_for_update`, so concurrent reviewers serialise on the row and the
decision written last is deliberate, not accidental. Only draft and
resubmission-requested applications are editable, and only by their owner.

---

## 5. Domain workflows

### 5.1 Authentication & session management

**Token model.** SimpleJWT with `ACCESS_TOKEN_LIFETIME=1h`,
`REFRESH_TOKEN_LIFETIME=7d`, `ROTATE_REFRESH_TOKENS=true`,
`BLACKLIST_AFTER_ROTATION=true`. The **access token never touches cookies or
localStorage** — it lives in SPA memory only. The **refresh token lives in an
HttpOnly, Secure, SameSite cookie**, invisible to JavaScript.

```
Login:  POST /api/auth/token/ {email|phone, password}
          ├─ Origin header checked (login-CSRF mitigation)
          ├─ LoginThrottle (credential+IP) + LoginIPThrottle (IP)
          ├─ email_not_verified? → 403 {code: email_not_verified}
          └─ 200 {access} + Set-Cookie: refresh (HttpOnly)

Silent refresh (single-flight in the SPA):
          access expired → 401 on any API call
          └─ POST /api/auth/token/refresh/ (cookie only)
               ├─ server rotates: old refresh blacklisted, new cookie issued
               ├─ concurrent 401s share ONE in-flight promise (no stampede,
               │  no double rotation)
               └─ returns {access} to memory

Logout: POST /api/auth/logout/ → refresh blacklisted server-side, cookie cleared
```

Rotation + blacklisting means a stolen refresh cookie is single-use; the
replayed one is rejected and can be detected. A known, accepted residual risk:
password reset does not revoke already-issued JWTs (documented in README).

**Google Sign-In** exchanges the browser's Google ID credential server-side
(`POST /api/auth/google/`) and issues the identical JWT session; Google users
are email-verified by definition.

**Email verification (hard gate).** Registration with an email sends a 6-digit
OTP; login returns `403 email_not_verified` until confirmed. Codes are
generated with `secrets`, stored **only as HMAC-SHA256 keyed with
`SECRET_KEY`** (a DB leak alone cannot brute-force the 10⁶ code space offline),
expire in 10 minutes, allow 5 attempts, are consumed atomically (race-safe
single use), and issuing a new code invalidates the previous one. Request and
resend endpoints always return a generic 200 — no account enumeration — with a
60-second resend cooldown. Password-reset confirmation also marks the email
verified (the code landed in the inbox).

### 5.2 Document pipeline

```
Upload   POST /api/applications/{id}/documents/  (multipart, ≤5 MB)
           ├─ owner + draft/resubmission status required
           ├─ WriteThrottle 30/h/user, per-application cap (10 docs)
           ├─ validate_file_content: extension whitelist
           │   + magic-byte sniff (JPEG/PNG/PDF) + size bound
           ├─ stored under media/documents/<app-id>/<hex>.<ext>
           └─ AuditLog DOCUMENT_UPLOADED

Delete   DELETE …/documents/{doc_id}/  → row deleted;
           post_delete signal removes the file from disk (PII hygiene),
           deferred to on_commit so rollback never orphans/deletes wrongly

Download GET /api/documents/{doc_id}/download/?token=…
           ├─ permission check (owner / reviewer / admin) runs FIRST
           ├─ issues TimestampSigner token (distinct salt), 15-minute TTL
           ├─ token is stateless — no DB round-trip to validate
           └─ response forced to Content-Disposition: attachment
               (kills the in-browser PDF-XSS surface: viewer JS never
                executes with the user's session)
```

### 5.3 User management (super admin)

- Create users with any role; names/emails/passwords validated by the same
  serializers as public signup (and mirrored in the SPA console).
- Password reset issues a strong temporary password; shown once via a modal
  with reveal toggle and strength indicator.
- Deactivation and role changes are guarded: the **last active super admin**
  cannot demote or deactivate themselves (lock is enforced in the view layer).
- Random public-ID collisions are retried rather than surfacing a misleading
  duplicate error.

### 5.4 Analytics (CEO)

`/api/analytics/` aggregates: KPI counts, 30-day submission volume, approval
rate over decided applications, pipeline distribution by status, and 30-day
email activity from `EmailLog`. All counts are index-backed; the endpoint is
cache-friendly and read-only, gated by `IsCEO`.

---

## 6. Cross-cutting concerns

### 6.1 Observability

- **Request correlation:** every request carries an `X-Request-ID` (inbound
  honoured if well-formed, otherwise minted) and is echoed on the response;
  the log filter stamps every line, so a user-reported ID retrieves the full
  server-side trail.
- **Audit trail:** all state changes (submit, decisions, uploads, deletions,
  admin actions) append to `AuditLog` with actor, object, metadata, IP, and
  request ID — queryable per application and per actor.
- **Email delivery record:** every transactional send lands in `EmailLog` with
  success/failure for analytics and debugging.
- **Health probes:** `/healthz` (process alive) and `/readyz` (database
  reachable) for orchestrators.

### 6.2 Error handling contract

DRF's standard envelope (`{field: [messages]}` or `{detail}`) with:
- `429` responses carrying `Retry-After` — the SPA renders the exact wait
- `403 {code: email_not_verified}` — machine-readable so the SPA routes to the
  verify screen instead of showing a dead-end error
- network failures normalised to `ApiError(0)` in the SPA with a friendly message

### 6.3 Rate limiting (two layers)

**Edge (nginx):** `auth` zone 2 r/s per IP (burst 10) on `/api/auth/*`; `api`
zone 20 r/s per IP (burst 40) on `/api|/media`; 30 concurrent connections per
IP. Floods die at the edge without touching Python.

**Application (DRF):** counters in the Postgres-backed cache, shared across
all gunicorn workers. `FixedWindowThrottle` is **atomic and fail-closed**: the
window is created with `cache.add` (wins exactly once under concurrency),
increments run under a lock, and a cache failure counts the request as
exceeded rather than letting it through.

| Scope | Limit | Keyed by | Endpoints |
| --- | --- | --- | --- |
| anon / user | 120/h · 600/h | IP / user | all requests (safety net) |
| register | 5/h | IP | `/auth/register/` |
| login | 10/10 min | credential + IP | `/auth/token/` |
| login_ip | 60/h | IP | `/auth/token/` (all credentials) |
| google_login | 60/h | IP | `/auth/google/` |
| otp request | 5/h | email + IP **and** IP | resend / password-reset request |
| otp_verify | 10/h | IP | verify / reset confirm |
| download | 300/h | IP | document download |
| submit · documents · review | 10/h · 30/h · 60/h | user | writes |

Behind extra proxies set `DJANGO_NUM_PROXIES` so IP keys resolve to the real
client (the TLS profile sets `2` for Caddy→nginx→gunicorn).

---

## 7. Frontend architecture

### 7.1 Module design (feature-sliced)

```
src/
├── main.tsx             entry: mounts App, providers
├── app/                 shell: App.tsx (GoogleOAuthProvider), config.ts,
│                        guards.tsx (RequireAuth/RequireRole), router.tsx
│                        (lazy route table — one chunk per page)
├── features/            vertical slices, each owning pages/components/hooks:
│   ├── auth/            Login, Register (3-step wizard), VerifyEmail,
│   │                    ForgotPassword, GoogleSignInButton, useAuth context
│   ├── applications/    ApplicationForm (blur validation), ApplicationDetail,
│   │                    ApplicationSections (shared read-only rendering)
│   ├── review/          ReviewQueue, ReviewDetail (decision UI)
│   ├── users/           admin console (list, create, password reset modal)
│   ├── analytics/       CEO dashboard (KPI cards, pipeline bars)
│   └── dashboard/       applicant home
├── lib/
│   ├── api/             client.ts + per-domain endpoint modules
│   └── validation.ts    SPA mirror of every backend rule (§8)
├── types/               API DTOs per domain (re-exported via index.ts)
├── components/
│   ├── ui/              design system: Field(+PasswordInput/Select/TextInput),
│   │                    Button, Alert, Modal, Skeleton, Pagination,
│   │                    StatusBadge, PasswordStrength, icons
│   ├── form/            CountrySelect (ISO 3166-1), DateOfBirthInput,
│   │                    PhoneInputField (country-aware E.164)
│   └── layout/          Layout (nav with role-aware links, active state)
├── data/                countries.ts, disposableEmails.ts (generated)
└── hooks/               usePaginatedList (race-guarded page fetching)
```

**Dependency flow (strict):** `app/` → `features/` → `lib/`, `components/`,
`data/`, `hooks/`. Shared code never imports a feature. The `@/` alias
(tsconfig `paths` + Vite `resolve.alias`) removes fragile `../../` chains.

### 7.2 Auth state & token strategy

- `useAuth` context holds the session user; the **access token stays in a
  module-private variable** inside `lib/api/client.ts` — never in storage.
- On 401, `request()` runs a **single-flight refresh** (one shared promise per
  cold-refresh race) and replays the original call once. Auth endpoints
  (login/register/OTP/Google) pass `retry=false` — a failed login must not
  waste a refresh round-trip or throttle budget.
- Boot sequence: try silent refresh → `fetchMe()` → render guarded tree;
  guards redirect unauthenticated users to `/login` and role-mismatched users
  away from reviewer/admin routes.

### 7.3 UX flow architecture

- **Validation on blur, errors on submit** — every field reports the moment it
  loses focus, errors clear as the user types; submit re-validates everything
  and focuses the first problem (see §8).
- **Destructive/irreversible actions get modals** — submit-for-review
  (explains the lock), document delete, user password reset (reveal toggle +
  strength meter + confirm field) — no `window.prompt` anywhere.
- **Loading = skeletons** (tables, cards, detail panes) to prevent layout
  shift; empty states and errors render through the shared `Alert` component.
- **Pagination** is server-driven (`PAGE_SIZE=20`) through `usePaginatedList`,
  which guards against out-of-order responses when the user pages quickly.
- Name inputs auto-capitalize on blur (first letter / each word) mirroring the
  backend normalisation, so the validator never fights the user.

---

## 8. Validation contract

Goal: **users never trigger a backend validation error from the SPA**, while
the backend remains the single authority (API clients, curl, anything that
bypasses the browser must still be defended). Five layers, outermost first:

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. HTML constraints        maxLength/minLength/type from LIMITS   │
│ 2. Blur validators         per-field, same rules as serializers   │
│ 3. Submit validation       validateApplication() full pass        │
│ 4. Backend serializer      authority + safety net (API clients)   │
│ 5. DB constraints          uniques, FKs, row locks (last resort)  │
└──────────────────────────────────────────────────────────────────┘
```

**Drift guard.** The backend is the source of truth:

1. `python manage.py validation_contract` introspects models/serializers/
   settings and emits `frontend/src/lib/backend-contract.json`.
2. The committed JSON is compared against `lib/validation.ts` constants
   (`LIMITS`, `DOB_MIN_ISO`, `OTP_LENGTH`, `PASSWORD_MIN_LENGTH`,
   `MAX_FILE_SIZE_MB`, `ALLOWED_FILE_EXTENSIONS`, `APPLICATION_ID_TYPES`) by
   `contract.test.ts` — part of `bun test`, so CI fails if either side changes
   without the other.
3. No inline literals: forms bind `maxLength={LIMITS.x}` etc.; a grep for
   hardcoded limits finds nothing.

**Change protocol:** edit the backend rule → regenerate the contract
(`python manage.py validation_contract > ../frontend/src/lib/backend-contract.json`)
→ update `validation.ts` constants → run `bun test`; the contract test flags
anything missed. Backend-only integrity rules (expired-ID submission block,
review concurrency) intentionally have no SPA mirror — the SPA warns early
(live expired-ID indicator) and the backend enforces definitively.

---

## 9. Security architecture

### 9.1 Defence in depth

```
Edge      nginx/TLS         TLS termination · security headers · rate zones ·
                            body-size cap (client_max_body_size 6m)
App       Django            CSP · HSTS · nosniff · frame-deny · SSL redirect ·
                            CSRF middleware · Origin checks on cookie endpoints
Session   JWT               memory-only access token · rotating HttpOnly
                            refresh cookie · blacklist after rotation
AuthZ     DRF permissions   role classes + object ownership on every queryset
Input     serializers       typed, bounded, normalised (E.164, names, DOB)
Files     validators        extension + magic bytes + size · attachment-only
                            download · expiring signed URLs
Abuse     throttles         atomic fail-closed counters, per credential/IP/user
Data      Postgres          uniques, FKs, row-locked transitions, audit trail
```

### 9.2 Threat → mitigation map

| Threat | Mitigation |
| --- | --- |
| Token theft via XSS | Access token memory-only; refresh token HttpOnly (unreadable by JS); strict CSP (`default-src self`, `frame-ancestors none`, no external script origins) |
| Login CSRF / forced logout | `Origin` header validation on all cookie-authenticated endpoints |
| Refresh replay | Rotation + blacklist: an used refresh token is dead the moment it is exchanged |
| Brute-force / credential stuffing | Per-credential **and** per-IP login throttles; nginx edge zones; generic error messages |
| Account enumeration | OTP request/resend endpoints return generic 200; registration doesn't reveal existing accounts |
| OTP brute-force | 6-digit code, 5 attempts, 10-minute expiry, HMAC-hashed at rest, verify throttle 10/h/IP |
| Offline OTP cracking after DB leak | Codes stored HMAC-SHA256 keyed by `SECRET_KEY`, not plain SHA-256 (10⁶ space is not brute-forceable without the key) |
| Disposable/temp-mail signups | Package-generated domain blocklist enforced identically on both tiers |
| Malicious upload (polyglot, spoofed MIME) | Magic-byte sniffing independent of client `Content-Type`; extension whitelist; 5 MB cap; per-application doc cap |
| PDF/viewer XSS | Downloads forced to `Content-Disposition: attachment`; files served only same-origin via signed URL |
| Document link sharing | Signed URLs expire in 15 minutes; permission check precedes issuance |
| IDOR on applications/documents | Querysets scoped by owner/reviewer role; object-level permission checks |
| Self-approval fraud | Review action rejects `reviewer == applicant` |
| Privilege-lockout / rogue admin | Last-active-super-admin guard; role changes audited |
| PII persistence after delete | File removed from disk on `post_delete` (post-commit) |
| SQL injection | ORM-only queries; no raw SQL |
| Clickjacking / MIME sniffing | `X-Frame-Options DENY`, `X-Content-Type-Options nosniff` |
| Forgeable secrets | Compose refuses boot without a 50+ char `DJANGO_SECRET_KEY` (JWTs and signed tokens derive from it); weak/short keys rejected in production mode |
| Cache-failure fail-open | Throttle counters fail **closed** — an unhealthy cache blocks, never bypasses |

### 9.3 Security posture notes

- Argon2id password hashing with transparent legacy-hash upgrades.
- `SECURE_HSTS` (1 year, includeSubDomains, preload) under TLS.
- Accepted risks are documented (e.g., password reset does not revoke live
  JWTs) — see README security notes and the audit doc.
- `seed_demo` refuses to run unless `DJANGO_DEBUG=true`; well-known demo
  credentials can never exist in production.

---

## 10. Testing & CI

### 10.1 Test portfolio

| Suite | Count | Scope |
| --- | --- | --- |
| Backend (`manage.py test kyc`) | 124 | auth + OTP + Google exchange, application lifecycle, uploads/downloads, permissions/access matrix, user management, analytics, throttles, cache backend, middleware, seed, validation contract |
| Frontend (`bun test`) | 38 | validator units (mirror of backend rules), capitalisation helpers, contract drift guard |

Backend tests run against a real PostgreSQL (never SQLite) so JSONB, trigram
indexes, and locking semantics are exercised honestly. Shared fixtures live in
`tests/utils.py`.

### 10.2 CI pipeline (GitHub Actions)

```
backend job                          frontend job
  postgres:18 service container        bun install --frozen-lockfile
  pip install -r requirements.txt      bun test            (incl. contract test)
  ruff check . && ruff format --check  bun audit --omit=dev
  pip-audit --strict                   bun run build       (tsc -b + vite)
  manage.py check
  manage.py test kyc
```

Every push to `main` and every PR runs both jobs; the contract test means a
backend rule change without a corresponding SPA mirror **fails CI**, not
production.

---

## 11. Deployment & operations

### 11.1 Environments

| Mode | Stack | Notes |
| --- | --- | --- |
| Local dev | runserver + Vite dev server | Vite proxies `/api`,`/media` → `:8000`; console email backend |
| Self-hosted (HTTP) | compose: Postgres + gunicorn + nginx | binds `127.0.0.1:8080` only — not network-reachable |
| Production (TLS) | + Caddy edge (ACME) | Secure cookies, HSTS, CSRF origin, `DJANGO_NUM_PROXIES=2` |
| Any Docker host | `backend/Dockerfile` standalone | point `DATABASE_URL` at managed Postgres |

### 11.2 Operational runbook highlights

- **Bootstrapping:** `entrypoint.sh` runs `migrate → createcachetable →
  collectstatic` before gunicorn; the cache table is mandatory (throttles and
  OTP cooldowns live there).
- **Backups:** `pg_dump` on a schedule + `media_data` volume copy (KYC
  documents are PII; treat backups with the same sensitivity).
- **Secrets:** all via environment (see README variable tables); compose
  refuses defaults; `.env` is git-ignored and never committed.
- **Migrations:** regular Django migrations (checked in CI via `manage.py
  check`); no manual SQL.
- **Scaling notes:** stateless gunicorn workers (session state = JWT + DB);
  the cache/counters are already worker-shared via Postgres, so horizontal
  app scaling needs no sticky sessions; add read replicas before the review
  queue grows; edge zones move to the LB tier when load-balancing.
- **Volume map:** `pg_data` (database), `media_data` (`/app/media` — identity
  documents).

---

## 12. Key architecture decisions

| # | Decision | Rationale |
| --- | --- | --- |
| 1 | Postgres as the **only** datastore (data + cache + counters) | One service to back up and operate; rate limiting stays atomic without Redis |
| 2 | Refresh token in HttpOnly cookie, access in memory | XSS cannot steal a session even if it runs |
| 3 | Signed stateless download tokens (15 min) | No download-session table; permission check at issuance only |
| 4 | Atomic fixed-window throttles, fail-closed | Correct under concurrent bursts; an unhealthy cache blocks rather than bypasses |
| 5 | OTP codes HMAC-hashed with `SECRET_KEY` | DB leak alone cannot recover codes |
| 6 | Frontend-first validation with an emitted contract | Best UX and drift-proof; backend stays authoritative |
| 7 | Domain-sliced modules on both tiers | Full-stack changes move through mirrored structures |
| 8 | `select_for_update` on every review transition | Concurrent decisions serialise; last write is deliberate |
| 9 | Audit log for all state changes | Regulatory traceability per application, actor, and request |
| 10 | Row-level `GinIndex` trigram search on users | Fast admin search without a search engine |

---

## 13. Extension guide

**New backend domain:** model module in `models/` → re-export in
`models/__init__.py` → serializer module in `serializers/` (+ shared field
validators in `serializers/fields.py`) → viewset/view in `views/` → routes in
`urls.py` → tests in `tests/test_<domain>.py` → re-export in
`serializers/__init__.py` / `views/__init__.py`.

**New frontend domain:** `features/<name>/` with pages/components → endpoint
module under `lib/api/` + DTOs under `types/` → lazy route in
`app/router.tsx` (+ guard if role-gated) → validators mirrored in
`lib/validation.ts`.

**Changed a limit or rule?** Backend first → regenerate the contract → update
`validation.ts` → `bun test` catches anything missed.

**New throttled endpoint:** pick/extend a scope in `common/throttles.py`, set
`throttle_scope` on the view, add the nginx zone if it needs edge protection.

**New role:** extend `User.Role`, add a permission class in
`common/permissions.py`, guard routes in `app/guards.tsx`, and decide its
place in the authorization matrix (README API table).
