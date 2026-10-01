"""
OD-aware assistant intents for students, faculty and admins.

Every answer is computed from the database through od_service (the same code
the OD screens use), scoped to the authenticated caller that the router passes
in. Nothing here reads an id, role or department out of the question text.

Each function returns (intent, answer) or None when the question is not about OD.
"""
import re
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .. import od_service as svc
from ..od_intelligence import find_dates

Answer = Optional[Tuple[str, str]]

_OD = re.compile(r"\bods?\b|\bon[- ]?duty\b", re.I)
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def mentions_od(message: str) -> bool:
    return bool(_OD.search(message))


def _has(m: str, *words) -> bool:
    return any(w in m for w in words)


def _when(req: models.ODRequest) -> str:
    if not req.start_at:
        return "date not recorded"
    if req.end_at and req.end_at.date() != req.start_at.date():
        return f"{req.start_at:%d %b %Y %H:%M} to {req.end_at:%d %b %Y %H:%M}"
    return f"{req.start_at:%d %b %Y}, {req.start_at:%H:%M}" + (f"-{req.end_at:%H:%M}" if req.end_at else "")


def _line(req: models.ODRequest) -> str:
    return (f"- #{req.id} {svc.display_name(req)} ({_when(req)}, {req.requested_hours:g}h): "
            f"{svc.STATE_LABELS.get(req.workflow_state, req.workflow_state)}")


def parse_day(message: str, today: date) -> Optional[date]:
    """The day a question refers to: today, tomorrow, a weekday name or an explicit date."""
    m = message.lower()
    if "day after tomorrow" in m:
        return today + timedelta(days=2)
    if "tomorrow" in m:
        return today + timedelta(days=1)
    if "today" in m:
        return today
    explicit = find_dates(message)
    if explicit:
        return explicit[0]
    for i, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b{name}\b", m):
            ahead = (i - today.weekday()) % 7
            return today + timedelta(days=ahead or 7)   # the coming one, never today
    return None


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------

def _my_requests(db: Session, st: models.Student):
    return (db.query(models.ODRequest).filter(models.ODRequest.student_id == st.id)
            .order_by(func.coalesce(models.ODRequest.submitted_at, models.ODRequest.request_date).desc(),
                      models.ODRequest.id.desc()))


