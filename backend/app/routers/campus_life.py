"""Student-life APIs: accommodation, clubs, events, volunteering and OD."""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..auth import require_role
from ..database import get_db
from ..utils import get_student_or_404

router = APIRouter(prefix="/api/student/campus-life", tags=["student-life"])
require_student = require_role("student")


def _student(db, user):
    return get_student_or_404(db, user)


@router.get("/profile")
def campus_profile(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    result = {
        "accommodation_type": st.accommodation_type,
        "hostel": None,
    }
    if st.hostel:
        result["hostel"] = {
            "name": st.hostel.hostel.name,
            "block": st.hostel.hostel.block,
            "room_type": st.hostel.hostel.room_type,
            "room_number": st.hostel.room_number,
            "bed_number": st.hostel.bed_number,
            "academic_year": st.hostel.academic_year,
        }
    return result


@router.get("/clubs")
def my_clubs(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    memberships = (
        db.query(models.ClubMembership)
        .options(joinedload(models.ClubMembership.club))
        .filter(models.ClubMembership.student_id == st.id)
        .order_by(models.ClubMembership.club_id)
        .all()
    )
    return [{
        "club_id": m.club.id,
        "club_name": m.club.name,
        "category": m.club.category,
        "role": m.role,
        "joined_on": str(m.joined_on),
        "meeting": f"{m.club.meeting_day} at {m.club.meeting_time}",
        "description": m.club.description,
    } for m in memberships]


@router.get("/events/upcoming")
def upcoming_club_events(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    club_ids = [m.club_id for m in db.query(models.ClubMembership).filter_by(student_id=st.id).all()]
    if not club_ids:
        return []
    events = (
        db.query(models.ClubEvent)
        .options(joinedload(models.ClubEvent.club))
        .filter(models.ClubEvent.club_id.in_(club_ids), models.ClubEvent.event_date >= date.today())
        .order_by(models.ClubEvent.event_date, models.ClubEvent.start_time)
        .all()
    )
    return [{
        "event_id": e.id,
        "club_id": e.club_id,
        "club_name": e.club.name,
        "title": e.title,
        "description": e.description,
        "date": str(e.event_date),
        "start_time": e.start_time,
        "end_time": e.end_time,
        "venue": e.venue,
        "registration_required": e.registration_required,
    } for e in events]


@router.get("/events/attended")
def attended_events(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    rows = (
        db.query(models.EventAttendance)
        .options(joinedload(models.EventAttendance.event).joinedload(models.ClubEvent.club))
        .filter(models.EventAttendance.student_id == st.id)
        .order_by(models.EventAttendance.attended_on.desc())
        .all()
    )
    return [{
        "event_id": r.event.id,
        "club_name": r.event.club.name,
        "title": r.event.title,
        "date": str(r.event.event_date),
        "venue": r.event.venue,
    } for r in rows]


@router.get("/events/volunteered")
def volunteered_events(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    rows = (
        db.query(models.EventVolunteer)
        .options(joinedload(models.EventVolunteer.event).joinedload(models.ClubEvent.club))
        .filter(models.EventVolunteer.student_id == st.id)
        .order_by(models.EventVolunteer.event_id.desc())
        .all()
    )
    return [{
        "event_id": r.event.id,
        "club_name": r.event.club.name,
        "title": r.event.title,
        "date": str(r.event.event_date),
        "responsibility": r.responsibility,
        "hours": r.hours,
        "status": r.status,
    } for r in rows]


@router.get("/od")
def od_summary(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    rows = (
        db.query(models.ODRequest)
        .options(joinedload(models.ODRequest.event))
        .filter(models.ODRequest.student_id == st.id)
        .order_by(models.ODRequest.request_date.desc())
        .all()
    )
    entitlement = 40.0
    used = round(sum(r.approved_hours or 0 for r in rows if r.status == "Approved"), 1)
    return {
        "annual_entitlement_hours": entitlement,
        "used_hours": used,
        "remaining_hours": round(max(0, entitlement - used), 1),
        "request_count": len(rows),
        "requests": [{
            "request_id": r.id,
            "event_id": r.event_id,
            "event_title": r.event.title if r.event else None,
            "requested_hours": r.requested_hours,
            "approved_hours": r.approved_hours,
            "status": r.status,
            "request_date": r.request_date.isoformat() if r.request_date else None,
            "reason": r.reason,
        } for r in rows],
    }


@router.get("/overview")
def campus_life_overview(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = _student(db, user)
    club_count = db.query(models.ClubMembership).filter_by(student_id=st.id).count()
    attended_count = db.query(models.EventAttendance).filter_by(student_id=st.id).count()
    volunteer_count = db.query(models.EventVolunteer).filter(
        models.EventVolunteer.student_id == st.id,
        models.EventVolunteer.status != "Cancelled",
    ).count()
    used = sum(
        r.approved_hours or 0
        for r in db.query(models.ODRequest).filter(
            models.ODRequest.student_id == st.id,
            models.ODRequest.status == "Approved"
        ).all()
    )
    return {
        "accommodation_type": st.accommodation_type,
        "club_count": club_count,
        "events_attended": attended_count,
        "events_volunteered": volunteer_count,
        "od_used_hours": round(used, 1),
        "od_remaining_hours": round(max(0, 40 - used), 1),
    }
