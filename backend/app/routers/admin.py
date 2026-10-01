from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import models
from ..database import get_db
from ..auth import require_role
from ..utils import attendance_pct, mark_total, student_summary, subject_summary, paginate

router = APIRouter(prefix="/api/admin", tags=["admin"])
require_admin = require_role("admin")


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    total_students = db.query(models.Student).count()
    total_faculty = db.query(models.Faculty).count()
    total_departments = db.query(models.Department).count()

    # Aggregate in SQL rather than loading every row into Python - at 5,000+
    # students this is the difference between a sub-second and multi-second dashboard.
    total_classes, total_attended = db.query(
        func.coalesce(func.sum(models.Attendance.total_classes), 0),
        func.coalesce(func.sum(models.Attendance.attended_classes), 0),
    ).one()
    overall_total = total_classes or 1
    overall_attended = total_attended

    marks_count = db.query(func.count(models.Mark.id)).scalar() or 0
    marks_sum = db.query(
        func.coalesce(func.sum(
            models.Mark.internal_1 + models.Mark.internal_2 + models.Mark.assignment + models.Mark.external
        ), 0)
    ).scalar() or 0
    avg_marks_pct = round((marks_sum / (marks_count * 100)) * 100, 1) if marks_count else 0

    upcoming_exams = db.query(models.Exam).order_by(models.Exam.exam_date).limit(6).all()

    offers = db.query(models.Application).filter(models.Application.status == "Offered").count()
    drives_open = db.query(models.PlacementDrive).filter(models.PlacementDrive.status == "Open").count()

    # One grouped query per metric instead of one query per department per student.
    students_by_dept = dict(
        db.query(models.Student.department_id, func.count(models.Student.id))
        .group_by(models.Student.department_id).all()
    )
    cgpa_by_dept = dict(
        db.query(models.Student.department_id, func.avg(models.Student.cgpa))
        .group_by(models.Student.department_id).all()
    )
    attendance_by_dept = (
        db.query(
            models.Student.department_id,
            func.coalesce(func.sum(models.Attendance.total_classes), 0),
            func.coalesce(func.sum(models.Attendance.attended_classes), 0),
        )
        .join(models.Attendance, models.Attendance.student_id == models.Student.id)
        .group_by(models.Student.department_id)
        .all()
    )
    attendance_lookup = {row[0]: (row[1], row[2]) for row in attendance_by_dept}

    dept_stats = []
    for d in db.query(models.Department).all():
        d_total, d_attended = attendance_lookup.get(d.id, (0, 0))
        dept_stats.append({
            "department": d.name,
            "code": d.code,
            "students": students_by_dept.get(d.id, 0),
            "avg_attendance_pct": round((d_attended / d_total) * 100, 1) if d_total else 0,
            "avg_cgpa": round(cgpa_by_dept.get(d.id) or 0, 2),
        })

    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_departments": total_departments,
        "overall_attendance_pct": round((overall_attended / overall_total) * 100, 1),
        "average_marks_pct": avg_marks_pct,
        "upcoming_exams": [
            {"subject": e.subject.name, "type": e.exam_type, "date": str(e.exam_date)}
            for e in upcoming_exams
        ],
        "placement_offers": offers,
        "open_drives": drives_open,
        "department_stats": dept_stats,
    }


@router.get("/students")
def students(page: Optional[int] = None, page_size: int = 25, q: Optional[str] = None,
             department_id: Optional[int] = None,
             db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    """Student directory. With `page` the result is paginated and searched on the
    server; without it the full list is returned (original behaviour)."""
    query = (
        db.query(models.Student)
        .join(models.User, models.User.id == models.Student.user_id)
        .join(models.Department, models.Department.id == models.Student.department_id)
        .options(joinedload(models.Student.user), joinedload(models.Student.department))
    )
    if department_id is not None:
        query = query.filter(models.Student.department_id == department_id)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(models.User.full_name).like(like),
                                 func.lower(models.Student.register_number).like(like),
                                 func.lower(models.Department.code).like(like),
                                 func.lower(models.User.email).like(like)))
    query = query.order_by(models.Student.id)
    if page is None:
        return [student_summary(s) for s in query.all()]
    return paginate(query, page, page_size, student_summary)


def _faculty_row(f: models.Faculty) -> dict:
    return {
        "id": f.id,
        "employee_code": f.employee_code,
        "full_name": f.user.full_name,
        "designation": f.designation,
        "department": f.department.name,
        "office": f.office,
        "subjects_count": len(f.subjects),
        "email": f.user.email,
    }


@router.get("/faculty")
def faculty(page: Optional[int] = None, page_size: int = 24, q: Optional[str] = None,
            department_id: Optional[int] = None,
            db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    query = (
        db.query(models.Faculty)
        .join(models.User, models.User.id == models.Faculty.user_id)
        .join(models.Department, models.Department.id == models.Faculty.department_id)
        .options(
            joinedload(models.Faculty.user),
            joinedload(models.Faculty.department),
            selectinload(models.Faculty.subjects),
        )
    )
    if department_id is not None:
        query = query.filter(models.Faculty.department_id == department_id)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(models.User.full_name).like(like),
                                 func.lower(models.Department.name).like(like),
                                 func.lower(models.Department.code).like(like),
                                 func.lower(models.Faculty.employee_code).like(like)))
    query = query.order_by(models.Faculty.id)
    if page is None:
        return [_faculty_row(f) for f in query.all()]
    return paginate(query, page, page_size, _faculty_row)


@router.get("/departments")
def departments(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    return [
        {"id": d.id, "name": d.name, "code": d.code,
         "students": len(d.students), "faculty": len(d.faculty), "courses": len(d.courses)}
        for d in db.query(models.Department).all()
    ]


@router.get("/courses")
def courses(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    return [
        {"id": c.id, "name": c.name, "department": c.department.name,
         "subjects": [subject_summary(s) for s in c.subjects]}
        for c in db.query(models.Course).all()
    ]


@router.get("/reports/attendance")
def attendance_report(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    subjects = db.query(models.Subject).all()
    result = []
    for s in subjects:
        recs = s.attendance_records
        total = sum(a.total_classes for a in recs) or 1
        attended = sum(a.attended_classes for a in recs)
        result.append({
            "subject_code": s.code, "subject_name": s.name,
            "avg_attendance_pct": round((attended / total) * 100, 1),
            "students": len(recs),
        })
    return result


@router.get("/reports/academic")
def academic_report(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    subjects = db.query(models.Subject).all()
    result = []
    for s in subjects:
        recs = s.marks
        avg_pct = round(sum(mark_total(m) for m in recs) / (len(recs) * 100) * 100, 1) if recs else 0
        grade_dist = {}
        for m in recs:
            grade_dist[m.grade] = grade_dist.get(m.grade, 0) + 1
        result.append({
            "subject_code": s.code, "subject_name": s.name,
            "avg_marks_pct": avg_pct, "grade_distribution": grade_dist,
        })
    return result
