from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import require_role
from ..utils import get_student_or_404, attendance_pct, mark_total, subject_summary, student_summary

router = APIRouter(prefix="/api/student", tags=["student"])
require_student = require_role("student")


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    att_records = db.query(models.Attendance).filter(models.Attendance.student_id == st.id).all()
    overall_total = sum(a.total_classes for a in att_records) or 1
    overall_attended = sum(a.attended_classes for a in att_records)
    marks = db.query(models.Mark).filter(models.Mark.student_id == st.id).all()
    fees = db.query(models.Fee).filter(models.Fee.student_id == st.id).order_by(models.Fee.id.desc()).first()
    subject_ids = [a.subject_id for a in att_records]
    upcoming_exams = (
        db.query(models.Exam)
        .filter(models.Exam.subject_id.in_(subject_ids))
        .order_by(models.Exam.exam_date)
        .limit(5)
        .all()
    )
    applications = db.query(models.Application).filter(models.Application.student_id == st.id).all()

    return {
        "profile": student_summary(st),
        "attendance_overall_pct": round((overall_attended / overall_total) * 100, 1),
        "subjects_count": len(att_records),
        "average_marks_pct": round(sum(mark_total(m) for m in marks) / (len(marks) * 100) * 100, 1) if marks else 0,
        "fees_status": fees.status if fees else "N/A",
        "upcoming_exams": [
            {"subject": e.subject.name, "type": e.exam_type, "date": str(e.exam_date), "venue": e.venue}
            for e in upcoming_exams
        ],
        "placement_applications": len(applications),
        "placement_offers": len([a for a in applications if a.status == "Offered"]),
    }


@router.get("/attendance")
def attendance(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    records = db.query(models.Attendance).filter(models.Attendance.student_id == st.id).all()
    result = []
    for a in records:
        pct = attendance_pct(a)
        result.append({
            "subject_code": a.subject.code,
            "subject_name": a.subject.name,
            "total_classes": a.total_classes,
            "attended_classes": a.attended_classes,
            "percentage": pct,
            "status": "Safe" if pct >= 75 else ("At Risk" if pct >= 65 else "Shortage"),
        })
    return result


@router.get("/marks")
def marks(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    records = db.query(models.Mark).filter(models.Mark.student_id == st.id).all()
    return [
        {
            "subject_code": m.subject.code,
            "subject_name": m.subject.name,
            "internal_1": m.internal_1,
            "internal_2": m.internal_2,
            "assignment": m.assignment,
            "external": m.external,
            "total": mark_total(m),
            "grade": m.grade,
        }
        for m in records
    ]


@router.get("/timetable")
def timetable(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    subject_ids = [a.subject_id for a in db.query(models.Attendance).filter(models.Attendance.student_id == st.id)]
    slots = db.query(models.TimetableSlot).filter(models.TimetableSlot.subject_id.in_(subject_ids)).all()
    return [
        {
            "day": s.day_of_week,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "room": s.room,
            "subject_code": s.subject.code,
            "subject_name": s.subject.name,
            "faculty_name": s.subject.faculty.user.full_name if s.subject.faculty else None,
        }
        for s in slots
    ]


@router.get("/exams")
def exams(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    subject_ids = [a.subject_id for a in db.query(models.Attendance).filter(models.Attendance.student_id == st.id)]
    records = (
        db.query(models.Exam)
        .filter(models.Exam.subject_id.in_(subject_ids))
        .order_by(models.Exam.exam_date)
        .all()
    )
    return [
        {
            "subject_code": e.subject.code,
            "subject_name": e.subject.name,
            "exam_type": e.exam_type,
            "date": str(e.exam_date),
            "start_time": e.start_time,
            "end_time": e.end_time,
            "venue": e.venue,
        }
        for e in records
    ]


@router.get("/fees")
def fees(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    records = db.query(models.Fee).filter(models.Fee.student_id == st.id).all()
    return [
        {
            "semester": f.semester,
            "total_amount": f.total_amount,
            "paid_amount": f.paid_amount,
            "balance": f.total_amount - f.paid_amount,
            "due_date": str(f.due_date),
            "status": f.status,
        }
        for f in records
    ]


@router.get("/library")
def library(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    records = db.query(models.LibraryRecord).filter(models.LibraryRecord.student_id == st.id).all()
    return [
        {
            "book_title": r.book_title,
            "issue_date": str(r.issue_date),
            "due_date": str(r.due_date),
            "return_date": str(r.return_date) if r.return_date else None,
            "status": r.status,
        }
        for r in records
    ]


@router.get("/subjects")
def subjects(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    course = st.department.courses[0] if st.department.courses else None
    subs = db.query(models.Subject).filter(models.Subject.course_id == course.id).all() if course else []
    return [subject_summary(s) for s in subs]
