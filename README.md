# KYC Application Verification System

A full-stack KYC (Know Your Customer) application and review system built on
a **100% free and open-source stack** — no paid services, no vendor lock-in.

- **Backend:** Django 6 + Django REST Framework + SimpleJWT (Python ≥ 3.12)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS 4 (SPA)
- **Database:** PostgreSQL (self-hosted, e.g. via the included docker-compose)
- **File storage:** local `media/` volume, served through an authenticated,
  time-limited signed download URL
- **Cache / rate limiting:** Django's database cache (Postgres-backed) — no
  Redis service required. Uses an optimized backend
  (`kyc.cache.LightweightDatabaseCache`) that replaces the stock backend's
  per-write full-table scan with a single indexed upsert and periodically
  sweeps expired rows.
- **Deployment:** docker-compose (Postgres + backend + nginx) or any Docker host

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    nginx (web)                       │
│   SPA static files  +  /api, /media proxy            │
└──────────────┬───────────────────────────────────────┘
               │ same origin (no CORS)
        ┌──────▼──────────────────────────────┐
        │             Backend                 │
        │  Django 6 + DRF + SimpleJWT         │
        │  gunicorn + WhiteNoise              │
        └──────┬─────────────────┬────────────┘
               │                 │
        ┌──────▼─────┐    ┌──────▼──────────┐
        │ PostgreSQL │    │ media/ volume   │
        │ (db)       │    │ KYC documents   │
        │ + cache    │    └─────────────────┘
        │   tables   │
        └────────────┘
```

Documents are served by the backend through a permission-checked endpoint
that issues one-hour signed download URLs (Django `TimestampSigner`), so
browsers can download files without sending the JWT. Files are served with
`Content-Disposition: attachment` — they are served on the app origin, and
forcing a download prevents in-browser PDF JavaScript from running with the
viewer's session.

---

## Project structure

```
user-management-system/
├── backend/                    # Django project
│   ├── config/                 # settings, urls, wsgi
│   ├── kyc/                    # main app
│   │   ├── models.py           # User, KYCApplication, Document, AuditLog,
│   │   │                       # audit logging + signed download tokens
│   │   ├── views.py            # applications, documents, review, audit
│   │   ├── auth_views.py       # cookie-based JWT login/refresh/logout
│   │   ├── serializers.py      # DRF serializers (signed URLs for documents)
│   │   ├── access.py           # role/ownership permissions + throttles
│   │   ├── middleware.py       # request-ID middleware
│   │   ├── cache.py            # Postgres-backed cache backend
│   │   ├── health.py           # /healthz and /readyz probes
│   │   ├── management/commands/
│   │   │   └── seed_demo.py            # demo users + sample data
│   │   └── migrations/
│   ├── Dockerfile              # python:3.13-slim image
│   ├── docker-compose.yml      # self-hosted stack: Postgres + backend + nginx
│   ├── pyproject.toml          # ruff lint/format config
│   ├── entrypoint.sh
│   └── requirements.txt
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── api.ts              # fetch wrapper, in-memory access token,
│   │   │                       # single-flight cookie refresh
│   │   ├── auth.tsx            # auth context
│   │   ├── types.ts            # types matching the backend API
│   │   ├── components/         # Layout, Field, Pagination, StatusBadge,
│   │   │                       # ApplicationSections (details/docs/audit)
│   │   ├── hooks/              # usePaginatedList
│   │   └── pages/              # Dashboard, ApplicationForm/Detail,
│   │                           # ReviewQueue/Detail, Login, Register
│   ├── Dockerfile              # nginx static image (also proxies /api)
│   ├── nginx.conf
│   └── package.json
└── README.md
```

---

## Data model

```
User (custom, email = USERNAME_FIELD)
  ├── username: auto-generated public User ID (PHIN-XXXXXXXX, never user-chosen)
  ├── first/middle/last name, gender, phone (unique, canonical +digits form)
  ├── role: applicant | reviewer | admin
  └── 1:N KYCApplication (as applicant)

KYCApplication
  ├── applicant → User
  ├── status: draft | submitted | approved | rejected | resubmission_requested
  ├── personal + address + ID fields (typed columns)
  ├── reviewer → User (nullable), review_notes, reviewed_at
  ├── 1:N Document
  └── 1:N AuditLog

