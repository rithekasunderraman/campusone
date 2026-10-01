# CampusOne — Status Report

Date: 2026-10-01 · Branch `main`

**Live site: <https://campusone-web.onrender.com>** · API: <https://campusone-api-hg7e.onrender.com>
(health: `/api/health`) · Hosted on Render (static site + web service + PostgreSQL 16, Singapore).

**Production data migration: complete and verified on 2026-10-01.** All 147,131 rows are in the
Render database and match the local copy row for row.

The existing dataset is intact: 6,025 users, 5,000 students, 1,000 faculty, 10,502 OD requests,
SQLite integrity check `ok`. Nothing was reseeded.

## Evidence behind "tested"

| Check | Result |
|---|---|
| Backend tests (`pytest`, throwaway SQLite built from the migrations) | 171 passed |
| **Assistant battery on real Google Gemini calls**, full dataset | 35 of 35 (`docs/ASSISTANT_BATTERY_LLM.md`) |
| **OD document flow on real Google Gemini calls** (text, PDF, image, injection) | 7 of 7 (`docs/LLM_LIVE_VERIFICATION.md`) |
| Fallback with Gemini key invalid, and with the key removed (live) | Deterministic answers and extraction returned |
| Same suite on PostgreSQL 16 | 149 passed, 1 SQLite-only test skipped |
| Same suite in a clean Linux container (what CI runs) | 150 passed |
| Browser tests (Playwright, Edge, on a copy of the full database) | 8 passed |
| Assistant battery on the full dataset, expected values computed in SQL | 31 of 31 (`docs/ASSISTANT_BATTERY.md`) |
| Real app on the live database, read-only | 55 endpoints, all 200, all under 1 s |
| Production-mode rehearsal on PostgreSQL | Full OD flow, document storage, CORS, health |
| **Production data migration to Render** | 33 tables, 147,131 rows, 0 differing rows; 7 relationship spot checks |
| **Direct check of the Render database** | `student1`, `faculty1`, `admin` present; bcrypt accepts each demo password and rejects a wrong one; 0 orphaned rows; 51 foreign keys enforced |
| **Deployed frontend bundle** | Built with `https://campusone-api-hg7e.onrender.com/api`; CORS allows only the frontend origin |
| **Live browser smoke test** (`e2e/live-smoke.spec.ts`) | 3 of 3: each role signs in on the live site and sees the migrated figures |
| **Live OD flow in a browser** | Student submitted with a document, class advisor approved, student's open page updated without a reload |
| SQLite → PostgreSQL data copy | 147,131 rows, row-by-row identical |
| Frontend `npm run build` (Windows and Linux container) | passes |

## Capabilities

### Implemented & Tested

**Safety and foundations**
- Git repository with a pre-change baseline commit; `.gitignore` keeps the database, `.env`,
  virtualenv, `node_modules` and build output out of git (verified: none tracked).
- JWT secret, database URL and CORS origins read from the environment; production mode refuses
  to start when a secret is missing or weak or CORS is `*`.
- Alembic migrations: `0001` reproduces the original schema (no drift against the live
  database), `0002` adds the OD workflow. The app no longer creates tables implicitly.
- Seed script refuses to wipe a database that has data.
- SQLite → PostgreSQL migration script with full verification.

**OD workflow engine**
- State machine enforced on the server: Draft → Submitted → Under faculty review →
  (Clarification requested → Resubmitted) → Under HOD review (when policy requires) →
  Approved / Rejected, with Cancel from every non-final state. Invalid transitions are refused.
- Submission rules: date range within term, hours within limits, OD balance, duplicate request,
  overlap, attendance threshold — all from institution policy, all deterministic.
- Routing to the student's class advisor; HOD sign-off above the policy threshold;
  department-scoped HOD access.
- Optimistic concurrency: two reviewers acting at once → exactly one succeeds (tested with
  simultaneous requests, on SQLite and PostgreSQL).
- One audit row per transition, written in the same transaction; audit rows cannot be updated
  or deleted through the application.
- Approval, balance re-check and attendance credits commit or roll back together (tested by
  forcing a failure mid-approval).
- Document upload with type/size checks, access control and a storage abstraction with two
  working backends (local files, database).
- Student, faculty and admin/HOD APIs: paginated, searchable, filterable; analytics
  (department-wise utilisation, approval rate, turnaround); audit view; editable policy.
- Screens: student apply wizard, OD dashboard, request timeline; faculty approval queue with
  approve / reject / clarify; admin/HOD queue, analytics, policy and audit log.
