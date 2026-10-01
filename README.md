# CampusOne AI – Integrated University Campus Management & Student Success Portal

A full-stack university ERP-style portal: Student / Faculty / Admin dashboards, academics,
attendance, exams, timetable, fees, library, placement portal, and a database-aware AI
Campus Assistant.

**Stack:** React + TypeScript + Vite + Tailwind CSS (frontend) · FastAPI + SQLAlchemy + SQLite (backend) · JWT auth · Recharts

---

## 1. Project structure

```
campusone/
├── backend/
│   ├── requirements.txt
│   ├── campusone.db              # created automatically on first run
│   └── app/
│       ├── main.py               # FastAPI app entrypoint
│       ├── database.py           # SQLAlchemy engine/session
│       ├── models.py             # all database models
│       ├── schemas.py            # Pydantic request/response models
│       ├── auth.py               # JWT + password hashing
│       ├── utils.py              # shared serialization helpers
│       ├── seed.py               # realistic demo data generator
│       └── routers/
│           ├── auth.py           # /api/auth/*
│           ├── student.py        # /api/student/*
│           ├── faculty.py        # /api/faculty/*
│           ├── admin.py          # /api/admin/*
│           ├── common.py         # /api/announcements, /api/events
│           ├── placement.py      # /api/placement/*
│           └── ai_assistant.py   # /api/ai/chat
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts / tailwind.config.js / tsconfig*.json
    └── src/
        ├── main.tsx / App.tsx / index.css
        ├── api/client.ts             # axios instance + auth interceptor
        ├── context/AuthContext.tsx   # login state
        ├── hooks/useFetch.ts         # generic data-fetching hook
        ├── layouts/DashboardLayout.tsx
        ├── components/Common.tsx     # StatCard, ProgressBar, Pill, etc.
        └── pages/
            ├── Login.tsx
            ├── AIAssistant.tsx
            ├── student/  (Dashboard, Attendance, Marks, Exams, Timetable, Fees, Library, Placement, Announcements, Campus Life)
            ├── faculty/  (Dashboard, Subjects, Students, Attendance, Marks, Exams, Timetable, Announcements)
            └── admin/    (Dashboard, Students, Faculty, Departments, Courses, Placement, Reports, Announcements)
```

---

## 2. Prerequisites

- Python 3.10+ (3.11 recommended)
- Node.js 18+ and npm
- Windows, macOS, or Linux — the commands below are Windows-friendly (PowerShell / cmd)

---

## 3. Backend setup (FastAPI)

