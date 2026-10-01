"""
Deterministic OD rules: policy lookup, balance, attendance, conflicts and
eligibility. Nothing in this module calls an LLM - these numbers are the single
source of truth used by the API, the workflow engine and the AI assistant.
"""
import math
import re
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models

# Workflow states
DRAFT = "Draft"
SUBMITTED = "Submitted"
UNDER_FACULTY_REVIEW = "UnderFacultyReview"
CLARIFICATION_REQUESTED = "ClarificationRequested"
RESUBMITTED = "Resubmitted"
UNDER_HOD_REVIEW = "UnderHODReview"
APPROVED = "Approved"
REJECTED = "Rejected"
CANCELLED = "Cancelled"

ALL_STATES = [DRAFT, SUBMITTED, UNDER_FACULTY_REVIEW, CLARIFICATION_REQUESTED, RESUBMITTED,
              UNDER_HOD_REVIEW, APPROVED, REJECTED, CANCELLED]
TERMINAL_STATES = {APPROVED, REJECTED, CANCELLED}
# Submitted and still awaiting a decision: these reserve OD hours.
IN_FLIGHT_STATES = [SUBMITTED, UNDER_FACULTY_REVIEW, CLARIFICATION_REQUESTED, RESUBMITTED, UNDER_HOD_REVIEW]
# States that occupy the student's calendar for overlap/duplicate checks.
BLOCKING_STATES = IN_FLIGHT_STATES + [APPROVED]
FACULTY_QUEUE_STATES = [UNDER_FACULTY_REVIEW, RESUBMITTED]

STATE_LABELS = {
    DRAFT: "Draft", SUBMITTED: "Submitted", UNDER_FACULTY_REVIEW: "Under faculty review",
    CLARIFICATION_REQUESTED: "Clarification requested", RESUBMITTED: "Resubmitted",
    UNDER_HOD_REVIEW: "Under HOD review", APPROVED: "Approved", REJECTED: "Rejected", CANCELLED: "Cancelled",
}


def get_institution(db: Session) -> models.Institution:
    inst = db.query(models.Institution).order_by(models.Institution.id).first()
    if inst is None:
        raise HTTPException(status_code=500, detail="Institution policy is not configured.")
    return inst


def policy_dict(inst: models.Institution) -> dict:
    return {
        "institution": inst.name,
        "od_hours_per_semester": inst.od_hours_per_semester,
        "term_start": str(inst.term_start),
        "term_end": str(inst.term_end),
        "min_attendance_pct": inst.min_attendance_pct,
        "approval_chain": inst.approval_chain.split(","),
        "hod_threshold_hours": inst.hod_threshold_hours,
        "max_hours_per_request": inst.max_hours_per_request,
    }


def hod_in_chain(inst: models.Institution) -> bool:
    return "hod" in [p.strip() for p in (inst.approval_chain or "").split(",")]


def requires_hod(inst: models.Institution, hours: float) -> bool:
    return hod_in_chain(inst) and hours > (inst.hod_threshold_hours or 0)


def _term_bounds(inst: models.Institution):
    start = datetime.combine(inst.term_start, time.min)
    end = datetime.combine(inst.term_end, time.min) + timedelta(days=1)
    return start, end


def _when(model=models.ODRequest):
    """The moment an OD request counts against: its start, or its filing date for old rows."""
    return func.coalesce(model.start_at, model.request_date)


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

def balance(db: Session, inst: models.Institution, student_id: int, exclude_request_id: Optional[int] = None) -> dict:
    start, end = _term_bounds(inst)
    base = db.query(models.ODRequest).filter(
        models.ODRequest.student_id == student_id, _when() >= start, _when() < end)
    if exclude_request_id:
        base = base.filter(models.ODRequest.id != exclude_request_id)
    used = base.filter(models.ODRequest.workflow_state == APPROVED).with_entities(
        func.coalesce(func.sum(models.ODRequest.approved_hours), 0.0)).scalar() or 0.0
    reserved = base.filter(models.ODRequest.workflow_state.in_(IN_FLIGHT_STATES)).with_entities(
        func.coalesce(func.sum(models.ODRequest.requested_hours), 0.0)).scalar() or 0.0
    allowance = float(inst.od_hours_per_semester)
    remaining = max(0.0, allowance - used)
    return {
        "allowance_hours": round(allowance, 1),
        "used_hours": round(used, 1),
        "reserved_hours": round(reserved, 1),          # awaiting a decision
        "remaining_hours": round(remaining, 1),         # allowance - approved
        "available_hours": round(max(0.0, remaining - reserved), 1),  # what a new request may ask for
        "term_start": str(inst.term_start),
        "term_end": str(inst.term_end),
    }


# ---------------------------------------------------------------------------
# Attendance (with OD credits)
# ---------------------------------------------------------------------------

