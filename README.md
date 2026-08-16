# KYC Application Verification System

A full-stack KYC (Know Your Customer) application and review system.

- **Backend:** Django 6 + Django REST Framework + SimpleJWT (Python ≥ 3.12)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS 4 (SPA)
- **Database:** PostgreSQL (Supabase) via `DATABASE_URL`
- **File storage:** Supabase Storage (private bucket, signed URLs) with local
  `media/` fallback
- **Cache / rate limiting:** Redis (required in production)
- **Deployment:** Render (backend + Redis) and any static host or the included
  nginx Docker image (frontend)

---

## Architecture

```
┌──────────────┐        ┌──────────────────────────────┐
│   Frontend   │  /api  │           Backend            │
│  React SPA   │ ─────► │  Django 6 + DRF + SimpleJWT  │
│  (Vite)      │        │  gunicorn + WhiteNoise       │
└──────────────┘        └──────┬──────────────┬────────┘
                               │              │
                        ┌──────▼─────┐  ┌─────▼──────────┐
                        │ PostgreSQL │  │ Supabase       │
                        │ (Supabase) │  │ Storage bucket │
                        └────────────┘  └────────────────┘
                               ▲
                        ┌──────┴─────┐
                        │   Redis    │  throttling, JWT blacklist,
                        └────────────┘  signed-URL cache
```

---

## Project structure

```
user-management-system/
├── backend/                    # Django project
│   ├── config/                 # settings, urls, wsgi/asgi
│   ├── kyc/                    # main app
│   │   ├── models.py           # User, KYCApplication, Document, AuditLog
│   │   ├── views.py            # applications, documents, review, audit
│   │   ├── auth_views.py       # cookie-based JWT login/refresh/logout
│   │   ├── serializers.py      # DRF serializers (signed URLs for documents)
│   │   ├── permissions.py      # role + ownership permissions
│   │   ├── supabase_client.py  # thin REST client for Supabase Storage
│   │   ├── middleware.py       # request-ID middleware
│   │   ├── throttles.py        # login/register rate limits
│   │   ├── health.py           # /healthz and /readyz probes
│   │   ├── management/commands/
│   │   │   ├── seed_demo.py            # demo users + sample data
│   │   │   └── migrate_to_postgres.py  # one-off SQLite → Postgres copy
│   │   └── migrations/
│   ├── Dockerfile              # python:3.13-slim image
│   ├── entrypoint.sh
│   └── requirements.txt
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── api.ts              # fetch wrapper, in-memory access token,
│   │   │                       # single-flight cookie refresh
│   │   ├── auth.tsx            # auth context
│   │   ├── types.ts            # types matching the backend API
│   │   ├── components/         # Layout, Field, Pagination, StatusBadge
│   │   ├── hooks/              # usePaginatedList
│   │   └── pages/              # Dashboard, ApplicationForm/Detail,
│   │                           # ReviewQueue/Detail, Login, Register
│   ├── Dockerfile              # nginx static image
│   ├── nginx.conf
│   └── package.json
├── supabase/README.md          # Supabase setup guide
└── render.yaml                 # Render blueprint (backend + Redis)
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
  ├── file (FileField) — local storage
  ├── storage_path — Supabase Storage path when mirrored
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

- Submitting requires the three document types to be present.
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
- Login and registration are rate-limited (shared via Redis in production).

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
| GET    | `/readyz`                                    | ❌   | —                             | Readiness probe (DB + storage)       |
| GET    | `/api/applications/`                         | ✅   | Applicant: own; Reviewer/Admin: all | List applications (paginated)  |
| POST   | `/api/applications/`                         | ✅   | Applicant                     | Create draft application             |
| GET    | `/api/applications/{id}/`                    | ✅   | Owner / Reviewer / Admin      | Application detail                   |
| PATCH  | `/api/applications/{id}/`                    | ✅   | Applicant (draft only)        | Update draft                         |
| POST   | `/api/applications/{id}/submit/`             | ✅   | Applicant                     | Submit for review                    |
| POST   | `/api/applications/{id}/documents/`          | ✅   | Applicant                     | Upload document                      |
| DELETE | `/api/applications/{id}/documents/{doc_id}/` | ✅   | Applicant                     | Delete document (file removed too)   |
| POST   | `/api/applications/{id}/review/`             | ✅   | Reviewer / Admin              | approve / reject / request_resubmission |
| GET    | `/api/applications/{id}/audit/`              | ✅   | Owner / Reviewer / Admin      | Audit trail (paginated)              |
| GET    | `/api/review-queue/`                         | ✅   | Reviewer / Admin              | Pending review queue                 |

Document uploads are validated for extension (jpg/jpeg/png/pdf), declared
content type, magic-byte content, and size (≤ 5 MB).

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
| `DATABASE_URL`                | ✅       | Postgres connection string (Supabase)          |
| `REDIS_URL`                   | ✅ (prod)| Required when `DJANGO_DEBUG=false`             |
| `SUPABASE_URL`                | ❌       | `https://<ref>.supabase.co`                    |
| `SUPABASE_SERVICE_ROLE_KEY`   | ❌       | Service role key (storage mirroring)           |
| `SUPABASE_STORAGE_BUCKET`     | ❌       | Bucket name (default `kyc-documents`)          |
| `CORS_ALLOWED_ORIGINS`        | ✅       | Frontend URL(s), comma-separated               |
| `CUSTOM_DOMAIN`               | ❌       | Optional extra CORS origin                     |

