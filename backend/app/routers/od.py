"""Enterprise OD (On-Duty) workflow API for students, faculty (class advisors) and admins/HODs."""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import config, models, od_intelligence
from .. import od_service as svc
from .. import od_workflow as wf
from ..auth import get_current_user, require_role
from ..database import get_db
from ..storage import StorageError, get_storage, new_key
from ..utils import get_faculty_or_404, get_student_or_404, paginate

student_router = APIRouter(prefix="/api/student/od", tags=["od-student"])
faculty_router = APIRouter(prefix="/api/faculty/od", tags=["od-faculty"])
admin_router = APIRouter(prefix="/api/admin/od", tags=["od-admin"])
shared_router = APIRouter(prefix="/api/od", tags=["od"])

require_student = require_role("student")
require_faculty = require_role("faculty")
require_admin = require_role("admin")

ALLOWED_TYPES = {
    "application/pdf": b"%PDF",
    "image/png": b"\x89PNG",
    "image/jpeg": b"\xff\xd8\xff",
    "image/webp": b"RIFF",
    "text/plain": b"",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def unit_of_work(db: Session):
    """Commit once on success; roll everything back on any failure."""
    try:
        yield
        db.commit()
    except wf.WorkflowError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail())
    except Exception:
        db.rollback()
        raise


def _iso(value):
    return value.isoformat() if value else None


def _flags(req: models.ODRequest) -> list:
    try:
        return json.loads(req.review_flags) if req.review_flags else []
    except ValueError:
        return []


def _doc_dict(doc: models.ODDocument) -> dict:
    try:
        fields = json.loads(doc.extracted_fields) if doc.extracted_fields else None
    except ValueError:
        fields = None
    return {
        "id": doc.id, "filename": doc.filename, "content_type": doc.content_type,
        "size_bytes": doc.size_bytes, "uploaded_at": _iso(doc.uploaded_at),
        "extraction_status": doc.extraction_status, "extracted_fields": fields,
        "extracted_text_preview": (doc.extracted_text or "")[:600] or None,
    }


def request_dict(req: models.ODRequest, role: str, detail: bool = False) -> dict:
    st = req.student
    data = {
        "id": req.id,
        "version": req.version,
        "state": req.workflow_state,
        "state_label": svc.STATE_LABELS.get(req.workflow_state, req.workflow_state),
        "status": req.status,
        "event_id": req.event_id,
        "event_name": svc.display_name(req),
        "organizer": req.organizer,
        "venue": req.venue,
        "start_at": _iso(req.start_at),
        "end_at": _iso(req.end_at),
        "requested_hours": req.requested_hours,
        "approved_hours": req.approved_hours or 0,
        "reason": req.reason,
        "created_at": _iso(req.request_date),
        "submitted_at": _iso(req.submitted_at),
        "decided_at": _iso(req.decided_at),
        "cancelled_at": _iso(req.cancelled_at),
        "requires_hod": bool(req.requires_hod),
        "clarification_requested": bool(req.clarification_requested),
        "clarification_text": req.clarification_text,
        "clarification_response": req.clarification_response,
        "decision_comment": req.decision_comment,
        "student": {
            "id": st.id, "full_name": st.user.full_name, "register_number": st.register_number,
            "department_code": st.department.code, "semester": st.semester,
        },
        "advisor_name": req.advisor.user.full_name if req.advisor else None,
        "hod_name": req.hod_user.full_name if req.hod_user else None,
        "document_count": len(req.documents),
        "allowed_actions": wf.allowed_actions(req.workflow_state, role),
    }
    # Review flags are advisory notes for approvers; students do not see them.
    if role != "student":
        data["flags"] = _flags(req)
    if detail:
        data["documents"] = [_doc_dict(d) for d in req.documents]
        data["timeline"] = [{
            "id": a.id, "action": a.action, "old_state": a.old_state, "new_state": a.new_state,
            "new_state_label": svc.STATE_LABELS.get(a.new_state, a.new_state),
            "actor_role": a.actor_role, "actor_name": a.actor.full_name if a.actor else "System",
            "comment": a.comment, "at": _iso(a.created_at),
        } for a in req.audit_logs]
        data["attendance_credits"] = [{
            "subject_code": c.subject.code, "subject_name": c.subject.name, "classes": c.classes_credited,
        } for c in req.attendance_credits]
    return data