Document
  ├── application → KYCApplication
  ├── doc_type: id_proof | address_proof | selfie
  ├── file (FileField) — stored in MEDIA_ROOT (media/ volume)
  └── original_filename, uploaded_at

AuditLog
  ├── application → KYCApplication, actor → User
  ├── action: created | updated | submitted | document_uploaded |
  │           document_removed | approved | rejected | resubmission_requested
  └── detail, created_at
```

---

## Application lifecycle

```
draft ──submit──► submitted ──approve──► approved
  ▲                   │
  │                   ├──reject──► rejected
  │                   │
  └──edit & resubmit──┴──request_resubmission──► resubmission_requested
```

- Submitting requires at least one supporting document.
- Only `submitted` applications can be reviewed; reviews are applied inside a
  `select_for_update()` transaction so concurrent reviews cannot race.
- Every state change and document operation writes an `AuditLog` row.

---

## Authentication

- **Access token** (short-lived JWT): returned in the response body, kept in
  memory in the SPA only — never in `localStorage`.
- **Refresh token** (7 days): set as an `HttpOnly; Secure; SameSite` cookie.
  JavaScript cannot read it, so XSS cannot steal it.
- Refresh **rotates** the token and blacklists the old one
  (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`); the frontend
  single-flights concurrent refreshes so rotation never invalidates the
  session.
- Cookie-authenticated endpoints validate the `Origin` header against the
  configured CORS origins as CSRF protection.
- Rate limiting is enforced in two layers (see below); counters are shared
  across all gunicorn workers via the Postgres-backed database cache.

### Google Sign-In (optional)

