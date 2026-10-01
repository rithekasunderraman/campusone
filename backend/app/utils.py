from sqlalchemy.orm import Session
from fastapi import HTTPException
from . import models


def get_student_or_404(db: Session, user: models.User) -> models.Student:
    student = db.query(models.Student).filter(models.Student.user_id == user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


def get_faculty_or_404(db: Session, user: models.User) -> models.Faculty:
    faculty = db.query(models.Faculty).filter(models.Faculty.user_id == user.id).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found")
    return faculty


def attendance_pct(att: models.Attendance) -> float:
    if not att.total_classes:
        return 0.0
    return round((att.attended_classes / att.total_classes) * 100, 1)


def mark_total(m: models.Mark) -> float:
    return round(m.internal_1 + m.internal_2 + m.assignment + m.external, 1)


def student_summary(st: models.Student) -> dict:
    return {
        "id": st.id,
        "register_number": st.register_number,
        "full_name": st.user.full_name,
        "department": st.department.name,
        "department_code": st.department.code,
        "year": st.year,
        "semester": st.semester,
        "cgpa": st.cgpa,
        "email": st.user.email,
        "accommodation_type": st.accommodation_type,
    }


def subject_summary(s: models.Subject) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "semester": s.semester,
        "credits": s.credits,
        "faculty_name": s.faculty.user.full_name if s.faculty else None,
    }


def paginate(query, page: int = 1, page_size: int = 20, serialise=lambda row: row, max_page_size: int = 100) -> dict:
    """Run a query one page at a time and return a uniform envelope."""
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), max_page_size))
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialise(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }
