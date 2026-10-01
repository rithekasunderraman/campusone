# Deployment guide

## Chosen stack: Render (database, API and frontend on one platform)

| Piece | Service | Why |
|---|---|---|
| Frontend | Render **Static Site** | A Vite build is plain static files; served from a CDN with a rewrite rule for client-side routes. |
| Backend | Render **Web Service** (Python) | Runs `uvicorn` directly from the repo, health-checked on `/api/health`. |
| Database | Render **PostgreSQL 16** | Managed, in the same region as the API, reached over Render's private network. |

One platform means one dashboard, one region (`singapore`) and one file — `render.yaml` at the
repo root — that recreates all three. Uploaded OD documents are stored in PostgreSQL
(`STORAGE_BACKEND=database`), so nothing depends on a persistent disk and there is no fourth
service to configure.

Free-plan limits to know before a demo: the API sleeps after about 15 minutes idle and takes
30–60 seconds to wake on the next request, and a free Render database is deleted after its trial
period (currently about 30 days) unless upgraded. For anything beyond a demo use the paid
starter plans by changing `plan:` in `render.yaml`.

## Current deployment (2026-10-01)

| | |
|---|---|
| Frontend | <https://campusone-web.onrender.com> |
| API | <https://campusone-api-hg7e.onrender.com> (Render added the `-hg7e` suffix) |
| `VITE_API_BASE_URL` on `campusone-web` | `https://campusone-api-hg7e.onrender.com/api` |
| `CORS_ORIGINS` on `campusone-api` | `https://campusone-web.onrender.com` |
| Database | `campusone-db`, loaded and verified from the local SQLite file |

Lesson from the first deploy: the frontend was built before `VITE_API_BASE_URL` was set, so it
called `/api` on the static site itself and every request silently failed while the login page
loaded normally. After changing that variable, redeploy the static site with the build cache
cleared — the value is baked in at build time. Check with:
`npx playwright test e2e/live-smoke.spec.ts` (with `E2E_BASE_URL` set).

### Rotating the database password

