# Fixes Applied — Login 401 Bug

## Symptom
`POST /api/auth/login` returned `401 Unauthorized` for **all three** demo
accounts (admin, faculty1, student1), even though the credentials, request
format, CORS config, and frontend API calls were all correct.

## Root Cause #1 (the actual reason every login failed)
`backend/app/main.py` decided whether to auto-seed the database using a
**file-size heuristic**:

```python
if not os.path.exists(db_path) or os.path.getsize(db_path) < 20000:
    seed.run()
```

This is broken. `Base.metadata.create_all(bind=engine)` runs unconditionally
at import time (before this check) and creates an **empty SQLite file that
is already ~98KB** on disk, purely from table schema overhead — before a
single row exists. Since 98,304 > 20,000, the condition was always false and
`seed.run()` **never executed**. The `users` table stayed permanently empty,
so every login attempt correctly returned 401 — the users genuinely didn't
exist in the database. This was reproduced deterministically on a clean
clone (verified with a standalone script).

**Fix:** replaced the size heuristic with an actual row-count check
(`db.query(models.User).count()`). This is reliable and, as a bonus,
**self-heals any existing broken database** — you don't need to manually
delete `campusone.db`; the next server start will detect zero users and
reseed automatically.

## Root Cause #2 (would have crashed seeding even if it had run)
`backend/requirements.txt` pinned `passlib[bcrypt]==1.7.4` but did not pin
the `bcrypt` package itself. `pip install` therefore pulled the newest
`bcrypt` (5.0.0), which removed the `__about__` attribute that passlib
1.7.4 depends on internally. Every call to `hash_password()` /
`verify_password()` raised:

```
AttributeError: module 'bcrypt' has no attribute '__about__'
...
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```

This was reproduced directly in a Python shell against the exact installed
versions.

**Fix:** pinned `bcrypt==4.0.1` in `requirements.txt`, the last version
compatible with `passlib[bcrypt]==1.7.4`.

## Root Cause #3 (AI assistant quality bug, not auth-related)
Admin AI queries like *"How many students are in CSE?"* and *"How many
students are placed?"* fell through to generic, unfiltered answers because
`app/routers/ai_assistant.py` had no department-name/code matching, and the
"placed" intent check was ordered **after** a more general student-count
check that matched first (`"student" in m and "how many" in m` matched
before `"placed" in m` was ever checked).

**Fix:** added a `_match_department()` helper used by the student/faculty
count intents, reordered the "placed" intent above the generic count
intent, and added handlers for department-wise attendance, upcoming exams,
and "which companies are conducting drives" — all of which were listed as
example queries in the original spec but were unimplemented or unreachable.

## Files changed
- `backend/requirements.txt` — pinned `bcrypt==4.0.1`
- `backend/app/main.py` — row-count-based seed check instead of file size
- `backend/app/routers/ai_assistant.py` — fixed admin intent detection/ordering,
  added department filtering, upcoming exams, and placement-drive company intents

## Verification performed
- Fresh clone → fresh venv → `pip install -r requirements.txt` → server start
  → confirmed `bcrypt==4.0.1` installed, seed ran, log showed
  "Database seeded successfully."
- All three demo accounts logged in successfully through the real Vite dev
  proxy (`localhost:5173/api/auth/login`), exactly as the browser calls it.
- Wrong password correctly returns 401.
- Every dashboard/module endpoint (admin, faculty, student — dashboard,
  students, faculty, departments, courses, subjects, timetable, exams,
  attendance, marks, fees, library) returned 200 OK with a valid token.
- Cross-role access correctly blocked: student token against
  `/api/admin/dashboard` → 403.
- AI assistant tested for every example query listed in the original spec
  across all three roles, with real database-grounded answers and no LLM
  API key configured (pure rule-based fallback path).