- Changes appear on other users' screens without a refresh (polling every 6–8 s; tested with
  two browser sessions).

**Document intelligence**
- Text extraction from PDF and plain text.
- Field extraction (event, organiser, date, venue), each tagged extracted / inferred /
  not found with a confidence level.
- Cross-check against the form and duplicate detection, shown to approvers as advisory flags.
  Nothing is auto-rejected or auto-corrected.
- No automated step can change a request's status: writes to the status column outside the
  workflow engine raise an error (tested, including with a hostile model response).

**Assistant**
- Original deterministic intents retained; four wrong answers fixed (classes I can miss,
  faculty student count, students below threshold, past exams shown as upcoming).
- New OD intents for all three roles (see README §4).
- Answers are scoped to the logged-in user; a department head only ever gets their department;
  claims in the question text are ignored (tested).

**Configurability and polish**
- Institution profile and OD policy are data, editable by an institution-wide admin; every
  new table carries `institution_id`.
- Server-side pagination and search on admin students, admin faculty, faculty students,
  faculty attendance, faculty marks, placement applications.
- Placement analytics 10.6 s → 0.4 s with identical output.
- Sidebar collapses to a drawer on small screens; OD pages have no sideways scroll at 390 px.
- CI workflow (both jobs rehearsed in Linux containers from the committed tree).

**LLM features — verified with real calls to Google Gemini (2026-10-01)**
- The LLM layer has two providers behind one interface, selected by `LLM_PROVIDER`
  (`anthropic` or `gemini`). Verification used **Google Gemini** (`gemini-2.5-flash` answered;
  `gemini-3.5-flash` and `gemini-flash-lite-latest` are configured as automatic fallbacks).
- Assistant rephrasing of database facts: 33 questions across the three roles, every figure
  intact. LLM wording is now accepted only if every number from the database sentence appears
  unchanged; otherwise the database sentence is returned (enforced in code, tested).
- Assistant best-effort answers from the caller's own data, including "I don't have that
  information" for an out-of-scope question, a prompt-injection attempt that returned only
  the caller's own record, and a department head asking about other departments.
- Document field extraction with source and confidence tags, on an unlabelled text invitation
  and a PDF; mismatch flags raised without rejecting the request.
- Reading an image with the model's vision (a PNG poster with no text layer).
- A document containing a prompt injection: status and approved hours unchanged.
- Eligibility explanation worded by the model, for an eligible and a not-eligible case.
- Fallback: with an invalid key, with the key removed, and with simulated rate limits,
  overload, timeouts, blocked or truncated replies, the deterministic answer is returned.

**Deployment — verified on the live site (2026-10-01)**
- Frontend, API and database are running on Render from `render.yaml`. The API reports
  `environment: production`, database ok, and Gemini as the configured LLM.
- Signing in as `student1`, `faculty1` and `admin` on the live site shows populated data:
  attendance 87.6% and CGPA 8.42 for the student, 3 subjects and 1,667 students for the faculty
  member, 5,000 students / 1,000 faculty / 1,427 offers / 7,273 applications for the admin, and
  the OD analytics for 10,500+ requests. Every API call went to the backend host and returned 200.
- One real OD request was run through production: request #10503 "Tech Symposium", 3 hours on
  12 Oct 2026. The database holds its four audit rows (create, submit, route to advisor, approve
  by `faculty1`), two attendance credits, and the uploaded document in database storage with
  fields extracted by Gemini. The student's balance on production is now 3 used, 37 remaining.

### Implemented but Untested

- **The Anthropic provider, live.** It remains fully supported through the same abstraction
  (`LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`) and its code is unchanged, but no Anthropic
  key was available, so no real Claude request has been made. Its surrounding logic is covered
  by the same tests as Gemini.
- **Scanned PDFs through an LLM.** Images were verified live; a scanned (image-only) PDF uses
  the same path but was not itself uploaded in the live run.
- **Gemini under sustained load.** Free keys are rate limited; the fall-through to the next
  model and to the deterministic answer is tested, but only at demo-level traffic.
- **HOD route, clarification and rejection on production.** Only the submit → advisor approves
  path was run on the live site; the other paths are tested locally on SQLite and PostgreSQL.
- **Image documents on production.** The live request used a text document.
- **CI on GitHub Actions.** The same commands pass in Linux containers; the result of the
  workflow run on GitHub has not been checked from here.
- **`alembic downgrade`** from 0002 to 0001 (written, never run).
- **Policy and institution-profile forms in the browser.** Their APIs are tested; the two
  forms were not clicked through in a browser test.
