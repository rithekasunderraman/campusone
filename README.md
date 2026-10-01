# CampusOne AI – Integrated University Campus Management & Student Success Portal

A full-stack university portal: Student / Faculty / Admin dashboards, academics, attendance,
exams, timetable, fees, library, placements, campus life, an **enterprise On-Duty (OD)
workflow** with document checks and audit trail, and a database-grounded AI Campus Assistant.

**Stack:** React + TypeScript + Vite + Tailwind (frontend) · FastAPI + SQLAlchemy + Alembic
(backend) · SQLite locally, PostgreSQL in production · JWT auth · optional Claude API.

Further documents: [`STATUS_REPORT.md`](STATUS_REPORT.md) (what is implemented and tested, demo
script) · [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) · [`docs/MULTI_TENANCY.md`](docs/MULTI_TENANCY.md)
· [`docs/ASSISTANT_BATTERY.md`](docs/ASSISTANT_BATTERY.md) · [`AUDIT_REPORT.md`](AUDIT_REPORT.md).

---

## 1. Run it locally

Prerequisites: Python 3.10+, Node.js 18+ (22 recommended).

**Backend** (terminal 1)

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then set JWT_SECRET (see the comment in the file)
uvicorn app.main:app --reload --port 8000
```

- An existing `campusone.db` is used as it is. If its schema is behind the code, the server
  stops and tells you to run `alembic upgrade head` (back the file up first).
- With no database at all, the schema is created by Alembic and demo data is seeded
  (5,000 students, 1,000 faculty, 25 admins) — development mode only.
- API docs: http://127.0.0.1:8000/docs · Health: http://127.0.0.1:8000/api/health

**Frontend** (terminal 2)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend on port 8000.

### Demo accounts

| Role | Username | Password | Notes |
|---|---|---|---|
| Admin (institution-wide) | `admin` | `admin123` | Sees every department; can edit OD policy |
| Admin (HOD of CSE) | `admin2` | `admin123` | `admin3` = ECE, `admin4` = MECH |
| Faculty | `faculty1` | `faculty123` | Class advisor of `student1`; teaches CSE301/303/305 |
| Student | `student1` | `student123` | Manish Kumar, 21CSE1042, CSE |

All generated accounts use the same per-role passwords.

---

## 2. Configuration

All settings come from environment variables (`backend/.env` locally, the host's settings in
production). `backend/.env.example` documents each one.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` or `production`. Production refuses to start with missing or weak secrets. |
| `JWT_SECRET` | Signs login tokens. Required in production (32+ characters). |
| `DATABASE_URL` | Empty locally = SQLite file. PostgreSQL URL in production. |
| `CORS_ORIGINS` | Allowed frontend origin(s). Required in production; `*` is rejected. |
| `LLM_PROVIDER` | `anthropic` (default) or `gemini`. Selects which LLM the app talks to. |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | Used when the provider is `anthropic`. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Used when the provider is `gemini`. |
| | LLM features are optional: everything works without a key. |
| `STORAGE_BACKEND` | `local` (filesystem) or `database` for uploaded OD documents. |

---

## 3. The OD workflow

```
Draft → Submitted → Under faculty review → [Clarification requested → Resubmitted →]
        [Under HOD review, when policy requires] → Approved | Rejected
Cancelled: by the student from any non-final state
```

- **Rules checked before submission** (deterministic, from institution policy): dates within
  the term, hours within the per-request limit, enough OD balance, no duplicate request for the
  same event, no overlap with the student's other requests, attendance at or above the threshold.
- **Routing:** to the student's class advisor; requests over the HOD threshold also need the
  department head.
- **Integrity:** every transition is one version-checked update plus one audit row in the same
  transaction; a second reviewer acting on a stale version gets a conflict; approval, balance
  check and attendance credits commit or roll back together; audit rows cannot be edited.
- **Documents:** PDF, image or text. Event name, date, venue and organiser are extracted and
  compared with the form; differences become advisory flags for the approver. Nothing is
  auto-rejected, and no automated step can change a request's status.
- **Screens:** student apply wizard, dashboard and request timeline; faculty approval queue;
  admin/HOD queue, analytics, policy editor and audit log. Lists refresh every few seconds.

Key code: `backend/app/od_workflow.py` (state machine), `od_service.py` (rules),
`od_intelligence.py` (documents), `routers/od.py` (API), `frontend/src/pages/*/OD*.tsx`.

---

## 4. AI Campus Assistant

Answers are resolved deterministically from the database for the logged-in user; an LLM, when
configured, only rephrases those facts or gives a best-effort answer from that user's own
authorised data. Examples: "Can I apply for OD tomorrow?", "How many OD hours do I have left?",
"Why was my last application rejected?", "How many more classes can I miss?" (student);
"How many OD requests are pending my approval?" (faculty); "Show department-wise OD
statistics", "Which department has the highest OD utilisation?" (admin).

---

## 5. Database and migrations

Schema changes are Alembic migrations in `backend/migrations/versions`.

```powershell
alembic current            # which revision the database is at
alembic upgrade head       # apply pending migrations (back up first)
```

`python -m app.seed` **drops every table** and regenerates demo data. It refuses to run on a
database that already has data unless you pass `--force-reset`, and never runs in production.

Moving the data to PostgreSQL: `python -m scripts.migrate_sqlite_to_postgres --target <url>`
(see `docs/DEPLOYMENT.md`).

---

## 6. Tests

```powershell
cd backend
pip install -r requirements-dev.txt
pytest                      # 171 tests on a throwaway database built from the migrations

cd ..\frontend
npx playwright test         # 8 browser tests; starts its own servers on a COPY of the database
```

Neither suite touches `campusone.db`. The browser tests use Microsoft Edge by default
(`E2E_CHANNEL=chrome` to change) and refuse to run unless they are talking to the test backend.
To run the backend suite on PostgreSQL set `TEST_DATABASE_URL` to a database whose name
contains `test`.

---

## 7. Project structure

```
campusone/
├── render.yaml                     # deployment blueprint (database + API + static site)
├── .github/workflows/ci.yml        # lint, tests, type-check and build on every push
├── docs/                           # deployment, multi-tenancy assessment, assistant evidence
├── backend/
│   ├── alembic.ini, migrations/    # schema history (0001 baseline, 0002 OD workflow)
│   ├── scripts/                    # SQLite→PostgreSQL migration, e2e server, assistant battery
│   ├── tests/                      # pytest suite
│   └── app/
│       ├── main.py, config.py, database.py, db_setup.py, auth.py, models.py, seed.py
│       ├── od_workflow.py, od_service.py, od_intelligence.py, od_bootstrap.py
│       ├── storage.py, llm.py
│       ├── agents/                 # assistant intents (campus life, OD)
│       └── routers/                # auth, student, faculty, admin, common, placement,
│                                   # campus_life, od, ai_assistant
└── frontend/
    ├── e2e/                        # Playwright browser tests
    └── src/
        ├── api/client.ts, context/AuthContext.tsx, hooks/useFetch.ts
        ├── components/Common.tsx, components/OD.tsx
        ├── layouts/DashboardLayout.tsx
        └── pages/ (student, faculty, admin, Login, AIAssistant)
```
