# CampusOne — Phase 0 Audit Report

Audit date: 2026-10-01. Read-only inspection of the code and the live SQLite
database (`backend/campusone.db`), plus a live run of both servers.

## 1. Stack as found

| Area | Finding |
|---|---|
| Backend | FastAPI 0.115 + SQLAlchemy 2.0, Python 3.10 venv, 8 routers, 49 endpoints |
| Frontend | React 18 + TypeScript + Vite 5 + Tailwind 3, React Router, axios, Recharts |
| Database | SQLite file, 26 tables, schema created by `Base.metadata.create_all` at import |
| Migrations | None. No Alembic, no `alembic_version` table |
| Auth | JWT HS256 (python-jose), bcrypt via passlib, `require_role()` dependency |
| Version control | Not a git repository |
| Tooling on this machine | git yes; Docker Desktop installed (daemon was stopped); no `gh`, no `psql`, no Tesseract; Edge and Chrome installed |

## 2. Dataset (live, verified)

6,025 users (25 admin / 1,000 faculty / 5,000 students), 3 departments, 3 courses,
10 subjects, 16,667 attendance rows, 16,667 marks rows, 20 exams, 20 timetable slots,
5,000 fees, 1,713 library records, 30 clubs, 360 club events, 11,271 memberships,
43,252 event attendance, 14,531 volunteer rows, 12 hostels, 2,694 allocations,
6 companies, 6 drives, 7,273 applications, 10,502 OD requests.
Spot checks of 2 rows per table were consistent (e.g. `student1` = student id 1,
`21CSE1042`, CSE, sem 5; `faculty1` = faculty id 1, CSE; `admin` = user id 1).

## 3. OD model — what matched your notes and what did not

Actual columns on `od_requests`:
`id, student_id, event_id (nullable), requested_hours, approved_hours, request_date,
status, reason, reviewed_by_faculty_id`.

- **Matched:** student_id, nullable event_id, requested_hours, approved_hours,
  request_date, status, reason.
- **Not in your notes:** `reviewed_by_faculty_id` exists — but it is NULL on all
  10,502 rows and no code ever writes it. So "no reviewer tracking" is true in
  practice.
- **Confirmed gaps:** no approval hierarchy, no workflow state, no documents, no
  audit log, no version column, and **no OD write endpoint at all** — the only OD
  API is the read-only `GET /api/student/campus-life/od`.
- **Extra gap not in your notes:** OD requests have **no date range**. The only
  time information is the linked club event's date. Overlap validation therefore
  needs new `start_at` / `end_at` columns (backfilled from the event for old rows).
- Status values in data: Approved 9,618 / Pending 440 / Rejected 444.
  Max approved hours for any student: 15 (allowance is hard-coded to 40 in two places).
- 2 legacy (student, event) duplicate pairs already exist; they are left untouched.

## 4. Things that change the plan

1. **No class-advisor concept exists.** Only faculty ids 1–5 teach subjects; there is
   no student→advisor link. A new `advisor_assignments` table is needed (new table,
   no change to `students`).
2. **No HOD concept exists.** Admin users have no department. A new
   `department_heads` table maps admin users to departments; admins without a
   mapping act institution-wide.
3. **All 5,000 students are Year 3 / Semester 5**, so "per semester" allowance is
   implemented with an explicit term window in the institution policy.
4. **Attendance is stored as per-subject aggregates**, not per-class rows. "Attendance
   adjustment" on OD approval is therefore implemented as a credit ledger
   (`od_attendance_credits`) rather than by rewriting aggregate counters.
5. **2,405 students are below 75% overall attendance**, so the attendance-threshold
   rule will genuinely block a large share of students — the threshold is a policy
   setting, not a constant.
6. **`seed.run()` calls `drop_all()`** and is triggered automatically at startup when
   the `users` table is empty. Harmless today, dangerous if pointed at the wrong
   database, so auto-seeding is gated behind an explicit dev-only setting.

None of these contradict a core assumption; work proceeds.

## 5. AI assistant

- Intent resolution is plain substring matching (`if "attendance" in m`) in
  `routers/ai_assistant.py`, with student-life intents delegated first to
  `agents/campus_life_agent.py`.
- An LLM call **is wired but dormant**: `_try_llm_rephrase` runs only if
  `ANTHROPIC_API_KEY` is set and the `anthropic` package is installed. Neither is
  true (package absent from `requirements.txt` and the venv; no key in the
  environment; nothing loads a `.env`). Hard-coded model id `claude-sonnet-4-6`.
- Known wrong answers from the earlier baseline run: "how many classes can I miss"
  → timetable; faculty "how many students do I teach" → subject list; student and
  faculty exam intents list past exams as upcoming.

## 6. Secrets

- `SECRET_KEY` is hard-coded at `backend/app/auth.py:12`, referenced at lines 32
  and 42 only. Not read from the environment.
- No other secrets in the code. `.env.example` exists but nothing reads a `.env`.

## 7. Frontend conventions to follow

- Routing in `src/App.tsx` (nested routes under a role-guarded `DashboardLayout`);
  sidebar items in `src/layouts/DashboardLayout.tsx`.
- Data fetching: `useFetch(url, deps)` returning `{data, loading, error, reload}`;
  writes go through the axios `client` with a `message` banner for results.
- UI primitives in `src/components/Common.tsx`: `PageHeader`, `StatCard`,
  `ProgressBar`, `EmptyState`, `Pill`, `Loading`; CSS classes `card`, `btn-primary`,
  `btn-secondary`, `input`, `table-clean`.
- Large lists (5,000 students, 7,273 applications) are fetched whole and filtered
  in the browser — no server pagination anywhere.

## 8. Run check

Backend (`uvicorn app.main:app --port 8000`) and frontend (`npm run dev`) both start
cleanly. `admin`, `faculty1`, `student1` all log in; cross-role access returns 403.
`npm run build` passes after the earlier `DashboardLayout.tsx` typing fix.