def student(message: str, db: Session, st: models.Student) -> Answer:
    m = message.lower()
    od = mentions_od(message)
    if not od and not _has(m, "application", "clarification", "class advisor"):
        return None
    if not od and _has(m, "placement", "job", "drive", "company"):
        return None   # "my placement application" is not an OD question
    inst = svc.get_institution(db)

    # --- Can I apply (tomorrow / on a date)? ---
    if od and _has(m, "can i apply", "can i take", "can i get", "am i eligible", "eligible for", "allowed to apply",
                   "can i request", "apply for od", "apply od"):
        day = parse_day(message, svc.today())
        if day is None:
            day = svc.today() + timedelta(days=1)
            day_text = "tomorrow"
        else:
            day_text = "today" if day == svc.today() else ("tomorrow" if day == svc.today() + timedelta(days=1)
                                                             else f"on {day:%A, %d %b %Y}")
        start, end = datetime.combine(day, time(9, 0)), datetime.combine(day, time(17, 0))
        # Probe with one hour: "can you apply at all that day"; the balance figure covers longer requests.
        result = svc.evaluate(db, inst, st, start, end, 1.0)
        failed = [c for c in result["checks"] if not c["ok"]]
        bal = result["balance"]
        route = (f"Requests over {inst.hod_threshold_hours:g} hours also need HOD approval."
                 if svc.hod_in_chain(inst) else "Your class advisor decides.")
        if not failed:
            return ("od_can_apply",
                    f"Yes, you can apply for OD {day_text}. You have {bal['available_hours']:g} of "
                    f"{bal['allowance_hours']:g} OD hours available, your attendance is "
                    f"{result['attendance']['effective_pct']:g}% (minimum {result['attendance']['threshold_pct']:g}%), "
                    f"and you have no other OD request that day. {route}")
        only_overlap = {c["code"] for c in failed} <= {"overlap", "duplicate"}
        reasons = " ".join(c["message"] for c in failed)
        if only_overlap:
            return ("od_can_apply",
                    f"You already have an OD request {day_text}: {reasons} You can still apply for hours that do not "
                    f"overlap it; you have {bal['available_hours']:g} OD hours available.")
        return ("od_can_apply", f"No, you cannot apply for OD {day_text}. {reasons}")

    # --- Why was my last application rejected? ---
    if _has(m, "reject") and (_has(m, "why", "reason") or od):
        last = _my_requests(db, st).filter(models.ODRequest.workflow_state == svc.REJECTED).first()
        if last is None:
            return ("od_rejection_reason", "None of your OD requests has been rejected.")
        reason = last.decision_comment or "no reason was recorded (this request predates the approval workflow)"
        decided = f" on {last.decided_at:%d %b %Y}" if last.decided_at else ""
        return ("od_rejection_reason",
                f"Your most recent rejected OD request is #{last.id} \"{svc.display_name(last)}\" ({_when(last)}). "
                f"It was rejected{decided}. Reason: {reason}.")

    # --- Clarification ---
    if "clarification" in m:
        waiting = _my_requests(db, st).filter(models.ODRequest.workflow_state == svc.CLARIFICATION_REQUESTED).all()
        if not waiting:
            return ("od_clarification", "No OD request is waiting for a clarification from you.")
        lines = [f"- #{r.id} {svc.display_name(r)}: \"{r.clarification_text}\"" for r in waiting]
        return ("od_clarification", "Your class advisor asked for clarification on:\n" + "\n".join(lines)
                + "\nOpen the request under On-Duty (OD) to respond.")

    # --- Pending ---
    if od and _has(m, "pending", "waiting", "in progress", "open request", "awaiting"):
        rows = _my_requests(db, st).filter(models.ODRequest.workflow_state.in_(svc.IN_FLIGHT_STATES)).all()
        if not rows:
            return ("od_pending", "You have no OD requests awaiting a decision.")
        return ("od_pending", f"You have {len(rows)} OD request(s) awaiting a decision:\n" + "\n".join(_line(r) for r in rows[:10]))

    # --- Status of my last application ---
    if _has(m, "status", "last application", "last request", "latest application", "latest request", "my application"):
        last = _my_requests(db, st).filter(models.ODRequest.workflow_state != svc.DRAFT).first()
        if last is None:
            return ("od_last_status", "You have not submitted any OD requests yet.")
        text = (f"Your latest OD request is #{last.id} \"{svc.display_name(last)}\" ({_when(last)}, "
                f"{last.requested_hours:g}h). Status: {svc.STATE_LABELS.get(last.workflow_state, last.workflow_state)}.")
        if last.workflow_state == svc.APPROVED:
            text += f" {last.approved_hours:g} hours were approved."
        elif last.workflow_state == svc.REJECTED and last.decision_comment:
            text += f" Reason: {last.decision_comment}."
        elif last.workflow_state == svc.CLARIFICATION_REQUESTED:
            text += f" Your class advisor asked: \"{last.clarification_text}\"."
        elif last.workflow_state == svc.UNDER_HOD_REVIEW:
            text += " Your class advisor recommended it and it is now with the HOD."
        elif last.workflow_state in (svc.UNDER_FACULTY_REVIEW, svc.RESUBMITTED) and last.advisor:
            text += f" It is with your class advisor, {last.advisor.user.full_name}."
        return ("od_last_status", text)

    # --- Who approves ---
    if _has(m, "who approves", "who will approve", "class advisor", "approver", "who is my advisor"):
        advisor = db.query(models.AdvisorAssignment).filter(models.AdvisorAssignment.student_id == st.id).first()
        name = advisor.faculty.user.full_name if advisor else "not assigned yet"
        extra = (f" Requests over {inst.hod_threshold_hours:g} hours also go to the HOD."
                 if svc.hod_in_chain(inst) else "")
        return ("od_approver", f"Your class advisor is {name}; they review your OD requests first.{extra}")

    if not od:
        return None

    # --- Policy ---
    if _has(m, "policy", "rule", "limit", "maximum", "allowance", "entitle", "how does od"):
        return ("od_policy",
                f"OD policy: {inst.od_hours_per_semester:g} hours per semester ({inst.term_start} to {inst.term_end}); "
                f"at most {inst.max_hours_per_request:g} hours per request; attendance of at least "
                f"{inst.min_attendance_pct:g}% to apply; "
                + (f"requests over {inst.hod_threshold_hours:g} hours need HOD approval after your class advisor."
                   if svc.hod_in_chain(inst) else "your class advisor makes the decision."))

    # --- History ---
    if _has(m, "history", "list", "show my od", "all my od", "my od requests", "od requests"):
        rows = _my_requests(db, st).limit(8).all()
        if not rows:
            return ("od_history", "You have no OD requests on record.")
        return ("od_history", "Your most recent OD requests:\n" + "\n".join(_line(r) for r in rows))

    # --- Balance (default for any other OD question about hours) ---
    if _has(m, "hour", "balance", "remaining", "left", "used", "how many", "how much"):
        bal = svc.balance(db, inst, st.id)
        reserved = (f" {bal['reserved_hours']:g} more hours are in requests awaiting a decision, so "
                    f"{bal['available_hours']:g} hours are available for a new request." if bal["reserved_hours"] else "")
        return ("od_balance",
                f"You have used {bal['used_hours']:g} OD hours and have {bal['remaining_hours']:g} hours remaining "
                f"out of {bal['allowance_hours']:g} this semester.{reserved}")
    return None


