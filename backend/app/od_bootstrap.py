"""
Idempotent data bootstrap for the OD workflow.

Fills the tables and columns introduced by migration 0002 from data that already
exists, without inventing history:

- one Institution row carrying the OD policy,
- a class advisor for every student (same department, groups of 60),
- department heads (HODs) drawn from existing admin users,
- workflow columns on pre-existing OD requests.

It is written with plain SQL on a Connection so it can be called both from the
Alembic migration (existing database) and from the seed script (fresh database).
Running it twice changes nothing.
"""
from datetime import date, datetime

from sqlalchemy import text

ADVISOR_GROUP_SIZE = 60
DEFAULT_INSTITUTION = {
    "id": 1,
    "code": "CAMPUSONE",
    "name": "CampusOne University",
    "short_name": "CampusOne",
    "primary_color": "#0F2A4A",
    "support_email": "support@campusone.edu",
    "od_hours_per_semester": 40.0,
    "min_attendance_pct": 75.0,
    "approval_chain": "faculty,hod",
    "hod_threshold_hours": 8.0,
    "max_hours_per_request": 16.0,
}

# Legacy coarse status -> workflow state.
LEGACY_STATE = {"Approved": "Approved", "Rejected": "Rejected", "Cancelled": "Cancelled", "Pending": "UnderFacultyReview"}


def _term_for(today: date):
    """Odd semester = July-December, even semester = January-June."""
    if today.month >= 7:
        return date(today.year, 7, 1), date(today.year, 12, 31)
    return date(today.year, 1, 1), date(today.year, 6, 30)


def _combine(day, hhmm, fallback):
    if isinstance(day, str):
        day = date.fromisoformat(day[:10])
    try:
        h, m = (hhmm or fallback).split(":")[:2]
        return datetime(day.year, day.month, day.day, int(h), int(m))
    except Exception:
        h, m = fallback.split(":")
        return datetime(day.year, day.month, day.day, int(h), int(m))


def ensure_od_foundation(conn) -> dict:
    """Bring OD support data up to date. Returns a summary of what was written."""
    summary = {}

    # 1. Institution.
    if conn.execute(text("select count(*) from institutions")).scalar() == 0:
        # The term must cover the OD activity already on record.
        first = conn.execute(text("select min(request_date) from od_requests")).scalar()
        anchor = date.fromisoformat(str(first)[:10]) if first else date.today()
        start, end = _term_for(anchor)
        conn.execute(text(
            "insert into institutions (id, code, name, short_name, primary_color, support_email, "
            "od_hours_per_semester, term_start, term_end, min_attendance_pct, approval_chain, "
            "hod_threshold_hours, max_hours_per_request, created_at) values "
            "(:id, :code, :name, :short_name, :primary_color, :support_email, :od_hours_per_semester, "
            ":term_start, :term_end, :min_attendance_pct, :approval_chain, :hod_threshold_hours, "
            ":max_hours_per_request, :created_at)"),
            dict(DEFAULT_INSTITUTION, term_start=start, term_end=end, created_at=datetime.utcnow()))
        summary["institution"] = f"created ({start} to {end})"
    inst_id = conn.execute(text("select min(id) from institutions")).scalar()

    # 2. Class advisors: students of a department, in id order, in groups of 60,
    #    each group advised by the next faculty member of the same department.
    missing = conn.execute(text(
        "select s.id, s.department_id from students s "
        "where s.id not in (select student_id from advisor_assignments) order by s.department_id, s.id")).fetchall()
    if missing:
        faculty_by_dept = {}
        for fid, dept in conn.execute(text("select id, department_id from faculty order by id")):
            faculty_by_dept.setdefault(dept, []).append(fid)
        position = {}
        rows = []
        for sid, dept in missing:
            pool = faculty_by_dept.get(dept)
            if not pool:
                continue
            i = position.get(dept, 0)
            position[dept] = i + 1
            rows.append({"i": inst_id, "s": sid, "f": pool[(i // ADVISOR_GROUP_SIZE) % len(pool)]})
        if rows:
            conn.execute(text(
                "insert into advisor_assignments (institution_id, student_id, faculty_id) values (:i, :s, :f)"), rows)
        summary["advisor_assignments"] = len(rows)

    # 3. Department heads: the 2nd, 3rd, 4th... admin accounts head one department
    #    each; the first admin stays institution-wide.
    if conn.execute(text("select count(*) from department_heads")).scalar() == 0:
        admins = [r[0] for r in conn.execute(text("select id from users where role = 'admin' order by id"))]
        depts = [r[0] for r in conn.execute(text("select id from departments order by id"))]
        rows = [{"i": inst_id, "d": d, "u": u} for d, u in zip(depts, admins[1:])]
        if rows:
            conn.execute(text(
                "insert into department_heads (institution_id, department_id, user_id) values (:i, :d, :u)"), rows)
        summary["department_heads"] = len(rows)

    # 4. Pre-existing OD requests: fill workflow columns from what is already known.
    pending = conn.execute(text("select count(*) from od_requests where workflow_state is null")).scalar()
    if pending:
        events = conn.execute(text(
            "select id, title, event_date, start_time, end_time, venue from club_events "
            "where id in (select distinct event_id from od_requests where workflow_state is null)")).fetchall()
        for eid, title, day, st, en, venue in events:
            conn.execute(text(
                "update od_requests set event_name = :t, venue = :v, start_at = :s, end_at = :e "
                "where event_id = :id and workflow_state is null"),
                {"t": title, "v": venue, "s": _combine(day, st, "09:00"), "e": _combine(day, en, "17:00"), "id": eid})
        conn.execute(text(
            "update od_requests set advisor_faculty_id = "
            "(select a.faculty_id from advisor_assignments a where a.student_id = od_requests.student_id) "
            "where workflow_state is null"))
        conn.execute(text(
            "update od_requests set institution_id = :i, submitted_at = request_date, requires_hod = :f, "
            "clarification_requested = :f where workflow_state is null"), {"i": inst_id, "f": False})
        for legacy, state in LEGACY_STATE.items():
            conn.execute(text(
                "update od_requests set workflow_state = :s where workflow_state is null and status = :l"),
                {"s": state, "l": legacy})
        # Anything with an unexpected legacy status is treated as awaiting review.
        conn.execute(text("update od_requests set workflow_state = 'UnderFacultyReview' where workflow_state is null"))
        summary["od_requests_backfilled"] = pending

    return summary
