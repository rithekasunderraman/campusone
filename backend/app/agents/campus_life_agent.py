"""Campus-life intent agent.

This layer is deliberately database-grounded: it detects student-life questions and
returns facts only from records belonging to the authenticated student.
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from .. import models


def answer(message: str, db: Session, student: models.Student):
    m = message.lower()

    if any(k in m for k in ["what clubs", "which clubs", "clubs am i", "my clubs", "club membership"]):
        rows = db.query(models.ClubMembership).filter_by(student_id=student.id).all()
        return "You are not currently enrolled in any clubs." if not rows else (
            "You are part of these clubs:\n" + "\n".join(
                f"- {r.club.name} ({r.club.category}) — {r.role}" for r in rows
            )
        )

    # OD questions are answered by od_agent (policy-aware) before this agent is consulted.

    if any(k in m for k in ["club upcoming", "upcoming club", "my club event", "club events", "upcoming events",
                            "events this week", "events are happening", "events happening", "what events"]):
        club_ids = [r.club_id for r in db.query(models.ClubMembership).filter_by(student_id=student.id).all()]
        if not club_ids:
            return "You are not a member of any clubs yet."
        query = db.query(models.ClubEvent).filter(
            models.ClubEvent.club_id.in_(club_ids),
            models.ClubEvent.event_date >= date.today()
        )
        this_week = "this week" in m
        if this_week:
            query = query.filter(models.ClubEvent.event_date <= date.today() + timedelta(days=7))
        events = query.order_by(models.ClubEvent.event_date, models.ClubEvent.start_time).limit(12).all()
        if not events:
            return ("None of your clubs has an event in the next 7 days." if this_week
                    else "There are no upcoming events for your clubs right now.")
        heading = "Your clubs' events in the next 7 days:\n" if this_week else "Here are your clubs' upcoming events:\n"
        return heading + "\n".join(
            f"- {e.club.name}: {e.title} on {e.event_date} at {e.start_time}, {e.venue}" for e in events
        )

    if any(k in m for k in ["events have i attended", "events attended", "attended events", "event attendance"]):
        rows = db.query(models.EventAttendance).filter_by(student_id=student.id).order_by(
            models.EventAttendance.attended_on.desc()
        ).all()
        if not rows:
            return "You haven't attended any club events yet."
        return f"You have attended {len(rows)} club event(s):\n" + "\n".join(
            f"- {r.event.club.name}: {r.event.title} ({r.event.event_date})" for r in rows[:20]
        )

    if any(k in m for k in ["volunteered", "volunteer count", "volunteering", "events i volunteered"]):
        rows = db.query(models.EventVolunteer).filter(
            models.EventVolunteer.student_id == student.id,
            models.EventVolunteer.status != "Cancelled"
        ).all()
        completed = sum(1 for r in rows if r.status == "Completed")
        hours = round(sum(r.hours or 0 for r in rows), 1)
        return f"You have volunteered for {len(rows)} event(s), including {completed} completed. Total volunteering time: {hours} hours."

    if any(k in m for k in ["hosteller", "day scholar", "accommodation", "hostel", "hostel details"]):
        if student.accommodation_type == "Hosteller" and student.hostel:
            h = student.hostel.hostel
            return f"You are a hosteller. You are staying at {h.name}, {h.block}, room {student.hostel.room_number}, bed {student.hostel.bed_number} ({h.room_type}). Academic year: {student.hostel.academic_year}."
        return "You are a day scholar, so no hostel accommodation is assigned to you."

    return None