def attendance_headroom(db: Session, st: models.Student) -> str:
    """How many more classes can I miss and stay above the threshold?"""
    inst = svc.get_institution(db)
    att = svc.attendance_summary(db, inst, st.id)
    t = att["threshold_pct"]
    if not att["subjects"]:
        return "No attendance has been recorded for you yet."
    lines = []
    for s in att["subjects"]:
        if s["effective_percentage"] >= t:
            lines.append(f"- {s['subject_name']} ({s['effective_percentage']:g}%): you can miss {s['can_miss']} more "
                         f"class{'es' if s['can_miss'] != 1 else ''}")
        else:
            lines.append(f"- {s['subject_name']} ({s['effective_percentage']:g}%): already below {t:g}% - attend the "
                         f"next {s['need_to_attend']} classes without a miss to recover")
    head = (f"Your overall attendance is {att['effective_pct']:g}%. To stay at or above {t:g}% in each subject "
            f"(counting each missed class as held):")
    return head + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Faculty
# ---------------------------------------------------------------------------

def faculty(message: str, db: Session, fac: models.Faculty, user: models.User) -> Answer:
    m = message.lower()
    if not (mentions_od(message) or _has(m, "approval", "approve", "advisee", "clarification")):
        return None
    from ..routers.od import od_faculty_stats
    stats = od_faculty_stats(db, fac, user)
    mine = db.query(models.ODRequest).filter(models.ODRequest.advisor_faculty_id == fac.id)

    if _has(m, "this month", "approved", "how many did i", "have i approved", "decisions"):
        return ("od_faculty_month",
                f"This month you approved {stats['approved_this_month']} OD request(s), recommended "
                f"{stats['forwarded_this_month']} to the HOD, rejected {stats['rejected_this_month']} and asked for "
                f"clarification on {stats['clarifications_this_month']}.")

    if _has(m, "clarification", "waiting on student", "awaiting student"):
        rows = mine.filter(models.ODRequest.workflow_state == svc.CLARIFICATION_REQUESTED).all()
        if not rows:
            return ("od_faculty_clarification", "No OD requests are waiting on a student's clarification.")
        return ("od_faculty_clarification", f"{len(rows)} request(s) are waiting on the student:\n"
                + "\n".join(f"- #{r.id} {r.student.user.full_name}: {svc.display_name(r)}" for r in rows[:10]))

    if _has(m, "hod"):
        return ("od_faculty_with_hod", f"{stats['with_hod']} request(s) you recommended are waiting for the HOD's decision.")

    if _has(m, "advisee", "how many students do i advise"):
        return ("od_faculty_advisees", f"You are the class advisor for {stats['advisees']} students.")

    if _has(m, "pending", "waiting", "queue", "to approve", "need my", "awaiting", "approval"):
        rows = (mine.filter(models.ODRequest.workflow_state.in_(svc.FACULTY_QUEUE_STATES))
                .order_by(models.ODRequest.submitted_at, models.ODRequest.id).limit(8).all())
        if not stats["pending"]:
            return ("od_faculty_pending", "You have no OD requests waiting for your decision.")
        lines = [f"- #{r.id} {r.student.user.full_name} ({r.student.register_number}): {svc.display_name(r)}, "
                 f"{_when(r)}, {r.requested_hours:g}h" for r in rows]
        more = f"\n...and {stats['pending'] - len(rows)} more." if stats["pending"] > len(rows) else ""
        return ("od_faculty_pending",
                f"You have {stats['pending']} OD request(s) waiting for your decision:\n" + "\n".join(lines) + more)

    return ("od_faculty_summary",
            f"OD summary for your {stats['advisees']} advisees: {stats['pending']} waiting for your decision, "
            f"{stats['awaiting_student']} waiting on the student, {stats['with_hod']} with the HOD.")