When Supabase is not configured, documents are stored locally under
`media/documents/` and served by Django (debug) or your web server.

### Frontend

| Variable       | Required | Description                          |
| -------------- | -------- | ------------------------------------ |
| `VITE_API_URL` | ✅       | Backend base URL, e.g. `https://kyc-backend.onrender.com` |

---

## Local development

### Prerequisites

- Python ≥ 3.12, Node ≥ 20, Postgres (or a Supabase project), Redis (optional
  in debug mode)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# create backend/.env with DATABASE_URL etc. (see supabase/README.md)
python manage.py migrate
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
python manage.py test kyc           # 18 tests: auth, flow, uploads, permissions
```

---

## Deployment

### Render (backend + Redis)

`render.yaml` defines a Python web service (`kyc-backend`) and a Redis
service (`kyc-redis`):

1. Render → **New → Blueprint** → select this repo.
2. Set the `sync: false` env vars in the dashboard: `DATABASE_URL`,
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CORS_ALLOWED_ORIGINS`,
   `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. Deploy. The start command runs `migrate`, `collectstatic`, then gunicorn.

The backend can also run from `backend/Dockerfile`
(`python:3.13-slim`, non-root user, `entrypoint.sh` runs migrations).

### Frontend

Build the SPA and serve it statically:

```bash
cd frontend
VITE_API_URL=https://kyc-backend.onrender.com npm run build
```

`frontend/Dockerfile` builds the app and serves `dist/` with nginx
(SPA fallback, hashed-asset caching, gzip, security headers,
`client_max_body_size 6m`).

### Supabase

See `supabase/README.md`: create the project, copy the connection string and
service role key, and create a **private** `kyc-documents` storage bucket.
Documents are served through time-limited signed URLs (cached server-side).

---

## Security notes

- Refresh tokens live in HttpOnly cookies; access tokens in memory only.
- Cookie-authenticated endpoints check the `Origin` header (CSRF mitigation).
- Django 6's built-in CSP middleware is enabled via `SECURE_CSP`; plus
  `X-Frame-Options`, `X-Content-Type-Options`, HSTS, and secure cookies.
- Uploads are validated by extension, MIME type, magic bytes, and size.
- Deleting a `Document` also deletes the file from disk/Supabase (PII).
- Login/register endpoints are throttled via Redis-backed counters.

---

## License

MIT — free to use, modify, distribute.