def classes_can_miss(attended: int, total: int, threshold_pct: float) -> int:
    """How many further classes may be missed (each also adding to the total) while staying at/above threshold."""
    t = threshold_pct / 100.0
    if t <= 0:
        return 10 ** 6
    if total == 0 or attended / total < t:
        return 0
    return max(0, math.floor(attended / t - total + 1e-9))


def classes_needed(attended: int, total: int, threshold_pct: float) -> int:
    """How many consecutive classes must be attended to climb back to the threshold."""
    t = threshold_pct / 100.0
    if total == 0 or attended / total >= t or t >= 1:
        return 0
    return max(0, math.ceil((t * total - attended) / (1 - t) - 1e-9))


def attendance_summary(db: Session, inst: models.Institution, student_id: int) -> dict:
    records = db.query(models.Attendance).filter(models.Attendance.student_id == student_id).all()
    credits = dict(
        db.query(models.ODAttendanceCredit.subject_id, func.sum(models.ODAttendanceCredit.classes_credited))
        .filter(models.ODAttendanceCredit.student_id == student_id)
        .group_by(models.ODAttendanceCredit.subject_id).all())
    threshold = float(inst.min_attendance_pct)
    subjects, tot, att, eff = [], 0, 0, 0
    for a in records:
        credit = int(credits.get(a.subject_id, 0) or 0)
        effective = min(a.total_classes, a.attended_classes + credit)
        tot += a.total_classes
        att += a.attended_classes
        eff += effective
        subjects.append({
            "subject_id": a.subject_id,
            "subject_code": a.subject.code,
            "subject_name": a.subject.name,
            "total_classes": a.total_classes,
            "attended_classes": a.attended_classes,
            "od_credited_classes": credit,
            "percentage": round(a.attended_classes / a.total_classes * 100, 1) if a.total_classes else 0.0,
            "effective_percentage": round(effective / a.total_classes * 100, 1) if a.total_classes else 0.0,
            "can_miss": classes_can_miss(effective, a.total_classes, threshold),
            "need_to_attend": classes_needed(effective, a.total_classes, threshold),
        })
    return {
        "threshold_pct": threshold,
        "total_classes": tot,
        "attended_classes": att,
        "overall_pct": round(att / tot * 100, 1) if tot else 0.0,
        "effective_pct": round(eff / tot * 100, 1) if tot else 0.0,
        "can_miss_overall": classes_can_miss(eff, tot, threshold),
        "subjects": subjects,
    }


_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _hhmm(value: str, fallback: time) -> time:
    try:
        h, m = value.split(":")[:2]
        return time(int(h), int(m))
    except Exception:
        return fallback