# ---------------------------------------------------------------------------
# Admin / HOD
# ---------------------------------------------------------------------------

def admin(message: str, db: Session, user: models.User) -> Answer:
    if not mentions_od(message):
        return None
    m = message.lower()
    from ..routers.od import admin_department_ids, od_analytics
    inst = svc.get_institution(db)
    scope = admin_department_ids(db, user)
    data = od_analytics(db, inst, scope)
    depts, totals = data["by_department"], data["totals"]
    scope_text = "" if scope is None else " in your department" + ("s" if len(depts) > 1 else "")

    if _has(m, "highest", "most", "top", "maximum") and _has(m, "utili", "usage", "use"):
        top = max(depts, key=lambda d: d["utilisation_pct"]) if depts else None
        if not top or not top["approved_hours"]:
            return ("od_admin_top_utilisation", "No OD hours have been approved this term yet.")
        return ("od_admin_top_utilisation",
                f"{top['department']} has the highest OD utilisation{scope_text}: {top['utilisation_pct']:g}% of its "
                f"allowance ({top['approved_hours']:,.1f} approved hours across {top['students']:,} students, "
                f"{top['avg_hours_per_student']:g}h per student).")

    if _has(m, "pending", "waiting", "awaiting", "queue"):
        lines = [f"- {d['department']}: {d['pending']} awaiting a decision ({d['pending_hod']} with the HOD)" for d in depts]
        return ("od_admin_pending",
                f"{totals['pending']} OD request(s) are awaiting a decision{scope_text}, {totals['pending_hod']} of "
                f"them waiting for the HOD:\n" + "\n".join(lines))

    if _has(m, "turnaround", "how long", "average time"):
        if totals["avg_turnaround_hours"] is None:
            return ("od_admin_turnaround", "No OD request has been decided through the workflow yet, so there is no "
                                           "turnaround figure. Imported legacy requests have no recorded decision time.")
        return ("od_admin_turnaround",
                f"Average OD turnaround is {totals['avg_turnaround_hours']:g} hours, measured over "
                f"{totals['decisions_with_turnaround']} workflow decision(s).")

    if _has(m, "approval rate", "approved", "rejected"):
        rate = "n/a" if totals["approval_rate_pct"] is None else f"{totals['approval_rate_pct']:g}%"
        return ("od_admin_approval_rate",
                f"OD approval rate{scope_text} this term is {rate}: {totals['approved']:,} approved and "
                f"{totals['rejected']:,} rejected out of {totals['requests']:,} requests.")

    if _has(m, "policy", "rule", "limit", "allowance"):
        return ("od_admin_policy",
                f"OD policy: {inst.od_hours_per_semester:g} hours per student per semester, minimum attendance "
                f"{inst.min_attendance_pct:g}%, at most {inst.max_hours_per_request:g} hours per request, approval chain "
                f"{' then '.join(svc.policy_dict(inst)['approval_chain'])}"
                + (f" (HOD for requests over {inst.hod_threshold_hours:g} hours)." if svc.hod_in_chain(inst) else "."))

    lines = []
    for d in depts:
        rate = "n/a" if d["approval_rate_pct"] is None else f"{d['approval_rate_pct']:g}%"
        lines.append(f"- {d['department']}: {d['total_requests']:,} requests, {d['approved']:,} approved, "
                     f"{d['rejected']:,} rejected, {d['pending']:,} pending; approval rate {rate}; "
                     f"{d['approved_hours']:,.1f} hours ({d['utilisation_pct']:g}% of allowance)")
    return ("od_admin_department_stats", f"Department-wise OD statistics for this term{scope_text}:\n" + "\n".join(lines))
