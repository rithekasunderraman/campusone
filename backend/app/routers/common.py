from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date as date_type

from .. import models
from ..database import get_db
from ..auth import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["common"])


@router.get("/announcements")
def announcements(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    records = (
        db.query(models.Announcement)
        .filter((models.Announcement.audience == "all") | (models.Announcement.audience == user.role))
        .order_by(models.Announcement.posted_on.desc())
        .all()
    )
    return [
        {"id": a.id, "title": a.title, "body": a.body, "audience": a.audience,
         "posted_on": a.posted_on.isoformat()}
        for a in records
    ]


@router.get("/events")
def events(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    records = db.query(models.Event).order_by(models.Event.event_date).all()
    return [
        {"id": e.id, "title": e.title, "description": e.description,
         "date": str(e.event_date), "venue": e.venue}
        for e in records
    ]


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    audience: str = "all"


@router.post("/admin/announcements")
def create_announcement(payload: AnnouncementCreate, db: Session = Depends(get_db),
                         user: models.User = Depends(require_role("admin"))):
    a = models.Announcement(title=payload.title, body=payload.body, audience=payload.audience)
    db.add(a)
    db.commit()
    return {"message": "Announcement posted", "id": a.id}


class EventCreate(BaseModel):
    title: str
    description: str
    event_date: date_type
    venue: str


@router.post("/admin/events")
def create_event(payload: EventCreate, db: Session = Depends(get_db),
                  user: models.User = Depends(require_role("admin"))):
    e = models.Event(title=payload.title, description=payload.description,
                      event_date=payload.event_date, venue=payload.venue)
    db.add(e)
    db.commit()
    return {"message": "Event created", "id": e.id}


# ---------------- Institution profile (branding) ----------------

def _institution_dict(inst: models.Institution) -> dict:
    return {
        "name": inst.name, "short_name": inst.short_name, "code": inst.code,
        "logo_url": inst.logo_url, "primary_color": inst.primary_color, "support_email": inst.support_email,
    }


@router.get("/institution")
def institution(db: Session = Depends(get_db)):
    """Public branding for the login page and sidebar. Contains no policy or personal data."""
    inst = db.query(models.Institution).order_by(models.Institution.id).first()
    if inst is None:
        return {"name": "CampusOne", "short_name": "CampusOne", "code": None, "logo_url": None,
                "primary_color": None, "support_email": None}
    return _institution_dict(inst)


class InstitutionUpdate(BaseModel):
    name: str
    short_name: str = ""
    support_email: str = ""
    logo_url: str = ""
    primary_color: str = ""


@router.put("/admin/institution")
def update_institution(payload: InstitutionUpdate, db: Session = Depends(get_db),
                       user: models.User = Depends(require_role("admin"))):
    from fastapi import HTTPException
    from .od import admin_department_ids
    if admin_department_ids(db, user) is not None:
        raise HTTPException(status_code=403, detail="Only an institution-wide administrator can change the institution profile.")
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="The institution name is required.")
    inst = db.query(models.Institution).order_by(models.Institution.id).first()
    if inst is None:
        raise HTTPException(status_code=500, detail="Institution is not configured.")
    inst.name = payload.name.strip()[:120]
    inst.short_name = payload.short_name.strip()[:40] or None
    inst.support_email = payload.support_email.strip()[:120] or None
    inst.logo_url = payload.logo_url.strip()[:300] or None
    inst.primary_color = payload.primary_color.strip()[:20] or None
    db.commit()
    return _institution_dict(inst)