def class_credits(db: Session, student_id: int, start_at: datetime, end_at: datetime) -> dict:
    """Timetabled classes of this student that fall inside an OD window: {subject_id: classes}."""
    subject_ids = [r[0] for r in db.query(models.Attendance.subject_id)
                   .filter(models.Attendance.student_id == student_id).all()]
    if not subject_ids or not start_at or not end_at:
        return {}
    slots = db.query(models.TimetableSlot).filter(models.TimetableSlot.subject_id.in_(subject_ids)).all()
    result: dict = {}
    day = start_at.date()
    while day <= end_at.date():
        name = _DAYS[day.weekday()]
        for s in slots:
            if s.day_of_week != name:
                continue
            s_start = datetime.combine(day, _hhmm(s.start_time, time(0, 0)))
            s_end = datetime.combine(day, _hhmm(s.end_time, time(23, 59)))
            if s_start < end_at and start_at < s_end:
                result[s.subject_id] = result.get(s.subject_id, 0) + 1
        day += timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def normalise_name(name: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def display_name(req: models.ODRequest) -> str:
    return req.event_name or (req.event.title if req.event else None) or "OD request"


def find_conflicts(db: Session, student_id: int, start_at: datetime, end_at: datetime,
                   event_id: Optional[int], event_name: Optional[str],
                   exclude_request_id: Optional[int] = None):
    """Returns (duplicates, overlaps) among the student's own active requests.

    A duplicate is an overlapping request for the same event; any other overlapping
    request is a plain overlap. Rejected, cancelled and draft requests never block.
    """
    q = db.query(models.ODRequest).filter(
        models.ODRequest.student_id == student_id,
        models.ODRequest.workflow_state.in_(BLOCKING_STATES),
        models.ODRequest.start_at < end_at,
        models.ODRequest.end_at > start_at,
    )
    if exclude_request_id:
        q = q.filter(models.ODRequest.id != exclude_request_id)
    wanted = normalise_name(event_name)
    duplicates, overlaps = [], []
    for other in q.order_by(models.ODRequest.start_at).all():
        same_event = (event_id is not None and other.event_id == event_id) or \
                     (wanted and normalise_name(display_name(other)) == wanted)
        (duplicates if same_event else overlaps).append(other)
    return duplicates, overlaps


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def _fmt(dt: datetime) -> str:
    return dt.strftime("%d %b %Y %H:%M")


def evaluate(db: Session, inst: models.Institution, student: models.Student,
             start_at: Optional[datetime], end_at: Optional[datetime], requested_hours: Optional[float],
             event_id: Optional[int] = None, event_name: Optional[str] = None,
             exclude_request_id: Optional[int] = None) -> dict:
    """Run every submission rule and return a structured, explainable result."""
    checks = []

    def add(code, ok, message):
        checks.append({"code": code, "ok": bool(ok), "message": message})

    # 1. Dates and hours
    dates_ok = False
    if not start_at or not end_at:
        add("dates", False, "Start and end date/time are required.")
    elif end_at <= start_at:
        add("dates", False, "The end must be after the start.")
    elif start_at.date() < inst.term_start or end_at.date() > inst.term_end:
        add("dates", False, f"OD must fall within the current term ({inst.term_start} to {inst.term_end}).")
    else:
        dates_ok = True
        add("dates", True, f"{_fmt(start_at)} to {_fmt(end_at)} is within the current term.")

    hours_ok = False
    if requested_hours is None or requested_hours <= 0:
        add("hours", False, "Requested hours must be greater than zero.")
    elif requested_hours > inst.max_hours_per_request:
        add("hours", False, f"A single request may cover at most {inst.max_hours_per_request:g} hours "
                            f"(you asked for {requested_hours:g}).")
    elif dates_ok and requested_hours > (end_at - start_at).total_seconds() / 3600 + 1e-6:
        add("hours", False, f"{requested_hours:g} hours is longer than the selected time window.")
    else:
        hours_ok = True
        add("hours", True, f"{requested_hours:g} hours requested (limit {inst.max_hours_per_request:g} per request).")

    # 2. Balance
    bal = balance(db, inst, student.id, exclude_request_id)
    if hours_ok:
        enough = requested_hours <= bal["available_hours"] + 1e-6
        add("balance", enough,
            f"{bal['available_hours']:g} of {bal['allowance_hours']:g} hours available "
            f"({bal['used_hours']:g} used, {bal['reserved_hours']:g} awaiting decision)"
            + ("." if enough else f" - not enough for {requested_hours:g} hours."))
    else:
        add("balance", False, f"{bal['available_hours']:g} of {bal['allowance_hours']:g} hours available.")

    # 3. Duplicate and overlap
    if dates_ok:
        duplicates, overlaps = find_conflicts(db, student.id, start_at, end_at, event_id, event_name, exclude_request_id)
        if duplicates:
            d = duplicates[0]
            add("duplicate", False, f"You already have a request for this event at an overlapping time "
                                    f"(#{d.id}, {STATE_LABELS.get(d.workflow_state, d.workflow_state)}).")
        else:
            add("duplicate", True, "No existing request for this event.")
        if overlaps:
            o = overlaps[0]
            add("overlap", False, f"Overlaps your request #{o.id} \"{display_name(o)}\" "
                                  f"({_fmt(o.start_at)} to {_fmt(o.end_at)}, "
                                  f"{STATE_LABELS.get(o.workflow_state, o.workflow_state)}).")
        else:
            add("overlap", True, "No overlap with your other OD requests.")
    else:
        add("duplicate", False, "Cannot check for duplicates until the dates are valid.")
        add("overlap", False, "Cannot check for overlaps until the dates are valid.")

    # 4. Attendance threshold
    att = attendance_summary(db, inst, student.id)
    att_ok = att["effective_pct"] >= att["threshold_pct"]
    add("attendance", att_ok,
        f"Attendance is {att['effective_pct']:g}% (minimum {att['threshold_pct']:g}% required)"
        + ("." if att_ok else " - below the eligibility threshold."))

    needs_hod = bool(hours_ok and requires_hod(inst, requested_hours))
    return {
        "eligible": all(c["ok"] for c in checks),
        "checks": checks,
        "balance": bal,
        "attendance": {k: att[k] for k in ("threshold_pct", "overall_pct", "effective_pct", "can_miss_overall")},
        "requires_hod": needs_hod,
        "approval_route": ["Class advisor", "HOD"] if needs_hod else ["Class advisor"],
        "classes_affected": sum(class_credits(db, student.id, start_at, end_at).values()) if dates_ok else 0,
    }


def explain(result: dict) -> str:
    """Plain-English, fully deterministic summary of an eligibility result."""
    failed = [c for c in result["checks"] if not c["ok"]]
    if not failed:
        route = " then ".join(result["approval_route"])
        return (f"You can apply. {result['checks'][2]['message']} "
                f"This request will go to: {route}.")
    return "You cannot submit this request yet: " + " ".join(c["message"] for c in failed)


def search_filter(q, term: Optional[str]):
    """Filter an ODRequest query (already joined to Student and User) by a free-text term."""
    if not term or not term.strip():
        return q
    like = f"%{term.strip().lower()}%"
    return q.filter(or_(
        func.lower(models.User.full_name).like(like),
        func.lower(models.Student.register_number).like(like),
        func.lower(func.coalesce(models.ODRequest.event_name, "")).like(like),
    ))


def today() -> date:
    return date.today()