def _base_query(db: Session):
    return (db.query(models.ODRequest)
            .join(models.Student, models.Student.id == models.ODRequest.student_id)
            .join(models.User, models.User.id == models.Student.user_id)
            .options(joinedload(models.ODRequest.student).joinedload(models.Student.user),
                     joinedload(models.ODRequest.student).joinedload(models.Student.department),
                     joinedload(models.ODRequest.event)))


def _get_request(db: Session, request_id: int) -> models.ODRequest:
    req = db.query(models.ODRequest).filter(models.ODRequest.id == request_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="OD request not found")
    return req


def _owned_request(db: Session, student: models.Student, request_id: int) -> models.ODRequest:
    req = _get_request(db, request_id)
    if req.student_id != student.id:
        # Do not reveal whether another student's request exists.
        raise HTTPException(status_code=404, detail="OD request not found")
    return req


def _advised_request(db: Session, faculty: models.Faculty, request_id: int) -> models.ODRequest:
    req = _get_request(db, request_id)
    if req.advisor_faculty_id != faculty.id:
        raise HTTPException(status_code=404, detail="OD request not found in your advisees' requests")
    return req


def admin_department_ids(db: Session, user: models.User) -> Optional[list]:
    """Departments this admin heads, or None when the admin is institution-wide."""
    ids = [r[0] for r in db.query(models.DepartmentHead.department_id)
           .filter(models.DepartmentHead.user_id == user.id).all()]
    return ids or None