```powershell
cd campusone\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the API server:

```powershell
uvicorn app.main:app --reload --port 8000
```

- On first run the app automatically creates `campusone.db` (SQLite) and seeds it with
  realistic demo data (departments, students, faculty, subjects, attendance, marks, exams,
  timetable, fees, library, announcements, events, companies, placement drives, and
  applications).
- To force a fresh reseed at any time (e.g. after changing `seed.py`):
  ```powershell
  python -m app.seed
  ```
- API docs (interactive): http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health

### Optional: enable LLM-polished AI Assistant replies

By default the AI Campus Assistant answers entirely from the database using a reliable
intent-matching engine — no external API key needed, and it never dead-ends on
"no matching information found."

If you'd like the assistant to rephrase those same database facts more conversationally
using an LLM, install the optional dependency and set an API key before starting the server:

```powershell
pip install anthropic
set ANTHROPIC_API_KEY=your-key-here      # PowerShell: $env:ANTHROPIC_API_KEY="your-key-here"
```

If the key is missing, the package isn't installed, or the call fails for any reason, the
assistant automatically falls back to the plain database-generated answer.

---

## 4. Frontend setup (React + Vite)

Open a **second terminal**:

```powershell
cd campusone\frontend
npm install
npm run dev
```

- App runs at http://localhost:5173
- The Vite dev server proxies all `/api/*` requests to `http://127.0.0.1:8000`, so make sure
  the backend is running first.

---

## 5. Demo credentials

| Role    | Username   | Password    | Notes                                   |
|---------|-----------|-------------|------------------------------------------|
| Admin   | admin     | admin123    | Dr. Ramesh Venkataraman                  |
| Faculty | faculty1  | faculty123  | Dr. Anand Subramaniam, CSE department    |
| Student | student1  | student123  | Manish Kumar, 21CSE1042, CSE, Sem 5      |

The seed now creates **25 admins, 1,000 faculty, and 5,000 students** (6,025 user accounts total),
plus interconnected academic and student-life records. All generated student/faculty demo accounts use
the same role password patterns:
`faculty123` / `student123`) seeded for realistic class rosters and analytics — useful when
demonstrating faculty attendance/marks entry or admin-level reports across multiple students.

The login page has one-click buttons to autofill the three primary demo accounts.

---

## 6. Implemented features

**Student portal:** profile, accommodation/hostel details, subject-wise attendance with 75% threshold flags, marks &
grades (with a bar chart), exam timetable, weekly class timetable, fees status, library
records, placement portal (view eligible drives, apply, track application status), Campus Life (clubs, upcoming club events, attended events, volunteering, OD usage and request history),
announcements & events, AI assistant.

**Faculty portal:** profile, assigned subjects, student directory (filterable by subject),
attendance management (editable, per-student), marks entry (editable, auto-computed grade),
exam schedule, teaching timetable, announcements, AI assistant.

**Admin portal:** institution-wide dashboard (student/faculty counts, attendance, academic
performance, department breakdown), student directory, faculty directory, departments,
courses & subjects, placement portal management (add companies, create drives, review and
update applicant status, view analytics — average/highest CTC, department-wise offers),
reports & analytics (attendance and academic performance charts), announcements & events
management (create + broadcast).

**AI Campus Assistant:** a dedicated module (not the homepage) that answers using the
logged-in user's own database records — attendance, marks, CGPA/SGPA, timetable, exams,
faculty, fees, library, and placement eligibility for students, plus club memberships, club events, event attendance, volunteering, accommodation and OD requests/usage; subjects, class performance,
and schedules for faculty; institution-wide statistics for admins. Rule-based by default,
with optional LLM rephrasing (see above). Always grounds its answer in real data — it never
just says "no matching information found."

**Auth:** JWT-based login with role-based route protection on both the API and the frontend.

---


## 6A. Student-life data model and APIs

The student-life extension is normalized and connected through foreign keys:

- `students.accommodation_type` → `hostel_allocations` → `hostels` for Hosteller/Day Scholar data.
- `students` ↔ `clubs` through `club_memberships`.
- `clubs` → `club_events`.
- `students` ↔ `club_events` through `event_attendance` and `event_volunteers`.
- `students` → `od_requests` → optional `club_events`, with approved hours calculated against a 40-hour annual entitlement.
- Unique constraints prevent duplicate club membership, attendance, or volunteer records for the same student/event.

Student-life API endpoints:

- `GET /api/student/campus-life/profile`
- `GET /api/student/campus-life/clubs`
- `GET /api/student/campus-life/events/upcoming`
- `GET /api/student/campus-life/events/attended`
- `GET /api/student/campus-life/events/volunteered`
- `GET /api/student/campus-life/od`
- `GET /api/student/campus-life/overview`

The AI Assistant routes student-life questions through `app/agents/campus_life_agent.py` before the
general academic intents. It is database-grounded and always scopes records to the authenticated student.
Example supported questions include:

- “What clubs am I part of?”
- “What are my club’s upcoming events?”
- “Which events have I attended?”
- “How many events have I volunteered for?”
- “How many OD hours have I used and how many remain?”
- “Am I a hosteller or day scholar?”

## 6B. Large dataset generation

`python -m app.seed` resets and regenerates the complete dataset. The generator creates:

- 5,000 students
- 1,000 faculty
- 25 admins
- 3 departments and 3 courses
- Academic attendance, marks, exams, timetables, fees, library and placement data
- 12 hostels and hosteller allocations
- 30 clubs
- 360 club events across past and upcoming dates
- Realistic club memberships for every student
- Interconnected event attendance and volunteering
- OD requests with approved/pending/rejected states

For the larger seed, the script reuses one bcrypt hash per role and uses SQLAlchemy bulk inserts
for high-volume student-life rows. This keeps the seed substantially faster than hashing every account
independently or committing every row individually.

**Important:** after pulling this version, run `python -m app.seed` once to rebuild an older database.
The project intentionally uses a reset-and-seed workflow rather than attempting an automatic migration
of an old SQLite file.

## 7. Testing instructions

1. Start the backend, confirm `/api/health` returns `{"status": "ok"}`.
2. Start the frontend, open http://localhost:5173.
3. Log in as `student1` / `student123` → verify the dashboard shows real attendance %, CGPA,
   fee status, and upcoming exams. Click through every sidebar item.
4. Log in as `faculty1` / `faculty123` → open **Attendance**, edit a student's attended/total
   classes, click Save, confirm the percentage updates. Do the same in **Marks Entry**.
5. Log in as `admin` / `admin123` → open **Placement Portal**, add a company, create a drive,
   then log back in as a student in an eligible department to confirm the drive appears under
   "Eligible drives" and can be applied to. Return to the admin view and update that
   application's status.
6. On any role, open **AI Assistant** and try the suggested questions (e.g. "What is my
   attendance?", "Show attendance for my classes", "What is the placement summary?").

---

## 8. Architecture notes

- **Auth & scoping:** every student/faculty endpoint resolves the logged-in `User` → their
  `Student`/`Faculty` profile server-side from the JWT, so a student can never query another
  student's records by manipulating IDs in the frontend.
- **Data model:** a normalized relational schema (Users → Students/Faculty → Departments →
  Courses → Subjects → Attendance/Marks/Exams/Timetable; Companies → Drives → Applications)
  keeps every module internally consistent — e.g. a subject's attendance, marks, exam, and
  timetable records all reference the same `Subject` row and the same assigned `Faculty`.
- **AI Assistant:** intent matching happens against the same SQLAlchemy queries the REST
  endpoints use, so the assistant's answers are guaranteed to match what the dashboards show.
  The optional LLM step only rephrases; it never receives write access or invents facts.
- **Frontend:** a single `useFetch` hook + `client.ts` axios instance handles all data
  fetching and auth headers; role-based sidebars and route guards in `App.tsx` keep each
  portal's pages isolated from the others.
