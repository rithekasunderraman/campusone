from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from .. import models
from ..database import get_db
from ..auth import require_role
from ..utils import get_faculty_or_404, attendance_pct, mark_total, student_summary, subject_summary

router = APIRouter(prefix="/api/faculty", tags=["faculty"])
require_faculty = require_role("faculty")


def _owned_subject_or_404(db: Session, fac: models.Faculty, subject_id: int) -> models.Subject:
    subj = db.query(models.Subject).filter(models.Subject.id == subject_id,
                                             models.Subject.faculty_id == fac.id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found or not assigned to you")
    return subj


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subjects = db.query(models.Subject).filter(models.Subject.faculty_id == fac.id).all()
    subject_ids = [s.id for s in subjects]
    student_count = (
        db.query(models.Attendance.student_id)
        .filter(models.Attendance.subject_id.in_(subject_ids))
        .distinct()
        .count()
    )
    upcoming_exams = (
        db.query(models.Exam)
        .filter(models.Exam.subject_id.in_(subject_ids))
        .order_by(models.Exam.exam_date)
        .limit(5)
        .all()
    )
    marks = db.query(models.Mark).filter(models.Mark.subject_id.in_(subject_ids)).all()
    avg_pct = round(sum(mark_total(m) for m in marks) / (len(marks) * 100) * 100, 1) if marks else 0

    return {
        "profile": {
            "full_name": user.full_name,
            "employee_code": fac.employee_code,
            "designation": fac.designation,
            "department": fac.department.name,
            "office": fac.office,
        },
        "subjects_count": len(subjects),
        "students_taught": student_count,
        "average_class_performance_pct": avg_pct,
        "upcoming_exams": [
            {"subject": e.subject.name, "type": e.exam_type, "date": str(e.exam_date), "venue": e.venue}
            for e in upcoming_exams
        ],
    }


@router.get("/subjects")
def subjects(db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subs = db.query(models.Subject).filter(models.Subject.faculty_id == fac.id).all()
    return [subject_summary(s) for s in subs]


@router.get("/students")
def students(subject_id: Optional[int] = None, db: Session = Depends(get_db),
             user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subject_ids = [subject_id] if subject_id else [s.id for s in
                    db.query(models.Subject).filter(models.Subject.faculty_id == fac.id)]
    if subject_id:
        _owned_subject_or_404(db, fac, subject_id)
    student_ids = (
        db.query(models.Attendance.student_id)
        .filter(models.Attendance.subject_id.in_(subject_ids))
        .distinct()
        .all()
    )
    sts = db.query(models.Student).filter(models.Student.id.in_([s[0] for s in student_ids])).all()
    return [student_summary(s) for s in sts]


@router.get("/attendance")
def get_attendance(subject_id: int, db: Session = Depends(get_db),
                    user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subj = _owned_subject_or_404(db, fac, subject_id)
    records = db.query(models.Attendance).filter(models.Attendance.subject_id == subj.id).all()
    return [
        {
            "attendance_id": a.id,
            "student_id": a.student_id,
            "register_number": a.student.register_number,
            "full_name": a.student.user.full_name,
            "total_classes": a.total_classes,
            "attended_classes": a.attended_classes,
            "percentage": attendance_pct(a),
        }
        for a in records
    ]


class AttendanceUpdate(BaseModel):
    attendance_id: int
    total_classes: int
    attended_classes: int


@router.post("/attendance")
def update_attendance(payload: AttendanceUpdate, db: Session = Depends(get_db),
                       user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    record = db.query(models.Attendance).filter(models.Attendance.id == payload.attendance_id).first()
    if not record or record.subject.faculty_id != fac.id:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    record.total_classes = payload.total_classes
    record.attended_classes = payload.attended_classes
    db.commit()
    return {"message": "Attendance updated", "percentage": attendance_pct(record)}


@router.get("/marks")
def get_marks(subject_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subj = _owned_subject_or_404(db, fac, subject_id)
    records = db.query(models.Mark).filter(models.Mark.subject_id == subj.id).all()
    return [
        {
            "mark_id": m.id,
            "student_id": m.student_id,
            "register_number": m.student.register_number,
            "full_name": m.student.user.full_name,
            "internal_1": m.internal_1,
            "internal_2": m.internal_2,
            "assignment": m.assignment,
            "external": m.external,
            "total": mark_total(m),
            "grade": m.grade,
        }
        for m in records
    ]


class MarksUpdate(BaseModel):
    mark_id: int
    internal_1: float
    internal_2: float
    assignment: float
    external: float


def _grade_from_total(total_100: float) -> str:
    if total_100 >= 90: return "S"
    if total_100 >= 80: return "A"
    if total_100 >= 70: return "B"
    if total_100 >= 60: return "C"
    if total_100 >= 50: return "D"
    if total_100 >= 40: return "E"
    return "F"


@router.post("/marks")
def update_marks(payload: MarksUpdate, db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    record = db.query(models.Mark).filter(models.Mark.id == payload.mark_id).first()
    if not record or record.subject.faculty_id != fac.id:
        raise HTTPException(status_code=404, detail="Marks record not found")
    record.internal_1 = payload.internal_1
    record.internal_2 = payload.internal_2
    record.assignment = payload.assignment
    record.external = payload.external
    total = payload.internal_1 + payload.internal_2 + payload.assignment + payload.external
    record.grade = _grade_from_total(total)
    db.commit()
    return {"message": "Marks updated", "total": round(total, 1), "grade": record.grade}


@router.get("/timetable")
def timetable(db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subject_ids = [s.id for s in db.query(models.Subject).filter(models.Subject.faculty_id == fac.id)]
    slots = db.query(models.TimetableSlot).filter(models.TimetableSlot.subject_id.in_(subject_ids)).all()
    return [
        {
            "day": s.day_of_week, "start_time": s.start_time, "end_time": s.end_time,
            "room": s.room, "subject_code": s.subject.code, "subject_name": s.subject.name,
        }
        for s in slots
    ]


@router.get("/exams")
def exams(db: Session = Depends(get_db), user: models.User = Depends(require_faculty)):
    fac = get_faculty_or_404(db, user)
    subject_ids = [s.id for s in db.query(models.Subject).filter(models.Subject.faculty_id == fac.id)]
    records = db.query(models.Exam).filter(models.Exam.subject_id.in_(subject_ids)).order_by(models.Exam.exam_date).all()
    return [
        {
            "subject_code": e.subject.code, "subject_name": e.subject.name, "exam_type": e.exam_type,
            "date": str(e.exam_date), "start_time": e.start_time, "end_time": e.end_time, "venue": e.venue,
        }
        for e in records
    ]
