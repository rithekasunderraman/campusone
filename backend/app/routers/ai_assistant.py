"""
AI Campus Assistant.

Design:
1. We ALWAYS resolve the answer from the database first (rule/intent based),
   scoped to the logged-in user's own identity and role.
2. If an LLM API key is configured (ANTHROPIC_API_KEY env var) we ask the LLM
   to rephrase the database facts into a natural sentence. If the key is
   missing, the call fails, or the response is empty, we fall back to a
   clean templated sentence built directly from the data - so the assistant
   NEVER just says "no matching information found".
"""
import os
import re
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..utils import get_student_or_404, get_faculty_or_404, attendance_pct, mark_total
from ..agents import campus_life_agent

router = APIRouter(prefix="/api/ai", tags=["ai-assistant"])


def _try_llm_rephrase(user_message: str, facts: str) -> Optional[str]:
    """Best-effort LLM polish of the database facts. Returns None on any failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic  # optional dependency, only used if installed + key present
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "You are CampusOne AI, a university portal assistant. "
                    "Rewrite the following facts into a short, friendly, direct answer "
                    "to the student's/faculty's question. Do not invent any information "
                    "beyond what is given. Do not add disclaimers.\n\n"
                    f"Question: {user_message}\n\nFacts:\n{facts}"
                ),
            }],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return text or None
    except Exception:
        return None


def _answer(user_message: str, facts: str) -> str:
    return _try_llm_rephrase(user_message, facts) or facts


# ---------------- Student intents ----------------

def _student_answer(msg: str, db: Session, st: models.Student) -> str:
    m = msg.lower()

    campus_answer = campus_life_agent.answer(msg, db, st)
    if campus_answer:
        return campus_answer

    if any(k in m for k in ["subject-wise attendance", "attendance by subject", "attendance breakdown"]):
        recs = db.query(models.Attendance).filter(models.Attendance.student_id == st.id).all()
        lines = [f"- {a.subject.name} ({a.subject.code}): {attendance_pct(a)}% "
                 f"({a.attended_classes}/{a.total_classes} classes)" for a in recs]
        return "Here is your subject-wise attendance:\n" + "\n".join(lines)

    if "attendance" in m:
        recs = db.query(models.Attendance).filter(models.Attendance.student_id == st.id).all()
        total = sum(a.total_classes for a in recs) or 1
        attended = sum(a.attended_classes for a in recs)
        pct = round((attended / total) * 100, 1)
        low = [a.subject.name for a in recs if attendance_pct(a) < 75]
        extra = f" You are below 75% in: {', '.join(low)}." if low else " You are meeting the 75% requirement in all subjects."
        return f"Your overall attendance is {pct}% ({attended}/{total} classes attended).{extra}"

    if "cgpa" in m:
        return f"Your current CGPA is {st.cgpa}."

    if any(k in m for k in ["sgpa", "gpa"]):
        marks = db.query(models.Mark).filter(models.Mark.student_id == st.id).all()
        if not marks:
            return "No marks have been recorded for this semester yet."
        credits_total = sum(m.subject.credits for m in marks)
        weighted = sum(m.sgpa_contribution * m.subject.credits for m in marks)
        sgpa = round(weighted / credits_total, 2) if credits_total else 0
        return f"Your estimated SGPA for this semester is {sgpa} (based on {len(marks)} subjects)."

    if "marks" in m or "grade" in m:
        marks = db.query(models.Mark).filter(models.Mark.student_id == st.id).all()
        lines = [f"- {mk.subject.name}: {mark_total(mk)}/100 (Grade {mk.grade})" for mk in marks]
        return "Here are your latest marks:\n" + "\n".join(lines)

    if "timetable" in m or "schedule" in m or "class" in m:
        subject_ids = [a.subject_id for a in db.query(models.Attendance).filter(models.Attendance.student_id == st.id)]
        slots = db.query(models.TimetableSlot).filter(models.TimetableSlot.subject_id.in_(subject_ids)).all()
        by_day = {}
        for s in slots:
            by_day.setdefault(s.day_of_week, []).append(f"{s.start_time}-{s.end_time} {s.subject.code} ({s.room})")
        if not by_day:
            return "No timetable has been published for your subjects yet."
        lines = [f"{day}: " + "; ".join(sorted(entries)) for day, entries in by_day.items()]
        return "Here is your weekly class timetable:\n" + "\n".join(lines)

    if "exam" in m:
        subject_ids = [a.subject_id for a in db.query(models.Attendance).filter(models.Attendance.student_id == st.id)]
        exams = (db.query(models.Exam).filter(models.Exam.subject_id.in_(subject_ids))
                 .order_by(models.Exam.exam_date).limit(3).all())
        if not exams:
            return "No upcoming exams are scheduled for you right now."
        lines = [f"- {e.subject.name} ({e.exam_type}) on {e.exam_date} at {e.venue}" for e in exams]
        return "Your next exams are:\n" + "\n".join(lines)

    if "faculty" in m or "teacher" in m or "professor" in m:
        subject_ids = [a.subject_id for a in db.query(models.Attendance).filter(models.Attendance.student_id == st.id)]
        subs = db.query(models.Subject).filter(models.Subject.id.in_(subject_ids)).all()
        lines = [f"- {s.name}: {s.faculty.user.full_name if s.faculty else 'Not assigned'}" for s in subs]
        return "Your subject faculty:\n" + "\n".join(lines)

    if "fee" in m:
        fee = db.query(models.Fee).filter(models.Fee.student_id == st.id).order_by(models.Fee.id.desc()).first()
        if not fee:
            return "No fee records are available for your account."
        balance = fee.total_amount - fee.paid_amount
        return (f"Your fee status for semester {fee.semester} is '{fee.status}'. "
                f"Total: ₹{fee.total_amount:,.0f}, Paid: ₹{fee.paid_amount:,.0f}, Balance: ₹{balance:,.0f}, "
                f"Due date: {fee.due_date}.")

    if "librar" in m or "book" in m:
        recs = db.query(models.LibraryRecord).filter(models.LibraryRecord.student_id == st.id).all()
        if not recs:
            return "You have no library records at the moment."
        lines = [f"- {r.book_title}: {r.status} (due {r.due_date})" for r in recs]
        return "Your library records:\n" + "\n".join(lines)

    if any(k in m for k in ["placement", "company", "drive", "eligible", "offer", "job"]):
        dept_code = st.department.code
        drives = db.query(models.PlacementDrive).filter(models.PlacementDrive.status == "Open").all()
        eligible = [d for d in drives if dept_code in d.company.eligible_departments.split(",")
                    and st.cgpa >= d.company.min_cgpa]
        if not eligible:
            return "There are no open placement drives you're currently eligible for. Check back soon!"
        lines = [f"- {d.company.name} ({d.company.role}), CTC {d.company.ctc_lpa} LPA, "
                 f"apply by {d.application_deadline}" for d in eligible]
        return "You are eligible for these open placement drives:\n" + "\n".join(lines)

    if "profile" in m or "register" in m or "department" in m:
        return (f"You are {st.user.full_name}, register number {st.register_number}, "
                f"{st.department.name}, Year {st.year}, Semester {st.semester}, CGPA {st.cgpa}.")

    return ("I can help with your attendance, marks, CGPA/SGPA, timetable, exams, faculty details, "
            "fees, library records, and placement eligibility. Try asking, for example, "
            "'What is my attendance?' or 'Which companies am I eligible for?'")


# ---------------- Faculty intents ----------------

def _faculty_answer(msg: str, db: Session, fac: models.Faculty) -> str:
    m = msg.lower()
    subjects = db.query(models.Subject).filter(models.Subject.faculty_id == fac.id).all()
    subject_ids = [s.id for s in subjects]

    if "subject" in m or "course" in m or "teach" in m:
        lines = [f"- {s.code}: {s.name} (Semester {s.semester}, {s.credits} credits)" for s in subjects]
        return "You are teaching:\n" + "\n".join(lines)

    if "student" in m and "count" in m or "how many student" in m:
        count = (db.query(models.Attendance.student_id)
                 .filter(models.Attendance.subject_id.in_(subject_ids)).distinct().count())
        return f"You currently teach {count} unique students across {len(subjects)} subjects."

    if "attendance" in m:
        lines = []
        for s in subjects:
            recs = s.attendance_records
            total = sum(a.total_classes for a in recs) or 1
            attended = sum(a.attended_classes for a in recs)
            lines.append(f"- {s.name}: class average {round((attended/total)*100,1)}%")
        return "Class-wise average attendance:\n" + "\n".join(lines)

    if "marks" in m or "performance" in m or "grade" in m:
        lines = []
        for s in subjects:
            recs = s.marks
            avg = round(sum(mark_total(mk) for mk in recs) / (len(recs) * 100) * 100, 1) if recs else 0
            lines.append(f"- {s.name}: class average {avg}%")
        return "Class-wise academic performance:\n" + "\n".join(lines)

    if "exam" in m:
        exams = (db.query(models.Exam).filter(models.Exam.subject_id.in_(subject_ids))
                 .order_by(models.Exam.exam_date).limit(5).all())
        lines = [f"- {e.subject.name} ({e.exam_type}) on {e.exam_date}" for e in exams]
        return "Upcoming exams for your subjects:\n" + "\n".join(lines) if lines else "No upcoming exams found."

    if "timetable" in m or "schedule" in m:
        slots = db.query(models.TimetableSlot).filter(models.TimetableSlot.subject_id.in_(subject_ids)).all()
        lines = [f"- {s.day_of_week} {s.start_time}-{s.end_time}: {s.subject.code} ({s.room})" for s in slots]
        return "Your weekly teaching schedule:\n" + "\n".join(lines) if lines else "No timetable published yet."

    return ("I can help with your assigned subjects, student counts, class-wise attendance and marks, "
            "exam schedules, and your timetable. Try asking, for example, "
            "'Show attendance for my classes' or 'What subjects do I teach?'")


# ---------------- Admin intents ----------------

def _match_department(msg: str, db: Session):
    """Find a department the message refers to by code or name (e.g. 'CSE', 'mechanical')."""
    m = msg.lower()
    for d in db.query(models.Department).all():
        if d.code.lower() in m.split() or d.code.lower() in m or d.name.lower() in m:
            return d
    return None


def _admin_answer(msg: str, db: Session) -> str:
    m = msg.lower()

    if "placed" in m and "student" in m:
        offered_ids = {a.student_id for a in db.query(models.Application).filter(models.Application.status == "Offered").all()}
        return f"{len(offered_ids)} students have been placed so far this year."

    if "student" in m and ("count" in m or "how many" in m):
        dept = _match_department(msg, db)
        if dept:
            count = db.query(models.Student).filter(models.Student.department_id == dept.id).count()
            return f"There are {count} students in {dept.name} ({dept.code})."
        return f"There are {db.query(models.Student).count()} students enrolled across all departments."

    if "faculty" in m and ("count" in m or "how many" in m):
        dept = _match_department(msg, db)
        if dept:
            count = db.query(models.Faculty).filter(models.Faculty.department_id == dept.id).count()
            return f"There are {count} faculty members in {dept.name} ({dept.code})."
        return f"There are {db.query(models.Faculty).count()} faculty members across all departments."

    if "upcoming exam" in m or ("exam" in m and ("show" in m or "upcoming" in m or "list" in m)):
        today = date.today()
        exams = (db.query(models.Exam).filter(models.Exam.exam_date >= today)
                 .order_by(models.Exam.exam_date).limit(10).all())
        if not exams:
            return "There are no upcoming examinations scheduled."
        lines = [f"- {e.subject.name} ({e.exam_type}) on {e.exam_date}" for e in exams]
        return "Upcoming examinations:\n" + "\n".join(lines)

    if "compan" in m and ("drive" in m or "conduct" in m or "placement" in m):
        drives = db.query(models.PlacementDrive).filter(models.PlacementDrive.status == "Open").all()
        if not drives:
            return "No companies currently have open placement drives."
        lines = [f"- {d.company.name} ({d.company.role}) - drive on {d.drive_date}, {d.company.ctc_lpa} LPA" for d in drives]
        return "Companies currently conducting drives:\n" + "\n".join(lines)

    if "placement" in m or "offer" in m or "package" in m:
        offered = db.query(models.Application).filter(models.Application.status == "Offered").all()
        if not offered:
            return "No placement offers have been recorded yet."
        packages = [a.drive.company.ctc_lpa for a in offered]
        return (f"{len(offered)} offers have been made so far. "
                f"Average package: {round(sum(packages)/len(packages),2)} LPA, "
                f"Highest package: {max(packages)} LPA.")

    if "department-wise attendance" in m or ("attendance" in m and "department" in m):
        lines = []
        for d in db.query(models.Department).all():
            student_ids = [s.id for s in d.students]
            recs = db.query(models.Attendance).filter(models.Attendance.student_id.in_(student_ids)).all()
            total = sum(a.total_classes for a in recs) or 1
            attended = sum(a.attended_classes for a in recs)
            lines.append(f"- {d.code}: {round((attended/total)*100,1)}%")
        return "Department-wise attendance:\n" + "\n".join(lines)

    if "attendance" in m:
        recs = db.query(models.Attendance).all()
        total = sum(a.total_classes for a in recs) or 1
        attended = sum(a.attended_classes for a in recs)
        return f"Institution-wide average attendance is {round((attended/total)*100,1)}%."

    if "department" in m:
        depts = db.query(models.Department).all()
        lines = [f"- {d.name} ({d.code}): {len(d.students)} students, {len(d.faculty)} faculty" for d in depts]
        return "Department overview:\n" + "\n".join(lines)

    return ("I can help with institution-wide statistics: student/faculty counts (overall or by department), "
            "department-wise attendance, upcoming exams, placement statistics, and which companies are "
            "conducting drives. Try asking, for example, 'How many students are in CSE?' or "
            "'Show department-wise attendance'.")


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db),
         user: models.User = Depends(get_current_user)):
    msg = payload.message.strip()
    if not msg:
        return schemas.ChatResponse(response="Please type a question - for example, 'What is my attendance?'")

    if user.role == "student":
        st = get_student_or_404(db, user)
        facts = _student_answer(msg, db, st)
    elif user.role == "faculty":
        fac = get_faculty_or_404(db, user)
        facts = _faculty_answer(msg, db, fac)
    else:
        facts = _admin_answer(msg, db)

    reply = _answer(msg, facts)

    db.add(models.ChatHistory(user_id=user.id, message=msg, response=reply))
    db.commit()

    return schemas.ChatResponse(response=reply)


@router.get("/history")
def history(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    records = (db.query(models.ChatHistory).filter(models.ChatHistory.user_id == user.id)
               .order_by(models.ChatHistory.created_at.desc()).limit(30).all())
    return [
        {"message": h.message, "response": h.response, "created_at": h.created_at.isoformat()}
        for h in reversed(records)
    ]
