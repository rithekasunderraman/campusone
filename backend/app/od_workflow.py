"""
OD workflow engine: the only code allowed to change an OD request's state.

Guarantees
- Only transitions listed in TRANSITIONS are possible; anything else is rejected.
- Each transition is one version-checked UPDATE (optimistic concurrency): if two
  reviewers act on the same request, exactly one wins and the other gets a 409.
- Each transition writes exactly one audit row in the same transaction.
- Nothing here commits. The caller commits once, so a status change, its audit
  row, the balance check and the attendance credits succeed or fail together.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from . import od_service as svc
from .od_service import (
    DRAFT, SUBMITTED, UNDER_FACULTY_REVIEW, CLARIFICATION_REQUESTED, RESUBMITTED,
    UNDER_HOD_REVIEW, APPROVED, REJECTED, CANCELLED,
)

# (current state, action) -> new state
TRANSITIONS = {
    (DRAFT, "submit"): SUBMITTED,
    (SUBMITTED, "route_to_faculty"): UNDER_FACULTY_REVIEW,
    (UNDER_FACULTY_REVIEW, "request_clarification"): CLARIFICATION_REQUESTED,
    (RESUBMITTED, "request_clarification"): CLARIFICATION_REQUESTED,
    (CLARIFICATION_REQUESTED, "respond_clarification"): RESUBMITTED,
    (UNDER_FACULTY_REVIEW, "forward_to_hod"): UNDER_HOD_REVIEW,
    (RESUBMITTED, "forward_to_hod"): UNDER_HOD_REVIEW,
    (UNDER_FACULTY_REVIEW, "approve"): APPROVED,
    (RESUBMITTED, "approve"): APPROVED,
    (UNDER_HOD_REVIEW, "approve"): APPROVED,
    (UNDER_FACULTY_REVIEW, "reject"): REJECTED,
    (RESUBMITTED, "reject"): REJECTED,
    (UNDER_HOD_REVIEW, "reject"): REJECTED,
    (DRAFT, "cancel"): CANCELLED,
    (SUBMITTED, "cancel"): CANCELLED,
    (UNDER_FACULTY_REVIEW, "cancel"): CANCELLED,
    (CLARIFICATION_REQUESTED, "cancel"): CANCELLED,
    (RESUBMITTED, "cancel"): CANCELLED,
    (UNDER_HOD_REVIEW, "cancel"): CANCELLED,
}

# Who may perform which action.
ACTION_ROLES = {
    "submit": {"student"},
    "route_to_faculty": {"system"},
    "request_clarification": {"faculty"},
    "respond_clarification": {"student"},
    "forward_to_hod": {"faculty"},
    "approve": {"faculty", "admin"},
    "reject": {"faculty", "admin"},
    "cancel": {"student"},
}

# Coarse legacy status kept for the pre-existing read APIs.
LEGACY_STATUS = {
    DRAFT: "Draft", SUBMITTED: "Pending", UNDER_FACULTY_REVIEW: "Pending",
    CLARIFICATION_REQUESTED: "Pending", RESUBMITTED: "Pending", UNDER_HOD_REVIEW: "Pending",
    APPROVED: "Approved", REJECTED: "Rejected", CANCELLED: "Cancelled",
}


class WorkflowError(Exception):
    def __init__(self, status_code: int, code: str, message: str, extra: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}

    def detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


def allowed_actions(state: str, role: str) -> list:
    return sorted(a for (s, a), _ in TRANSITIONS.items() if s == state and role in ACTION_ROLES[a])


def _audit(db: Session, req: models.ODRequest, actor: Optional[models.User], role: str,
           action: str, old_state: Optional[str], new_state: str, comment: Optional[str]):
    db.add(models.ODAuditLog(
        institution_id=req.institution_id, request_id=req.id,
        actor_user_id=actor.id if actor else None, actor_role=role,
        action=action, old_state=old_state, new_state=new_state,
        comment=(comment or None), created_at=datetime.utcnow(),
    ))


def transition(db: Session, req: models.ODRequest, action: str, actor: Optional[models.User], role: str,
               expected_version: int, comment: Optional[str] = None, updates: Optional[dict] = None) -> None:
    """Apply one state transition. Raises WorkflowError; never commits."""
    old_state = req.workflow_state
    new_state = TRANSITIONS.get((old_state, action))
    if new_state is None:
        raise WorkflowError(409, "invalid_transition",
                            f"Cannot {action.replace('_', ' ')} a request that is "
                            f"{svc.STATE_LABELS.get(old_state, old_state)}.")
    if role not in ACTION_ROLES[action]:
        raise WorkflowError(403, "forbidden_action", f"A {role} cannot {action.replace('_', ' ')} an OD request.")
    if expected_version is None:
        raise WorkflowError(400, "version_required", "The request version is required for this action.")

    values = dict(updates or {})
    values[models.ODRequest.workflow_state] = new_state
    values[models.ODRequest.status] = LEGACY_STATUS[new_state]
    values[models.ODRequest.version] = expected_version + 1

    # The version (and state) in the WHERE clause is what makes a double action
    # impossible: a second writer matches zero rows.
    matched = (db.query(models.ODRequest)
               .filter(models.ODRequest.id == req.id,
                       models.ODRequest.version == expected_version,
                       models.ODRequest.workflow_state == old_state)
               .update(values, synchronize_session=False))
    if matched != 1:
        raise WorkflowError(409, "stale_request",
                            "This request was changed by someone else. Reload it and try again.")
    _audit(db, req, actor, role, action, old_state, new_state, comment)
    db.flush()
    db.refresh(req)


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------

def create_draft(db: Session, inst: models.Institution, student: models.Student, actor: models.User, *,
                 event_id: Optional[int], event_name: str, organizer: Optional[str], venue: Optional[str],
                 start_at: datetime, end_at: datetime, requested_hours: float, reason: Optional[str]
                 ) -> models.ODRequest:
    req = models.ODRequest(
        institution_id=inst.id, student_id=student.id, event_id=event_id,
        event_name=event_name, organizer=organizer, venue=venue,
        start_at=start_at, end_at=end_at, requested_hours=requested_hours, approved_hours=0,
        reason=reason, request_date=datetime.utcnow(),
        workflow_state=DRAFT, status=LEGACY_STATUS[DRAFT],
        requires_hod=False, clarification_requested=False, version=1,
    )
    db.add(req)
    db.flush()
    _audit(db, req, actor, "student", "create", None, DRAFT, None)
    db.flush()
    return req


def submit(db: Session, inst: models.Institution, req: models.ODRequest, student: models.Student,
           actor: models.User, expected_version: int) -> dict:
    """Validate, then Draft -> Submitted -> UnderFacultyReview in one transaction."""
    if req.workflow_state != DRAFT:
        raise WorkflowError(409, "invalid_transition",
                            f"Only a draft can be submitted (this request is "
                            f"{svc.STATE_LABELS.get(req.workflow_state, req.workflow_state)}).")
    result = svc.evaluate(db, inst, student, req.start_at, req.end_at, req.requested_hours,
                          req.event_id, svc.display_name(req), exclude_request_id=req.id)
    if not result["eligible"]:
        failed = [c for c in result["checks"] if not c["ok"]]
        raise WorkflowError(422, "validation_failed",
                            "This request cannot be submitted: " + " ".join(c["message"] for c in failed),
                            {"checks": result["checks"]})
    advisor = db.query(models.AdvisorAssignment).filter(
        models.AdvisorAssignment.student_id == student.id).first()
    if advisor is None:
        raise WorkflowError(409, "no_advisor", "No class advisor is assigned to you. Contact the department office.")

    transition(db, req, "submit", actor, "student", expected_version, updates={
        models.ODRequest.submitted_at: datetime.utcnow(),
        models.ODRequest.advisor_faculty_id: advisor.faculty_id,
        models.ODRequest.requires_hod: result["requires_hod"],
    })
    transition(db, req, "route_to_faculty", None, "system", req.version,
               comment="Routed to class advisor")
    return result


def _finalise_approval(db: Session, inst: models.Institution, req: models.ODRequest, actor: models.User,
                       role: str, expected_version: int, comment: Optional[str],
                       approved_hours: Optional[float], extra: dict) -> None:
    hours = req.requested_hours if approved_hours is None else approved_hours
    if hours <= 0 or hours > req.requested_hours + 1e-6:
        raise WorkflowError(422, "invalid_hours",
                            f"Approved hours must be between 0 and the {req.requested_hours:g} hours requested.")
    # Re-check the balance at decision time: other requests may have been approved since submission.
    bal = svc.balance(db, inst, req.student_id, exclude_request_id=req.id)
    if hours > bal["remaining_hours"] + 1e-6:
        raise WorkflowError(409, "balance_exceeded",
                            f"Approving {hours:g} hours would exceed the student's OD allowance "
                            f"({bal['remaining_hours']:g} hours left of {bal['allowance_hours']:g}).")
    updates = {
        models.ODRequest.approved_hours: hours,
        models.ODRequest.decided_at: datetime.utcnow(),
        models.ODRequest.decision_comment: comment or None,
        models.ODRequest.clarification_requested: False,
    }
    updates.update(extra)
    transition(db, req, "approve", actor, role, expected_version, comment, updates)
    # Attendance adjustment, in the same transaction as the approval.
    for subject_id, classes in svc.class_credits(db, req.student_id, req.start_at, req.end_at).items():
        db.add(models.ODAttendanceCredit(
            institution_id=req.institution_id, request_id=req.id, student_id=req.student_id,
            subject_id=subject_id, classes_credited=classes))
    db.flush()


def faculty_approve(db: Session, inst: models.Institution, req: models.ODRequest, faculty: models.Faculty,
                    actor: models.User, expected_version: int, comment: Optional[str],
                    approved_hours: Optional[float] = None) -> str:
    """Approve as class advisor. Forwards to the HOD when the policy requires sign-off."""
    if req.requires_hod:
        head = db.query(models.DepartmentHead).filter(
            models.DepartmentHead.department_id == req.student.department_id).first()
        transition(db, req, "forward_to_hod", actor, "faculty", expected_version,
                   comment or "Recommended for approval", {
                       models.ODRequest.reviewed_by_faculty_id: faculty.id,
                       models.ODRequest.hod_user_id: head.user_id if head else None,
                       models.ODRequest.clarification_requested: False,
                   })
        return UNDER_HOD_REVIEW
    _finalise_approval(db, inst, req, actor, "faculty", expected_version, comment, approved_hours,
                       {models.ODRequest.reviewed_by_faculty_id: faculty.id})
    return APPROVED


def hod_approve(db: Session, inst: models.Institution, req: models.ODRequest, actor: models.User,
                expected_version: int, comment: Optional[str], approved_hours: Optional[float] = None) -> str:
    if req.workflow_state != UNDER_HOD_REVIEW:
        raise WorkflowError(409, "invalid_transition",
                            "Only requests awaiting HOD review can be approved here "
                            f"(this one is {svc.STATE_LABELS.get(req.workflow_state, req.workflow_state)}).")
    _finalise_approval(db, inst, req, actor, "admin", expected_version, comment, approved_hours,
                       {models.ODRequest.hod_user_id: actor.id})
    return APPROVED


def reject(db: Session, req: models.ODRequest, actor: models.User, role: str, expected_version: int,
           comment: Optional[str], faculty: Optional[models.Faculty] = None) -> None:
    if not (comment or "").strip():
        raise WorkflowError(422, "comment_required", "A reason is required when rejecting a request.")
    if role == "admin" and req.workflow_state != UNDER_HOD_REVIEW:
        raise WorkflowError(409, "invalid_transition", "Only requests awaiting HOD review can be rejected here.")
    updates = {
        models.ODRequest.approved_hours: 0,
        models.ODRequest.decided_at: datetime.utcnow(),
        models.ODRequest.decision_comment: comment.strip(),
        models.ODRequest.clarification_requested: False,
    }
    if faculty is not None:
        updates[models.ODRequest.reviewed_by_faculty_id] = faculty.id
    if role == "admin":
        updates[models.ODRequest.hod_user_id] = actor.id
    transition(db, req, "reject", actor, role, expected_version, comment.strip(), updates)


def request_clarification(db: Session, req: models.ODRequest, faculty: models.Faculty, actor: models.User,
                          expected_version: int, comment: Optional[str]) -> None:
    if not (comment or "").strip():
        raise WorkflowError(422, "comment_required", "Say what needs to be clarified.")
    transition(db, req, "request_clarification", actor, "faculty", expected_version, comment.strip(), {
        models.ODRequest.clarification_requested: True,
        models.ODRequest.clarification_text: comment.strip(),
        models.ODRequest.clarification_response: None,
        models.ODRequest.reviewed_by_faculty_id: faculty.id,
    })


def respond_clarification(db: Session, req: models.ODRequest, actor: models.User,
                          expected_version: int, response: Optional[str]) -> None:
    if not (response or "").strip():
        raise WorkflowError(422, "comment_required", "A response is required.")
    transition(db, req, "respond_clarification", actor, "student", expected_version, response.strip(), {
        models.ODRequest.clarification_requested: False,
        models.ODRequest.clarification_response: response.strip(),
    })


def cancel(db: Session, req: models.ODRequest, actor: models.User, expected_version: int,
           comment: Optional[str]) -> None:
    transition(db, req, "cancel", actor, "student", expected_version, comment, {
        models.ODRequest.cancelled_at: datetime.utcnow(),
        models.ODRequest.clarification_requested: False,
    })
