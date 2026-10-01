# CampusOne Student-Life Expansion

## Dataset scale
- 5,000 students
- 1,000 faculty
- 25 admins
- 30 clubs
- 360 club events
- ~60% hostellers with hostel allocations
- 1–4 club memberships per student
- Interconnected event attendance, volunteering and OD requests

## Backend
New SQLAlchemy entities:
`Hostel`, `HostelAllocation`, `Club`, `ClubMembership`, `ClubEvent`,
`EventAttendance`, `EventVolunteer`, `ODRequest`.

New student-life router:
`app/routers/campus_life.py`

New grounded intent agent:
`app/agents/campus_life_agent.py`

Reference SQL:
`backend/sql/student_life.sql`

## Frontend
New student page:
`frontend/src/pages/student/CampusLife.tsx`

New route:
`/student/campus-life`

The page shows accommodation, club memberships, upcoming events, attendance,
volunteering, and OD usage/request history.

## Re-seeding
Delete/reset the old SQLite database by running:

```bash
cd backend
python -m app.seed
```

The seed script already calls `drop_all()` and `create_all()`, so it rebuilds
the schema and all data from scratch.

## AI examples
The assistant now answers:
- What clubs am I part of?
- What are my club's upcoming events?
- Which events have I attended?
- How many events have I volunteered for?
- How many OD hours have I used and how many remain?
- Am I a hosteller or day scholar?
- Show my OD request status.