- **Original create flows** — student placement apply through the UI, admin add company /
  drive, post announcement or event — unchanged code, covered by API tests only where noted.

### Planned, Not Started

- Multi-tenant isolation. Status is "architected for, not yet proven": no second institution
  exists and no isolation test has been written (`docs/MULTI_TENANCY.md`).
- Retrieval-augmented generation. Not added because no unstructured policy document exists
  in the project; OD policy is structured data and is answered directly.
- Cloud object storage backend (S3-compatible). The abstraction is there; database storage
  covers deployment without it.
- Push notifications (WebSockets/SSE), email notifications, per-class attendance records.
- HOD-initiated clarification requests (only the class advisor can ask today).

### Blocked

| Item | Blocked on |
|---|---|
| Live verification of the Anthropic provider | An Anthropic API key (optional; Gemini covers the features). |

### Housekeeping after go-live

- The Render database password was shared in a chat transcript during the migration and
  should be rotated in the Render dashboard (see `docs/DEPLOYMENT.md`).
- Request #10503 on production is a verification artefact for `student1`; it is approved, so it
  cannot be cancelled in the app and stays as demo data, using 3 of the student's 40 hours.
- The free Render plan sleeps the API after about 15 minutes idle (first request then takes
  30–60 seconds) and the free database expires after its trial period unless upgraded.

## One incident to know about

During the first browser test run the test dev server was mis-wired and reached the real
backend, so one test OD request (#10503) was written to the live database. It was caught on
the next run. A fresh backup was taken (`backend/backups/campusone-before-e2e-artefact-cleanup.db`)
and only that request and its 7 child rows were removed, returning the table to 10,502 rows.
The test server is now hard-wired to its own backend and the tests refuse to run unless the
backend identifies itself as the test instance.

## Demo credentials

| Role | Username | Password |
|---|---|---|
| Student (Manish Kumar, CSE) | `student1` | `student123` |
| Faculty, class advisor of student1 | `faculty1` | `faculty123` |
| HOD of CSE | `admin2` | `admin123` |
| Institution-wide admin | `admin` | `admin123` |

## Demo click-through

Open the live site <https://campusone-web.onrender.com> (or run both servers locally, README §1, and open http://localhost:5173). Use two browser windows (or one
normal and one private window) so the student and the approver are signed in at the same time.
This creates real OD requests for `student1`. On the live site `student1` already has 3 hours used by request #10503, so the figures in steps 1 and 14 are 37h available and 16 used / 24 remaining there.

**Student submits**
1. Window A: sign in as `student1`. Click **On-Duty (OD)**. Note "Available to request: 40h".
2. Click **Apply for OD**. Enter event name "National Tech Symposium", organiser "IEEE",
   venue "Main Auditorium", a start and end on a future weekday (09:00 to 12:00), 3 hours,
   and a purpose. Click **Continue**.
3. Attach any PDF or text invitation (optional). Click **Continue**.
4. Eligibility shows six green checks, the balance after the request, the approval route
   "Class advisor" and the classes covered. Click **Continue**, then **Submit request**.
5. The request page opens with status **Under faculty review** and a three-entry timeline.
   Leave this window open.

**Faculty approves**
6. Window B: sign in as `faculty1`. Click **OD Approvals**. The request is in
   "Awaiting my decision"; click the event name.
7. The panel shows the student's balance and attendance, the document and any automatic
   check notes. Type a comment and click **Approve**.
8. Back in window A, without refreshing: within a few seconds the status becomes **Approved**,
   the approver's note appears, and "Attendance credited" lists the classes.

**HOD route and admin analytics**
9. Window A: apply again for a different day, 08:00 to 18:00, 10 hours. The route now reads
   "Class advisor → HOD". Submit.
10. Window B (`faculty1`): open it and click **Recommend to HOD**.
11. Window B: log out, sign in as `admin2`. Click **OD Oversight**. The request is under
    "Awaiting HOD decision"; open it and click **Approve**.
12. Click **View audit log**: five entries from "Draft created" to "Approved", each with actor
    and time.
13. Click the **Analytics** tab: requests and utilisation by department, approval rate,
    average turnaround. Sign in as `admin` instead to see all three departments and the
    **Policy** tab.

**Assistant answers from the same data**
14. Window A (`student1`): click **AI Assistant** and ask "How many OD hours do I have left?" →
    13 used, 27 remaining of 40.
15. Ask "What is the status of my last OD application?" and "Can I apply for OD tomorrow?".
16. As `faculty1`: "How many OD requests have I approved this month?"
    As `admin`: "Show department-wise OD statistics" and "Which department has the highest OD
    utilisation?"