Set `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend build)
to the same OAuth "Web application" client ID from Google Cloud Console to
enable it; leave unset to disable. The SPA's Google button posts the OIDC ID
token to `POST /api/auth/google/`, where django-allauth's Google provider
verifies it (signature against Google's public keys, issuer, audience, expiry,
and `jti` replay via the cache). The local user is then resolved or
provisioned and issued the **same** JWT session as password login (access
token in the body, refresh token in the HttpOnly cookie) — no Django session
is created.

Account resolution order:

1. An existing `SocialAccount` for `(google, uid)` → its user.
2. An existing local user with the same Google-verified email → linked
   (Google proved ownership of the email). Refused if that user already has a
   *different* Google identity linked.
3. Otherwise a new applicant is created with an unusable password.

Google accounts are always created as `applicant`; the ID token must carry a
verified email, and inactive users are rejected. The endpoint is
Origin-checked (login-CSRF) and per-IP throttled like password login.

### Email verification & password reset (Resend)

Signup is **hard-verified**: registration emails a 6-digit OTP (via the
Resend HTTP API, `kyc/email.py`) and password login returns `403` with
`code: email_not_verified` until the user confirms it at
`POST /api/auth/verify-email/`. Users who existed before this feature shipped
were grandfathered as verified by migration 0010; Google users are verified
by definition (Google proved ownership), and staff can verify manually in the
admin. Forgot-password (`/api/auth/password-reset/request/` + `/confirm/`)
works for any account — including Google-only users setting their first
password — and confirming a reset also marks the email verified (the code
arrived in the account's inbox).

OTP security: codes come from `secrets`, are stored only as SHA-256 hashes,
expire after 10 minutes, allow 5 attempts, are single-use, and issuing a new
code invalidates the previous one. Request/resend endpoints always return a
generic 200 (no account enumeration) and are throttled per email+IP (5/hour)
with a 60-second resend cooldown.

Set `RESEND_API_KEY` and a verified `DEFAULT_FROM_EMAIL` in production. Note:
with an *unverified* domain Resend only delivers from `onboarding@resend.dev`
to the account owner's own inbox — verify a domain first. Accepted risk: a
password reset does not revoke already-issued JWTs (access 1h / refresh 7d).

### Rate limiting

**Edge layer (nginx)** — drops floods before they reach Django:

| Zone   | Applies to            | Limit                          |
| ------ | --------------------- | ------------------------------ |
| `auth` | `/api/auth/*`         | 2 req/s per IP (burst 10)      |
| `api`  | `/api/*`, `/media/*`  | 20 req/s per IP (burst 40)     |
| conn   | whole server          | 30 concurrent connections / IP |

**Application layer (DRF)** — counters in the Postgres-backed cache, shared
across workers; throttled responses return `429` with a `Retry-After` header:

| Scope      | Limit      | Keyed by            | Endpoints                          |
| ---------- | ---------- | ------------------- | ---------------------------------- |
| `anon`     | 120/hour   | IP                  | any unauthenticated request        |
| `user`     | 600/hour   | user                | any authenticated request          |
| `register` | 5/hour     | IP                  | `POST /api/auth/register/`         |
| login      | 10/10 min  | email + IP          | `POST /api/auth/token/`            |
| `login_ip` | 60/hour    | IP                  | `POST /api/auth/token/` (all emails) |
| `google_login` | 60/hour | IP                 | `POST /api/auth/google/`           |
| otp request | 5/hour    | email + IP          | `POST /api/auth/verify-email/resend/`, `/api/auth/password-reset/request/` |
| `otp_verify` | 10/hour  | IP                  | `POST /api/auth/verify-email/`, `/api/auth/password-reset/confirm/` |
| `download` | 300/hour   | IP                  | `GET /api/documents/{id}/download/` |
| `submit`   | 10/hour    | user                | `POST /api/applications/{id}/submit/` |
| `documents`| 30/hour    | user                | `POST /api/applications/{id}/documents/` |
| `review`   | 60/hour    | user                | `POST /api/applications/{id}/review/` |

Login is bounded two ways: per credential (email + IP) to stop a single
account being stuffed, and per IP to stop one address rotating through many
accounts. Behind an extra load balancer, set `DJANGO_NUM_PROXIES` so
IP-keyed throttles read the correct `X-Forwarded-For` entry. The SPA shows
the `Retry-After` wait time when it receives a 429.

---

## API endpoints

| Method | Endpoint                                     | Auth | Role                          | Description                          |
| ------ | -------------------------------------------- | ---- | ----------------------------- | ------------------------------------ |
| POST   | `/api/auth/register/`                        | ❌   | —                             | Register applicant (names, email, phone, gender); emails a verification OTP |
| POST   | `/api/auth/verify-email/`                    | ❌   | —                             | Confirm signup OTP → unlocks login   |
| POST   | `/api/auth/verify-email/resend/`             | ❌   | —                             | Resend signup OTP (60s cooldown; generic 200) |
| POST   | `/api/auth/password-reset/request/`          | ❌   | —                             | Email a password-reset OTP (generic 200) |
| POST   | `/api/auth/password-reset/confirm/`          | ❌   | —                             | Consume reset OTP → set new password |
| POST   | `/api/auth/token/`                           | ❌   | —                             | Login (email **or phone**) → access token + refresh cookie |
| POST   | `/api/auth/google/`                          | ❌   | —                             | Google Sign-In → same JWT session    |
| POST   | `/api/auth/token/refresh/`                   | ❌   | —                             | Rotate refresh cookie → new access   |
| POST   | `/api/auth/logout/`                          | ❌   | —                             | Blacklist refresh token, clear cookie |
| GET    | `/api/auth/me/`                              | ✅   | Any                           | Current user profile                 |
| GET    | `/healthz`                                   | ❌   | —                             | Liveness probe                       |
| GET    | `/readyz`                                    | ❌   | —                             | Readiness probe (database)           |
| GET    | `/api/applications/`                         | ✅   | Applicant: own; Reviewer/Admin: all | List applications (paginated)  |
| POST   | `/api/applications/`                         | ✅   | Applicant                     | Create draft application             |
| GET    | `/api/applications/{id}/`                    | ✅   | Owner / Reviewer / Admin      | Application detail                   |
| PATCH  | `/api/applications/{id}/`                    | ✅   | Applicant (draft only)        | Update draft                         |
| POST   | `/api/applications/{id}/submit/`             | ✅   | Applicant                     | Submit for review                    |
| POST   | `/api/applications/{id}/documents/`          | ✅   | Applicant                     | Upload document                      |
| GET    | `/api/documents/{doc_id}/download/`          | ❌   | Signed token                | Download document (1-hour signed URL) |
| DELETE | `/api/applications/{id}/documents/{doc_id}/` | ✅   | Applicant                     | Delete document (file removed too)   |
| POST   | `/api/applications/{id}/review/`             | ✅   | Reviewer / Admin              | approve / reject / request_resubmission |
| GET    | `/api/applications/{id}/audit/`              | ✅   | Owner / Reviewer / Admin      | Audit trail (paginated)              |
| GET    | `/api/review-queue/`                         | ✅   | Reviewer / Admin              | Pending review queue                 |

Document uploads are validated for extension (jpg/jpeg/png/pdf), magic-byte
content, and size (≤ 5 MB). Document downloads use one-hour signed URLs
issued only to users who pass the ownership/role permission checks, so files
can be downloaded without the JWT (served as attachments, see above).

---

## Frontend routes

| Route               | Page                    | Purpose                          |
| ------------------- | ----------------------- | -------------------------------- |
| `/`                 | `DashboardPage`         | Role-based overview              |
| `/login`            | `LoginPage`             | Email/phone + password login, forgot-password link |
| `/register`         | `RegisterPage`          | Registration (names, email, phone, gender, Google) |
| `/verify-email`     | `VerifyEmailPage`       | Confirm the signup OTP (resend w/ cooldown) |
| `/forgot-password`  | `ForgotPasswordPage`    | Email → OTP → new password wizard |
| `/applications/new` | `ApplicationFormPage`   | Create/edit application          |
| `/applications/:id` | `ApplicationDetailPage` | View, upload docs, submit        |
| `/review`           | `ReviewQueuePage`       | Reviewer queue                   |
| `/review/:id`       | `ReviewDetailPage`      | Review decision                  |

---

## Environment variables

### Backend

| Variable                      | Required | Description                                    |
| ----------------------------- | -------- | ---------------------------------------------- |
| `DJANGO_SECRET_KEY`           | ✅       | 50+ char random string                         |
| `DJANGO_DEBUG`                | ✅       | `true` / `false`                               |
| `DJANGO_ALLOWED_HOSTS`        | ✅       | Comma-separated hosts                          |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | ✅       | Comma-separated HTTPS origins                  |
| `DATABASE_URL`                | ✅       | PostgreSQL connection string (any instance)    |
| `CORS_ALLOWED_ORIGINS`        | ❌       | Frontend URL(s) when served cross-origin; not needed for same-origin deploys |
| `DJANGO_SECURE_SSL_REDIRECT`  | ❌       | `false` when TLS terminates at a proxy that already forces HTTPS (default `true` in prod) |
| `DJANGO_NUM_PROXIES`          | ❌       | Proxy hops in front of gunicorn for IP-keyed rate limits (default `1` = nginx) |
| `CUSTOM_DOMAIN`               | ❌       | Optional extra CORS origin                     |
| `GOOGLE_CLIENT_ID`            | ❌       | Google OAuth client ID; enables Google Sign-In (unset = disabled) |
| `RESEND_API_KEY`              | ✅ prod  | Resend API key for transactional email (signup/reset OTPs); unset = console backend in DEBUG only |
| `DEFAULT_FROM_EMAIL`          | ❌       | Verified sender address, e.g. `Login Portal <noreply@yourdomain.com>` |
| `EMAIL_BACKEND`               | ❌       | Override the Django email backend (default: Resend in prod, console in DEBUG) |

Documents are stored under `media/documents/` (mount a persistent volume at
`/app/media` in production) and served through the signed download endpoint.

### Frontend

| Variable       | Required | Description                          |
| -------------- | -------- | ------------------------------------ |
| `VITE_API_URL` | ❌       | Backend base URL when the SPA is served from a different origin; leave unset for same-origin deploys (uses `/api`) |

---

## Local development

### Prerequisites

- Python ≥ 3.12, Node ≥ 20, PostgreSQL

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# create backend/.env with DATABASE_URL etc. (see backend/.env.example)
python manage.py migrate
python manage.py createcachetable   # cache tables for throttling
python manage.py seed_demo          # optional demo users + data
python manage.py runserver          # http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
# Vite proxies /api and /media to localhost:8000
```

### Demo accounts (after `seed_demo`)

| Role      | Email              | Password   |
| --------- | ------------------ | ---------- |
| Admin     | admin@kyc.local    | Admin@123  |
| Reviewer  | reviewer@kyc.local | Review@123 |
| Applicant | user@kyc.local     | User@123   |

### Tests

```bash
cd backend
python manage.py test kyc           # 71 tests: auth, email OTP, Google Sign-In, flow, uploads, downloads, permissions, admin
```

Security posture and audit history: [docs/security-audit-2026-08-16.md](docs/security-audit-2026-08-16.md).

---

## Deployment

### Self-hosted (docker-compose) — recommended, $0

The whole stack (PostgreSQL + backend + nginx) runs from open-source images:

```bash
cd backend
export DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
docker compose up --build
# open http://localhost:8080
```

- Compose refuses to start without a strong `DJANGO_SECRET_KEY` (50+ chars):
  JWTs and signed download tokens are derived from it, so a known default
  would make them forgeable. `POSTGRES_PASSWORD` is likewise mandatory.

- nginx serves the SPA and proxies `/api` + `/media` to the backend, so the
  deployment is same-origin: no CORS configuration needed.
- The base stack is plain HTTP and binds to `127.0.0.1:8080` only — it is
  not reachable from the network, so cleartext cookies/PII cannot leak if
  the host is exposed. Remote access requires the TLS profile below.
- Documents persist in the `media_data` volume; the database in `pg_data`.
- For production: use the TLS profile below, and back up both volumes
  (`pg_dump` + volume copy).

#### TLS (production)

The base stack serves plain HTTP — fine for localhost, not for the internet.
The `tls` profile adds a Caddy edge with automatic ACME certificates and
switches Django to HTTPS mode (Secure cookies, HSTS, SSL redirect):

```bash
cd backend
export SITE_ADDRESS=kyc.example.com
export DJANGO_ALLOWED_HOSTS=kyc.example.com
docker compose --profile tls -f docker-compose.yml -f docker-compose.tls.yml up --build
```

Caddy terminates TLS on 80/443; the plain-HTTP nginx container is bound to
`127.0.0.1` only. The profile also sets `DJANGO_NUM_PROXIES=2`
(Caddy → nginx → backend) so IP-keyed rate limits still see the real client
address. For local HTTPS testing set `SITE_ADDRESS=localhost`
(Caddy uses its internal CA). If you terminate TLS with your own proxy
instead, keep `DJANGO_SECURE_SSL_REDIRECT=false` only if that proxy already
forces HTTPS and forwards `X-Forwarded-Proto`.

### Any Docker host

The backend can also run standalone from `backend/Dockerfile`
(`python:3.13-slim`, non-root user, `entrypoint.sh` runs `migrate`,
`createcachetable`, and `collectstatic` before starting gunicorn). Point
`DATABASE_URL` at any reachable PostgreSQL instance.

### Frontend

Build the SPA and serve it statically:

```bash
cd frontend
VITE_API_URL=https://api.example.com npm run build   # cross-origin deploys only
```

`frontend/Dockerfile` builds the app and serves `dist/` with nginx
(SPA fallback, hashed-asset caching, gzip, security headers,
`client_max_body_size 6m`, `/api` + `/media` proxy for same-origin deploys).

---

## Security notes

- Refresh tokens live in HttpOnly cookies; access tokens in memory only.
- Cookie-authenticated endpoints check the `Origin` header (CSRF mitigation).
- Django 6's built-in CSP middleware is enabled via `SECURE_CSP`; plus
  `X-Frame-Options`, `X-Content-Type-Options`, HSTS, and secure cookies.
- Uploads are validated by extension, magic bytes, and size.
- Deleting a `Document` also deletes the file from disk (PII).
- Document downloads require a 15-minute signed token issued only after the
  ownership/role permission checks pass.
- Two-layer rate limiting: nginx `limit_req`/`limit_conn` zones at the edge,
  plus DRF throttles (anon/user safety nets, login/register/download caps,
  per-user write scopes) backed by Postgres cache counters; 429 responses
  carry a `Retry-After` header.

---

## License

MIT — free to use, modify, distribute.
