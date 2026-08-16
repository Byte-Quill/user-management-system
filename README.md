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
browsers can open files in a new tab without sending the JWT.

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
- Login and registration are rate-limited (counters shared across workers
  via the Postgres-backed database cache).

---

## API endpoints

| Method | Endpoint                                     | Auth | Role                          | Description                          |
| ------ | -------------------------------------------- | ---- | ----------------------------- | ------------------------------------ |
| POST   | `/api/auth/register/`                        | ❌   | —                             | Register applicant                   |
| POST   | `/api/auth/token/`                           | ❌   | —                             | Login → access token + refresh cookie |
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

Document uploads are validated for extension (jpg/jpeg/png/pdf), declared
content type, magic-byte content, and size (≤ 5 MB). Document downloads use
one-hour signed URLs issued only to users who pass the ownership/role
permission checks, so files can be opened in a new tab without the JWT.

---

## Frontend routes

| Route               | Page                    | Purpose                          |
| ------------------- | ----------------------- | -------------------------------- |
| `/`                 | `DashboardPage`         | Role-based overview              |
| `/login`            | `LoginPage`             | Email/password login             |
| `/register`         | `RegisterPage`          | New applicant registration       |
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
| `CUSTOM_DOMAIN`               | ❌       | Optional extra CORS origin                     |

Documents are stored under `media/documents/` (mount a persistent volume at
`/app/media` in production) and served through the signed download endpoint.

### Frontend

| Variable       | Required | Description                          |
| -------------- | -------- | ------------------------------------ |
| `VITE_API_URL` | ❌       | Backend base URL when the SPA is served from a different origin; leave unset for same-origin deploys (uses `/api`) |

---

## Local development

### Prerequisites

- Python ≥ 3.12, Node ≥ 20, PostgreSQL (or use SQLite for quick experiments)

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
python manage.py test kyc           # 24 tests: auth, flow, uploads, downloads, permissions, admin
```

---

## Deployment

### Self-hosted (docker-compose) — recommended, $0

The whole stack (PostgreSQL + backend + nginx) runs from open-source images:

```bash
cd backend
docker compose up --build
# open http://localhost:8080
```

- nginx serves the SPA and proxies `/api` + `/media` to the backend, so the
  deployment is same-origin: no CORS configuration needed.
- Documents persist in the `media_data` volume; the database in `pg_data`.
- For production: set a strong `DJANGO_SECRET_KEY`, put TLS in front (e.g.
  Caddy), and back up both volumes (`pg_dump` + volume copy).

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
- Uploads are validated by extension, MIME type, magic bytes, and size.
- Deleting a `Document` also deletes the file from disk (PII).
- Document downloads require a one-hour signed token issued only after the
  ownership/role permission checks pass.
- Login/register endpoints are throttled via Postgres-backed cache counters.

---

## License

MIT — free to use, modify, distribute.
