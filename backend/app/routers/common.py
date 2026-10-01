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