This is done in the Render dashboard, on the `campusone-db` page (look for the credentials /
connections section; the exact control depends on your plan and Render's current UI). It has
not been done or tested as part of this project, so treat the following as a checklist rather
than a verified procedure:

1. Create the new credential (or reset the password) for the database.
2. Check `campusone-api` → **Environment** → `DATABASE_URL`. It is linked to the database by
   the blueprint, so it should show the new internal URL by itself. If it still shows the old
   password, trigger a manual deploy of `campusone-api`; if it is still old after that, paste
   the new Internal Database URL in by hand.
3. Confirm `https://campusone-api-hg7e.onrender.com/api/health` reports `"database": "ok"`
   and that you can still sign in.
4. Confirm the old External Database URL is refused (remove the old credential if Render kept it).

## What has been verified locally

- The exact production start command, with `APP_ENV=production`, against PostgreSQL 16:
  login for all roles, 18 read endpoints, a full OD flow (submit with document → advisor →
  HOD → approved), document download from database storage, audit log, the assistant, and CORS
  allowing only the configured origin.
- The whole backend test suite on PostgreSQL (149 passed, 1 SQLite-only test skipped).
- The data migration into PostgreSQL at the current schema: 147,131 rows, row-by-row identical.

Nothing has been deployed yet: that needs your accounts (below).

## Steps that need you

Each step says why it cannot be done for you.

### 1. Put the code on GitHub — *needs your GitHub account*

Create an empty repository at <https://github.com/new> (no README, no .gitignore), then:

```powershell
cd C:\Users\rithe\Downloads\campusone-ai-student-life-updated\campusone
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

The CI workflow (`.github/workflows/ci.yml`) runs on that first push.

### 2. Create the services — *needs your Render account*

1. Sign up at <https://render.com> and connect your GitHub account.
2. **New → Blueprint**, pick the repository. Render reads `render.yaml` and proposes
   `campusone-db`, `campusone-api` and `campusone-web`.
3. It asks for the three values that are deliberately not in the repo. Enter:
   - `VITE_API_BASE_URL` → `https://campusone-api.onrender.com/api`
   - `CORS_ORIGINS` → `https://campusone-web.onrender.com`
   - `GEMINI_API_KEY` → your Gemini key (optional, step 5), or leave empty
   - `ANTHROPIC_API_KEY` → leave empty
4. Click **Apply**.

If Render reports that a name is taken it adds a suffix (for example
`campusone-api-x1y2.onrender.com`). In that case, after the first deploy open each service's
**Environment** tab, correct the two URLs to the real ones, and redeploy both — the frontend
bakes the API address in at build time, and the API only accepts the frontend origin it is told.

`JWT_SECRET` is generated by Render and `DATABASE_URL` is injected from the database; you never
see or type either.

### 3. Load the data — *needs the database URL from your Render dashboard*

A fresh deployment has the schema (created by `alembic upgrade head` at start-up) but no users.
Copy the existing dataset in, from your machine:

1. Render dashboard → `campusone-db` → **Connect** → copy the **External Database URL**.
2. Run:

```powershell
cd C:\Users\rithe\Downloads\campusone-ai-student-life-updated\campusone\backend
.\venv\Scripts\Activate.ps1
$env:TARGET_DATABASE_URL = "<paste the External Database URL>"
python -m scripts.migrate_sqlite_to_postgres
```

It reads `campusone.db` read-only, copies every table in one transaction, and finishes with
`RESULT: MIGRATION VERIFIED` after comparing all rows. Your local SQLite file is not changed.
Expect a few minutes over the internet. If you ever need to reload, add `--replace`.

### 4. Check it

- `https://campusone-api.onrender.com/api/health` → `{"status":"ok","database":"ok",...}`
- Open `https://campusone-web.onrender.com` and sign in with the demo accounts.
- Run the browser tests against the live site (this creates real OD requests for `student1`
  in the deployed database):

```powershell
cd ..\frontend
$env:E2E_BASE_URL = "https://campusone-web.onrender.com"
npx playwright test e2e/od-flow.spec.ts
```

### 5. Optional: turn on the LLM features — *needs a key only you can paste into Render*

The blueprint sets `LLM_PROVIDER=gemini`. In Render → `campusone-api` → **Environment**, set
`GEMINI_API_KEY` to your Gemini key and save (the service redeploys). The key is stored by
Render; it is not in the repository. `/api/health` then reports `"llm": "gemini (...)"`.

This enables natural phrasing in the assistant, best-effort answers to questions outside the
built-in intents, reading of image and scanned-PDF documents, and LLM field extraction. Without a
key every feature still works on the deterministic engine.

To use Claude instead, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` (from
<https://console.anthropic.com>); nothing else changes. `GEMINI_MODEL` (optional) and `LLM_MODEL`
select the model for each provider.

Free Gemini keys are rate limited (a handful of requests per minute). When a limit is hit or a
model is overloaded, the next model in `GEMINI_MODEL` is tried, and if none answers the user gets
the deterministic answer — the request never fails.

## Running the production configuration locally

```powershell
docker run -d --name campusone-pg -e POSTGRES_PASSWORD=campusone_local -e POSTGRES_DB=campusone -p 5433:5432 postgres:16-alpine
python -m scripts.migrate_sqlite_to_postgres --target postgresql://postgres:campusone_local@localhost:5433/campusone
$env:APP_ENV="production"; $env:DATABASE_URL="postgresql://postgres:campusone_local@localhost:5433/campusone"
$env:JWT_SECRET="<at least 32 random characters>"; $env:CORS_ORIGINS="http://localhost:5173"; $env:STORAGE_BACKEND="database"
alembic upgrade head; uvicorn app.main:app --port 8000
```

In production mode the app refuses to start if `JWT_SECRET` is missing or weak, if
`DATABASE_URL` is missing, or if `CORS_ORIGINS` is missing or `*`.

## Rollback and backups

- Code: redeploy an earlier commit from the Render dashboard.
- Schema: migrations are additive; `alembic downgrade 0001` removes the OD workflow tables
  (and their data) — take a database backup first.
- Local SQLite backups taken during this work are in `backend/backups/` (not in git).
