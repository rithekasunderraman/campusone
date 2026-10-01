from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime

from .. import models
from ..database import get_db
from ..auth import require_role
from ..utils import get_student_or_404, paginate

router = APIRouter(prefix="/api/placement", tags=["placement"])
require_student = require_role("student")
require_admin = require_role("admin")


def _company_dict(c: models.Company):
    return {
        "id": c.id, "name": c.name, "role": c.role, "ctc_lpa": c.ctc_lpa,
        "min_cgpa": c.min_cgpa, "eligible_departments": c.eligible_departments.split(","),
        "description": c.description,
    }


def _drive_dict(d: models.PlacementDrive):
    return {
        "id": d.id, "company": _company_dict(d.company), "drive_date": str(d.drive_date),
        "application_deadline": str(d.application_deadline), "status": d.status,
        "applicants": len(d.applications),
    }


@router.get("/companies")
def companies(db: Session = Depends(get_db)):
    return [_company_dict(c) for c in db.query(models.Company).all()]


@router.get("/drives")
def drives(db: Session = Depends(get_db)):
    return [_drive_dict(d) for d in db.query(models.PlacementDrive).order_by(models.PlacementDrive.drive_date).all()]


@router.get("/eligible")
def eligible_drives(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    dept_code = st.department.code
    result = []
    for d in db.query(models.PlacementDrive).filter(models.PlacementDrive.status == "Open").all():
        c = d.company
        if dept_code in c.eligible_departments.split(",") and st.cgpa >= c.min_cgpa:
            already_applied = db.query(models.Application).filter(
                models.Application.student_id == st.id, models.Application.drive_id == d.id
            ).first()
            entry = _drive_dict(d)
            entry["already_applied"] = bool(already_applied)
            result.append(entry)
    return result


@router.get("/my-applications")
def my_applications(db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    apps = db.query(models.Application).filter(models.Application.student_id == st.id).all()
    return [
        {
            "id": a.id, "company": a.drive.company.name, "role": a.drive.company.role,
            "ctc_lpa": a.drive.company.ctc_lpa, "status": a.status,
            "applied_on": a.applied_on.isoformat(), "drive_date": str(a.drive.drive_date),
        }
        for a in apps
    ]


@router.post("/apply/{drive_id}")
def apply(drive_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_student)):
    st = get_student_or_404(db, user)
    drive = db.query(models.PlacementDrive).filter(models.PlacementDrive.id == drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Placement drive not found")
    if drive.status != "Open":
        raise HTTPException(status_code=400, detail="This drive is not open for applications")
    company = drive.company
    if st.department.code not in company.eligible_departments.split(","):
        raise HTTPException(status_code=403, detail="You are not eligible for this drive (department)")
    if st.cgpa < company.min_cgpa:
        raise HTTPException(status_code=403, detail=f"Minimum CGPA required is {company.min_cgpa}")
    existing = db.query(models.Application).filter(
        models.Application.student_id == st.id, models.Application.drive_id == drive_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already applied to this drive")
    app = models.Application(student_id=st.id, drive_id=drive_id, status="Applied")
    db.add(app)
    db.commit()
    return {"message": f"Applied to {company.name} successfully", "application_id": app.id}


# ---------------- Admin / TPO ----------------

class CompanyCreate(BaseModel):
    name: str
    role: str
    ctc_lpa: float
    min_cgpa: float
    eligible_departments: str  # comma separated codes e.g. "CSE,ECE"
    description: str = ""


@router.post("/admin/companies")
def create_company(payload: CompanyCreate, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    c = models.Company(**payload.dict())
    db.add(c)
    db.commit()
    return {"message": "Company added", "id": c.id}


class DriveCreate(BaseModel):
    company_id: int
    drive_date: date
    application_deadline: date


@router.post("/admin/drives")
def create_drive(payload: DriveCreate, db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    company = db.query(models.Company).filter(models.Company.id == payload.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    d = models.PlacementDrive(company_id=payload.company_id, drive_date=payload.drive_date,
                               application_deadline=payload.application_deadline, status="Open")
    db.add(d)
    db.commit()
    return {"message": "Placement drive created", "id": d.id}


def _application_row(a: models.Application) -> dict:
    return {
        "id": a.id, "student_name": a.student.user.full_name,
        "register_number": a.student.register_number, "department": a.student.department.code,
        "cgpa": a.student.cgpa, "company": a.drive.company.name, "status": a.status,
        "applied_on": a.applied_on.isoformat(),
    }


@router.get("/admin/applications")
def all_applications(drive_id: int = None, page: Optional[int] = None, page_size: int = 25,
                     q: Optional[str] = None, status: Optional[str] = None,
                     db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    query = (
        db.query(models.Application)
        .join(models.Student, models.Student.id == models.Application.student_id)
        .join(models.User, models.User.id == models.Student.user_id)
        .join(models.PlacementDrive, models.PlacementDrive.id == models.Application.drive_id)
        .join(models.Company, models.Company.id == models.PlacementDrive.company_id)
        .options(joinedload(models.Application.student).joinedload(models.Student.user),
                 joinedload(models.Application.student).joinedload(models.Student.department),
                 joinedload(models.Application.drive).joinedload(models.PlacementDrive.company))
    )
    if drive_id:
        query = query.filter(models.Application.drive_id == drive_id)
    if status:
        query = query.filter(models.Application.status == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(models.User.full_name).like(like),
                                 func.lower(models.Student.register_number).like(like),
                                 func.lower(models.Company.name).like(like)))
    query = query.order_by(models.Application.id)
    if page is None:
        return [_application_row(a) for a in query.all()]
    return paginate(query, page, page_size, _application_row)


class ApplicationStatusUpdate(BaseModel):
    status: str  # Applied|Shortlisted|Interview|Offered|Rejected


@router.patch("/admin/applications/{application_id}")
def update_application_status(application_id: int, payload: ApplicationStatusUpdate,
                               db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    app = db.query(models.Application).filter(models.Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = payload.status
    db.commit()
    return {"message": "Application status updated", "status": app.status}


@router.get("/admin/analytics")
def placement_analytics(db: Session = Depends(get_db), user: models.User = Depends(require_admin)):
    # Aggregated in SQL: the previous version loaded every application and its
    # student, drive and company one row at a time (10 s at 7,000 applications).
    status_counts = dict(db.query(models.Application.status, func.count(models.Application.id))
                         .group_by(models.Application.status).all())
    offers = (
        db.query(models.Department.code, func.count(models.Application.id),
                 func.avg(models.Company.ctc_lpa), func.max(models.Company.ctc_lpa), func.sum(models.Company.ctc_lpa))
        .select_from(models.Application)
        .join(models.Student, models.Student.id == models.Application.student_id)
        .join(models.Department, models.Department.id == models.Student.department_id)
        .join(models.PlacementDrive, models.PlacementDrive.id == models.Application.drive_id)
        .join(models.Company, models.Company.id == models.PlacementDrive.company_id)
        .filter(models.Application.status == "Offered")
        .group_by(models.Department.id, models.Department.code)
        .order_by(models.Department.id)
        .all()
    )
    total_offers = sum(row[1] for row in offers)
    total_ctc = sum(float(row[4] or 0) for row in offers)
    return {
        "total_applications": sum(status_counts.values()),
        "total_offers": total_offers,
        "average_ctc_lpa": round(total_ctc / total_offers, 2) if total_offers else 0,
        "highest_ctc_lpa": max((float(row[3]) for row in offers), default=0),
        "department_summary": [
            {"department": code, "offers": n, "avg_ctc_lpa": round(float(avg), 2), "highest_ctc_lpa": float(top)}
            for code, n, avg, top, _ in offers
        ],
        "status_breakdown": {
            status: status_counts.get(status, 0)
            for status in ["Applied", "Shortlisted", "Interview", "Offered", "Rejected"]
        },
    }
