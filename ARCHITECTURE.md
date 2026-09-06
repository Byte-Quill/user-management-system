# Architecture

This document describes the codebase layout and the module boundaries that
keep it scalable. For feature/security details, see the [README](README.md).

## Design principles

1. **Layered backend** — `views/` (HTTP) → `serializers/` (validation/IO
   shapes) → `models/` (persistence) with cross-cutting concerns isolated in
   `common/` and pure business logic in `services/`. Adding a feature means
   touching one module per layer, not a 500-line file.
2. **Domain-oriented modules** — both backend and frontend are split along
   the same business domains (auth, applications, review, users, analytics),
   so backend and frontend changes stay aligned.
3. **Zero-breakage public APIs** — `kyc/models/__init__.py`,
   `kyc/serializers/__init__.py` and `kyc/views/__init__.py` re-export the
   pre-existing public names, so `from kyc.models import KYCApplication`
   keeps working everywhere (admin, management commands, tests, migrations).
   The app label stays `kyc`, so **no migrations changed and no data is
   affected** (`manage.py makemigrations --check` reports no changes).
4. **Explicit dependency flow (frontend)** — `app/` (shell) may import
   `features/`; `features/` may import `lib/`, `components/`, `data/`;
   shared code never imports feature code. The `@/` path alias keeps imports
   stable regardless of file depth.

## Backend layout (`backend/kyc/`)

```
kyc/
├── common/      # cross-cutting: middleware, cache, health, throttles,
│                # permissions, auth backend, tokens, validators, email domains
├── models/      # persistence, one module per domain:
│                #   user, application, document, audit, email_log, email_otp
├── serializers/ # DRF input/output shapes: fields (shared validators),
│                # auth, users, applications
├── services/    # business logic: otp (issue/request/verify), email (Resend)
├── views/       # HTTP layer per domain: auth, applications, review,
│                # users, analytics
├── tests/       # one module per domain + shared utils.py
├── admin.py     # Django admin
├── urls.py      # route table (imports from views package)
└── migrations/  # untouched by the restructure
```

Dependency rule: `views → serializers → models`, everything may use
`common`/`services`; nothing in `common`/`services` imports `views`.

## Frontend layout (`frontend/src/`)

```
src/
├── app/         # App shell: GoogleOAuthProvider wiring (config.ts),
│                # route guards (guards.tsx), lazy route table (router.tsx)
├── lib/
│   ├── api/     # client.ts (fetch wrapper, in-memory access token,
│   │            # single-flight refresh, ApiError) + per-domain endpoint
│   │            # modules (auth, applications, users, analytics)
│   └── validation.ts   # client-side validators mirroring backend rules
├── types/       # API types split per domain
├── features/    # vertical slices: auth/, applications/, review/,
│                # users/, analytics/, dashboard/ — each owns its pages,
│                # components and hooks
├── components/  # design-system pieces: ui/, form/, layout/
├── data/        # generated/static datasets (countries, disposable emails)
└── hooks/       # cross-feature hooks (usePaginatedList)
```

Route-level code splitting is preserved (one lazy chunk per page); the
`@/` alias (tsconfig `paths` + vite `resolve.alias`) removes fragile
`../../` import chains.

## Validation architecture (frontend-first UX, backend-authoritative)

Goal: **users never trigger a backend validation error** through the SPA.
The backend remains the source of truth — the SPA mirrors every rule, and a
contract test refuses drift. The layers, in order:

1. **`validation.ts` constants** — every rule the SPA enforces lives in
   `LIMITS`, `DOB_MIN_ISO`, `OTP_LENGTH`, `PASSWORD_MIN_LENGTH`,
   `MAX_FILE_SIZE_MB` / `ALLOWED_FILE_EXTENSIONS`, `APPLICATION_ID_TYPES`.
   Forms use these constants for `maxLength`/hints **and** the validators —
   no inline literals.
2. **`python manage.py validation_contract`** — emits
   `frontend/src/lib/backend-contract.json` from the *backend* models /
   serializers / settings (the single source of truth). Regenerate after any
   backend rule change:
   `python manage.py validation_contract > ../frontend/src/lib/backend-contract.json`
3. **`contract.test.ts`** — compares the committed JSON against the SPA
   constants. If either side changes without the other, the frontend test
   suite fails, so the two layers cannot silently drift.
4. **In-page validators** — Register/Login/Forgot/Verify/Application forms
   validate on blur and on submit, and the admin "create user" form gates on
   the same rules as `AdminUserCreateSerializer`. What the browser allows is
   exactly what the backend accepts (except legacy/edge cases the backend
   deliberately rejects as integrity guards: expired-ID blocks submission,
   review concurrency).
5. **Backend serializers re-validate** — as the authority and the safety net
   for API clients, curl, and anything that bypasses the SPA. A 4xx from the
   backend is expected only for *database-level* conditions (duplicates,
   status races), never for ordinary form mistakes.

Rule of thumb when adding a field or changing a limit: change the backend,
regenerate the contract, update `validation.ts`, let the tests catch the rest.

## Adding a new feature

Backend: add a model module in `models/`, register its re-export in
`models/__init__.py`, add serializers in `serializers/`, views in `views/`,
and routes in `urls.py`. Frontend: create `features/<name>/` with its pages
and components, add endpoint functions under `lib/api/`, and register the
route in `app/router.tsx`.