def _scoped_request(db: Session, user: models.User, request_id: int) -> models.ODRequest:
    req = _get_request(db, request_id)
    scope = admin_department_ids(db, user)
    if scope is not None and req.student.department_id not in scope:
        raise HTTPException(status_code=404, detail="OD request not found in your department")
    return req


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"File is too large (limit {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")
    ctype = (upload.content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload a PDF, PNG, JPEG, WEBP or text file.")
    if not data.startswith(ALLOWED_TYPES[ctype]):
        raise HTTPException(status_code=415, detail="The file content does not match its type.")
    return data


def _attach_document(db: Session, req: models.ODRequest, upload: UploadFile, data: bytes) -> models.ODDocument:
    ctype = (upload.content_type or "").split(";")[0].strip().lower()
    key = new_key(f"od/{req.institution_id}/{req.id}", upload.filename or "document")
    get_storage().save(key, data, ctype)
    doc = models.ODDocument(
        institution_id=req.institution_id, request_id=req.id,
        filename=(upload.filename or "document")[:200], storage_path=key, content_type=ctype,
        size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        uploaded_at=datetime.utcnow(), extraction_status="pending",
    )
    db.add(doc)
    db.flush()
    return doc


def _discard(key: Optional[str]):
    if key:
        try:
            get_storage().delete(key)
        except StorageError:
            pass


class ActionPayload(BaseModel):
    version: int
    comment: Optional[str] = None
    approved_hours: Optional[float] = None


class ClarificationResponse(BaseModel):
    version: int
    response: str


class EligibilityRequest(BaseModel):
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    requested_hours: Optional[float] = None
    event_id: Optional[int] = None
    event_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------

@student_router.get("/balance")
def student_balance(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    inst = svc.get_institution(db)
    advisor = db.query(models.AdvisorAssignment).filter(models.AdvisorAssignment.student_id == st.id).first()
    counts = dict(db.query(models.ODRequest.workflow_state, func.count(models.ODRequest.id))
                  .filter(models.ODRequest.student_id == st.id).group_by(models.ODRequest.workflow_state).all())
    return {
        "balance": svc.balance(db, inst, st.id),
        "attendance": svc.attendance_summary(db, inst, st.id),
        "policy": svc.policy_dict(inst),
        "advisor_name": advisor.faculty.user.full_name if advisor else None,
        "counts": {
            "open": sum(counts.get(s, 0) for s in svc.IN_FLIGHT_STATES),
            "needs_action": counts.get(svc.CLARIFICATION_REQUESTED, 0),
            "approved": counts.get(svc.APPROVED, 0),
            "rejected": counts.get(svc.REJECTED, 0),
            "draft": counts.get(svc.DRAFT, 0),
        },
    }


@student_router.post("/eligibility")
def student_eligibility(payload: EligibilityRequest, db: Session = Depends(get_db),
                        user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    inst = svc.get_institution(db)
    result = svc.evaluate(db, inst, st, payload.start_at, payload.end_at, payload.requested_hours,
                          payload.event_id, payload.event_name)
    result["explanation"] = od_intelligence.explain_eligibility(result)
    return result


@student_router.get("/events")
def student_events(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    """Club events the student can pick when applying (their clubs, recent and upcoming)."""
    st = get_student_or_404(db, user)
    club_ids = [m.club_id for m in db.query(models.ClubMembership).filter_by(student_id=st.id).all()]
    if not club_ids:
        return []
    since = svc.today() - timedelta(days=14)
    events = (db.query(models.ClubEvent).options(joinedload(models.ClubEvent.club))
              .filter(models.ClubEvent.club_id.in_(club_ids), models.ClubEvent.event_date >= since)
              .order_by(models.ClubEvent.event_date).limit(40).all())
    return [{
        "event_id": e.id, "title": e.title, "club_name": e.club.name, "date": str(e.event_date),
        "start_time": e.start_time, "end_time": e.end_time, "venue": e.venue,
    } for e in events]


@student_router.post("/requests", status_code=201)
async def create_request(
    background: BackgroundTasks,
    event_name: str = Form(""),
    start_at: datetime = Form(...),
    end_at: datetime = Form(...),
    requested_hours: float = Form(...),
    event_id: Optional[int] = Form(None),
    organizer: str = Form(""),
    venue: str = Form(""),
    reason: str = Form(""),
    submit: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_student),
):
    st = get_student_or_404(db, user)
    inst = svc.get_institution(db)
    event = None
    if event_id is not None:
        event = db.query(models.ClubEvent).filter(models.ClubEvent.id == event_id).first()
        if event is None:
            raise HTTPException(status_code=404, detail="The selected event does not exist.")
    name = (event_name or "").strip() or (event.title if event else "")
    if not name:
        raise HTTPException(status_code=422, detail="An event name is required.")
    data = await _read_upload(file) if file is not None and file.filename else None

    key = None
    try:
        with unit_of_work(db):
            req = wf.create_draft(
                db, inst, st, user, event_id=event_id, event_name=name[:200],
                organizer=(organizer or "").strip()[:200] or (event.club.name if event else None),
                venue=(venue or "").strip()[:200] or (event.venue if event else None),
                start_at=start_at.replace(tzinfo=None), end_at=end_at.replace(tzinfo=None),
                requested_hours=requested_hours, reason=(reason or "").strip() or None)
            doc = None
            if data is not None:
                doc = _attach_document(db, req, file, data)
                key = doc.storage_path
            if submit:
                wf.submit(db, inst, req, st, user, req.version)
            request_id, doc_id = req.id, (doc.id if doc else None)
    except Exception:
        _discard(key)
        raise
    if doc_id:
        background.add_task(od_intelligence.analyse_document, doc_id)
    return request_dict(_get_request(db, request_id), "student", detail=True)


@student_router.get("/requests")
def list_my_requests(page: int = 1, page_size: int = 10, status: Optional[str] = None, q: Optional[str] = None,
                     db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    query = _base_query(db).filter(models.ODRequest.student_id == st.id)
    if status == "open":
        query = query.filter(models.ODRequest.workflow_state.in_(svc.IN_FLIGHT_STATES))
    elif status == "closed":
        query = query.filter(models.ODRequest.workflow_state.in_(list(svc.TERMINAL_STATES)))
    elif status:
        if status not in svc.ALL_STATES:
            raise HTTPException(status_code=422, detail=f"Unknown status filter: {status}")
        query = query.filter(models.ODRequest.workflow_state == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(models.ODRequest.event_name, "")).like(like))
    query = query.order_by(func.coalesce(models.ODRequest.submitted_at, models.ODRequest.request_date).desc(),
                           models.ODRequest.id.desc())
    return paginate(query, page, page_size, lambda r: request_dict(r, "student"))


@student_router.get("/requests/{request_id}")
def get_my_request(request_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    return request_dict(_owned_request(db, st, request_id), "student", detail=True)


@student_router.post("/requests/{request_id}/submit")
def submit_request(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                   user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    inst = svc.get_institution(db)
    req = _owned_request(db, st, request_id)
    with unit_of_work(db):
        wf.submit(db, inst, req, st, user, payload.version)
    return request_dict(_get_request(db, request_id), "student", detail=True)


@student_router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                   user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    req = _owned_request(db, st, request_id)
    with unit_of_work(db):
        wf.cancel(db, req, user, payload.version, payload.comment)
    return request_dict(_get_request(db, request_id), "student", detail=True)


@student_router.post("/requests/{request_id}/clarification-response")
def respond_to_clarification(request_id: int, payload: ClarificationResponse, db: Session = Depends(get_db),
                             user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    req = _owned_request(db, st, request_id)
    with unit_of_work(db):
        wf.respond_clarification(db, req, user, payload.version, payload.response)
    return request_dict(_get_request(db, request_id), "student", detail=True)


@student_router.post("/requests/{request_id}/documents", status_code=201)
async def add_document(request_id: int, background: BackgroundTasks, file: UploadFile = File(...),
                       db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    req = _owned_request(db, st, request_id)
    if req.workflow_state in svc.TERMINAL_STATES:
        raise HTTPException(status_code=409, detail="Documents cannot be added to a closed request.")
    if len(req.documents) >= 5:
        raise HTTPException(status_code=409, detail="A request can hold at most 5 documents.")
    data = await _read_upload(file)
    key = None
    try:
        with unit_of_work(db):
            doc = _attach_document(db, req, file, data)
            key, doc_id = doc.storage_path, doc.id
    except Exception:
        _discard(key)
        raise
    background.add_task(od_intelligence.analyse_document, doc_id)
    return _doc_dict(db.get(models.ODDocument, doc_id))


# ---------------------------------------------------------------------------
# Faculty (class advisor)
# ---------------------------------------------------------------------------

@faculty_router.get("/stats")
def faculty_stats(db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    return od_faculty_stats(db, fac, user)


def od_faculty_stats(db: Session, fac: models.Faculty, user: models.User) -> dict:
    counts = dict(db.query(models.ODRequest.workflow_state, func.count(models.ODRequest.id))
                  .filter(models.ODRequest.advisor_faculty_id == fac.id)
                  .group_by(models.ODRequest.workflow_state).all())
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    decisions = dict(db.query(models.ODAuditLog.action, func.count(models.ODAuditLog.id))
                     .filter(models.ODAuditLog.actor_user_id == user.id,
                             models.ODAuditLog.created_at >= month_start,
                             models.ODAuditLog.action.in_(["approve", "forward_to_hod", "reject", "request_clarification"]))
                     .group_by(models.ODAuditLog.action).all())
    advisees = db.query(models.AdvisorAssignment).filter(models.AdvisorAssignment.faculty_id == fac.id).count()
    return {
        "advisees": advisees,
        "pending": sum(counts.get(s, 0) for s in svc.FACULTY_QUEUE_STATES),
        "awaiting_student": counts.get(svc.CLARIFICATION_REQUESTED, 0),
        "with_hod": counts.get(svc.UNDER_HOD_REVIEW, 0),
        "approved_this_month": decisions.get("approve", 0),
        "forwarded_this_month": decisions.get("forward_to_hod", 0),
        "rejected_this_month": decisions.get("reject", 0),
        "clarifications_this_month": decisions.get("request_clarification", 0),
    }


@faculty_router.get("/queue")
def faculty_queue(page: int = 1, page_size: int = 10, q: Optional[str] = None, state: str = "pending",
                  db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    states = {"pending": svc.FACULTY_QUEUE_STATES,
              "awaiting_student": [svc.CLARIFICATION_REQUESTED],
              "with_hod": [svc.UNDER_HOD_REVIEW]}.get(state)
    if states is None:
        raise HTTPException(status_code=422, detail="state must be pending, awaiting_student or with_hod")
    query = _base_query(db).filter(models.ODRequest.advisor_faculty_id == fac.id,
                                   models.ODRequest.workflow_state.in_(states))
    query = svc.search_filter(query, q).order_by(models.ODRequest.submitted_at, models.ODRequest.id)
    return paginate(query, page, page_size, lambda r: request_dict(r, "faculty"))


@faculty_router.get("/history")
def faculty_history(page: int = 1, page_size: int = 10, db: Session = Depends(get_db),
                    user: models.User = Depends(require_faculty)):
    get_faculty_or_404(db, user)
    query = (db.query(models.ODAuditLog)
             .options(joinedload(models.ODAuditLog.request).joinedload(models.ODRequest.student)
                      .joinedload(models.Student.user))
             .filter(models.ODAuditLog.actor_user_id == user.id, models.ODAuditLog.actor_role == "faculty")
             .order_by(models.ODAuditLog.created_at.desc(), models.ODAuditLog.id.desc()))
    return paginate(query, page, page_size, lambda a: {
        "id": a.id, "request_id": a.request_id, "action": a.action,
        "new_state": a.new_state, "new_state_label": svc.STATE_LABELS.get(a.new_state, a.new_state),
        "comment": a.comment, "at": _iso(a.created_at),
        "event_name": svc.display_name(a.request),
        "student_name": a.request.student.user.full_name,
        "register_number": a.request.student.register_number,
        "requested_hours": a.request.requested_hours,
        "current_state_label": svc.STATE_LABELS.get(a.request.workflow_state, a.request.workflow_state),
    })


@faculty_router.get("/requests/{request_id}")
def faculty_get_request(request_id: int, db: Session = Depends(get_db),
                        user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    req = _advised_request(db, fac, request_id)
    inst = svc.get_institution(db)
    data = request_dict(req, "faculty", detail=True)
    data["student_balance"] = svc.balance(db, inst, req.student_id)
    att = svc.attendance_summary(db, inst, req.student_id)
    data["student_attendance"] = {k: att[k] for k in ("threshold_pct", "overall_pct", "effective_pct")}
    return data


@faculty_router.post("/requests/{request_id}/approve")
def faculty_approve(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                    user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    inst = svc.get_institution(db)
    req = _advised_request(db, fac, request_id)
    with unit_of_work(db):
        wf.faculty_approve(db, inst, req, fac, user, payload.version, payload.comment, payload.approved_hours)
    return request_dict(_get_request(db, request_id), "faculty", detail=True)


@faculty_router.post("/requests/{request_id}/reject")
def faculty_reject(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                   user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    req = _advised_request(db, fac, request_id)
    with unit_of_work(db):
        wf.reject(db, req, user, "faculty", payload.version, payload.comment, faculty=fac)
    return request_dict(_get_request(db, request_id), "faculty", detail=True)


@faculty_router.post("/requests/{request_id}/request-clarification")
def faculty_request_clarification(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                                  user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    req = _advised_request(db, fac, request_id)
    with unit_of_work(db):
        wf.request_clarification(db, req, fac, user, payload.version, payload.comment)
    return request_dict(_get_request(db, request_id), "faculty", detail=True)


# ---------------------------------------------------------------------------
# Admin / HOD
# ---------------------------------------------------------------------------

def _admin_scope_query(db: Session, user: models.User, department_id: Optional[int]):
    scope = admin_department_ids(db, user)
    query = _base_query(db)
    if scope is not None:
        if department_id is not None and department_id not in scope:
            raise HTTPException(status_code=403, detail="You do not head that department.")
        query = query.filter(models.Student.department_id.in_(scope))
    if department_id is not None:
        query = query.filter(models.Student.department_id == department_id)
    return query


@admin_router.get("/scope")
def admin_scope(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    scope = admin_department_ids(db, user)
    depts = db.query(models.Department).order_by(models.Department.id).all()
    visible = [d for d in depts if scope is None or d.id in scope]
    return {
        "institution_wide": scope is None,
        "departments": [{"id": d.id, "code": d.code, "name": d.name} for d in visible],
    }


@admin_router.get("/queue")
def admin_queue(page: int = 1, page_size: int = 10, department_id: Optional[int] = None, q: Optional[str] = None,
                db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    query = _admin_scope_query(db, user, department_id).filter(
        models.ODRequest.workflow_state == svc.UNDER_HOD_REVIEW)
    query = svc.search_filter(query, q).order_by(models.ODRequest.submitted_at, models.ODRequest.id)
    return paginate(query, page, page_size, lambda r: request_dict(r, "admin"))


@admin_router.get("/requests")
def admin_requests(page: int = 1, page_size: int = 10, department_id: Optional[int] = None,
                   state: Optional[str] = None, q: Optional[str] = None,
                   db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    query = _admin_scope_query(db, user, department_id)
    if state:
        if state not in svc.ALL_STATES:
            raise HTTPException(status_code=422, detail=f"Unknown state filter: {state}")
        query = query.filter(models.ODRequest.workflow_state == state)
    query = svc.search_filter(query, q).order_by(
        func.coalesce(models.ODRequest.submitted_at, models.ODRequest.request_date).desc(), models.ODRequest.id.desc())
    return paginate(query, page, page_size, lambda r: request_dict(r, "admin"))


@admin_router.get("/requests/{request_id}")
def admin_get_request(request_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    req = _scoped_request(db, user, request_id)
    inst = svc.get_institution(db)
    data = request_dict(req, "admin", detail=True)
    data["student_balance"] = svc.balance(db, inst, req.student_id)
    att = svc.attendance_summary(db, inst, req.student_id)
    data["student_attendance"] = {k: att[k] for k in ("threshold_pct", "overall_pct", "effective_pct")}
    return data


@admin_router.get("/requests/{request_id}/audit")
def admin_audit(request_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    req = _scoped_request(db, user, request_id)
    return {
        "request_id": req.id,
        "event_name": svc.display_name(req),
        "student_name": req.student.user.full_name,
        "current_state": req.workflow_state,
        "entries": [{
            "id": a.id, "at": _iso(a.created_at), "action": a.action,
            "old_state": a.old_state, "new_state": a.new_state,
            "actor_role": a.actor_role, "actor_name": a.actor.full_name if a.actor else "System",
            "actor_username": a.actor.username if a.actor else None, "comment": a.comment,
        } for a in req.audit_logs],
    }


@admin_router.post("/requests/{request_id}/approve")
def admin_approve(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                  user: models.User = Depends(require_admin)):
    inst = svc.get_institution(db)
    req = _scoped_request(db, user, request_id)
    with unit_of_work(db):
        wf.hod_approve(db, inst, req, user, payload.version, payload.comment, payload.approved_hours)
    return request_dict(_get_request(db, request_id), "admin", detail=True)


@admin_router.post("/requests/{request_id}/reject")
def admin_reject(request_id: int, payload: ActionPayload, db: Session = Depends(get_db),
                 user: models.User = Depends(require_admin)):
    req = _scoped_request(db, user, request_id)
    with unit_of_work(db):
        wf.reject(db, req, user, "admin", payload.version, payload.comment)
    return request_dict(_get_request(db, request_id), "admin", detail=True)


def od_analytics(db: Session, inst: models.Institution, scope: Optional[list]) -> dict:
    """Department-wise OD utilisation, approval rate and turnaround for the current term."""
    start, end = svc._term_bounds(inst)
    when = svc._when()
    depts = db.query(models.Department).order_by(models.Department.id).all()
    depts = [d for d in depts if scope is None or d.id in scope]
    dept_ids = [d.id for d in depts]
    students = dict(db.query(models.Student.department_id, func.count(models.Student.id))
                    .filter(models.Student.department_id.in_(dept_ids))
                    .group_by(models.Student.department_id).all())
    rows = (db.query(models.Student.department_id, models.ODRequest.workflow_state,
                     func.count(models.ODRequest.id),
                     func.coalesce(func.sum(models.ODRequest.approved_hours), 0.0))
            .join(models.Student, models.Student.id == models.ODRequest.student_id)
            .filter(models.Student.department_id.in_(dept_ids), when >= start, when < end)
            .group_by(models.Student.department_id, models.ODRequest.workflow_state).all())
    decided = (db.query(models.Student.department_id, models.ODRequest.submitted_at, models.ODRequest.decided_at)
               .join(models.Student, models.Student.id == models.ODRequest.student_id)
               .filter(models.Student.department_id.in_(dept_ids),
                       models.ODRequest.decided_at.isnot(None), models.ODRequest.submitted_at.isnot(None)).all())
    turnaround = {}
    for dept_id, submitted, done in decided:
        turnaround.setdefault(dept_id, []).append((done - submitted).total_seconds() / 3600)

    by_dept, totals = [], {s: 0 for s in svc.ALL_STATES}
    for d in depts:
        counts = {s: 0 for s in svc.ALL_STATES}
        approved_hours = 0.0
        for dept_id, state, n, hours in rows:
            if dept_id == d.id and state in counts:
                counts[state] = n
                totals[state] += n
                if state == svc.APPROVED:
                    approved_hours = float(hours or 0)
        decided_n = counts[svc.APPROVED] + counts[svc.REJECTED]
        capacity = students.get(d.id, 0) * float(inst.od_hours_per_semester)
        times = turnaround.get(d.id, [])
        by_dept.append({
            "department_id": d.id, "department": d.code, "department_name": d.name,
            "students": students.get(d.id, 0),
            "total_requests": sum(counts.values()),
            "approved": counts[svc.APPROVED], "rejected": counts[svc.REJECTED],
            "cancelled": counts[svc.CANCELLED],
            "pending": sum(counts[s] for s in svc.IN_FLIGHT_STATES),
            "pending_hod": counts[svc.UNDER_HOD_REVIEW],
            "approval_rate_pct": round(counts[svc.APPROVED] / decided_n * 100, 1) if decided_n else None,
            "approved_hours": round(approved_hours, 1),
            "utilisation_pct": round(approved_hours / capacity * 100, 2) if capacity else 0.0,
            "avg_hours_per_student": round(approved_hours / students[d.id], 2) if students.get(d.id) else 0.0,
            "avg_turnaround_hours": round(sum(times) / len(times), 1) if times else None,
            "decisions_with_turnaround": len(times),
        })
    all_times = [t for ts in turnaround.values() for t in ts]
    decided_total = totals[svc.APPROVED] + totals[svc.REJECTED]
    return {
        "term": {"start": str(inst.term_start), "end": str(inst.term_end)},
        "totals": {
            "requests": sum(totals.values()),
            "approved": totals[svc.APPROVED], "rejected": totals[svc.REJECTED],
            "pending": sum(totals[s] for s in svc.IN_FLIGHT_STATES),
            "pending_hod": totals[svc.UNDER_HOD_REVIEW],
            "approval_rate_pct": round(totals[svc.APPROVED] / decided_total * 100, 1) if decided_total else None,
            "approved_hours": round(sum(d["approved_hours"] for d in by_dept), 1),
            "avg_turnaround_hours": round(sum(all_times) / len(all_times), 1) if all_times else None,
            "decisions_with_turnaround": len(all_times),
        },
        "state_breakdown": [{"state": s, "label": svc.STATE_LABELS[s], "count": totals[s]} for s in svc.ALL_STATES],
        "by_department": by_dept,
        "note": "Turnaround is measured only for requests decided through the workflow; "
                "imported legacy requests have no recorded decision time.",
    }


@admin_router.get("/analytics")
def admin_analytics(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    return od_analytics(db, svc.get_institution(db), admin_department_ids(db, user))


class PolicyUpdate(BaseModel):
    od_hours_per_semester: float
    min_attendance_pct: float
    approval_chain: list
    hod_threshold_hours: float
    max_hours_per_request: float


@admin_router.get("/policy")
def get_policy(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    data = svc.policy_dict(svc.get_institution(db))
    data["can_edit"] = admin_department_ids(db, user) is None
    return data


@admin_router.put("/policy")
def update_policy(payload: PolicyUpdate, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    if admin_department_ids(db, user) is not None:
        raise HTTPException(status_code=403, detail="Only an institution-wide administrator can change OD policy.")
    chain = [str(p).strip().lower() for p in payload.approval_chain]
    if chain not in (["faculty"], ["faculty", "hod"]):
        raise HTTPException(status_code=422, detail="approval_chain must be ['faculty'] or ['faculty', 'hod'].")
    if not (0 < payload.od_hours_per_semester <= 500):
        raise HTTPException(status_code=422, detail="OD hours per semester must be between 1 and 500.")
    if not (0 <= payload.min_attendance_pct <= 100):
        raise HTTPException(status_code=422, detail="Minimum attendance must be between 0 and 100.")
    if payload.hod_threshold_hours < 0 or payload.max_hours_per_request <= 0:
        raise HTTPException(status_code=422, detail="Hour limits must be positive.")
    inst = svc.get_institution(db)
    inst.od_hours_per_semester = payload.od_hours_per_semester
    inst.min_attendance_pct = payload.min_attendance_pct
    inst.approval_chain = ",".join(chain)
    inst.hod_threshold_hours = payload.hod_threshold_hours
    inst.max_hours_per_request = payload.max_hours_per_request
    db.commit()
    data = svc.policy_dict(inst)
    data["can_edit"] = True
    return data


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

@shared_router.get("/documents/{document_id}")
def download_document(document_id: int, db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    doc = db.get(models.ODDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    req = doc.request
    if user.role == "student":
        allowed = req.student.user_id == user.id
    elif user.role == "faculty":
        fac = get_faculty_or_404(db, user)
        allowed = req.advisor_faculty_id == fac.id
    else:
        scope = admin_department_ids(db, user)
        allowed = scope is None or req.student.department_id in scope
    if not allowed:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data = get_storage().retrieve(doc.storage_path)
    except StorageError:
        raise HTTPException(status_code=410, detail="The stored file is no longer available.")
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in doc.filename)
    return Response(content=data, media_type=doc.content_type or "application/octet-stream",
                    headers={"Content-Disposition": f'inline; filename="{safe}"'})
