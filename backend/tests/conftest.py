"""
Test harness. Every test runs against a throwaway SQLite database built from the
Alembic migrations and filled with a small fixture campus - never the live,
seeded campusone.db.
"""
import os
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

# Environment must be set before the application is imported.
_TMP = Path(tempfile.mkdtemp(prefix="campusone-test-"))
os.environ["APP_ENV"] = "development"
# Default: a throwaway SQLite file. Set TEST_DATABASE_URL to run the same suite on
# PostgreSQL - the database name must contain "test" because its schema is wiped first.
_PG_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if _PG_URL:
    from sqlalchemy import create_engine as _ce, text as _text
    from sqlalchemy.engine import make_url as _make_url
    assert "test" in (_make_url(_PG_URL).database or ""), "TEST_DATABASE_URL must point at a database named *test*"
    with _ce(_PG_URL, isolation_level="AUTOCOMMIT").connect() as _c:
        _c.execute(_text("DROP SCHEMA IF EXISTS public CASCADE"))
        _c.execute(_text("CREATE SCHEMA public"))
    os.environ["DATABASE_URL"] = _PG_URL
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-only-secret-key-not-used-anywhere-else-0123456789"
os.environ["AUTO_SEED"] = "false"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["MAX_UPLOAD_MB"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import config, models  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.db_setup import prepare_database  # noqa: E402
from app.main import app  # noqa: E402
from app.od_bootstrap import ensure_od_foundation  # noqa: E402

LIVE_DB = Path(__file__).resolve().parent.parent / "campusone.db"
assert LIVE_DB.as_posix() not in config.DATABASE_URL, "Tests must never run against the live database."

PASSWORD = "pw-for-tests"


def next_weekday(weekday: int, after_days: int = 2) -> date:
    """The next given weekday (0 = Monday) at least `after_days` from today."""
    d = date.today() + timedelta(days=after_days)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


def _build_campus(db):
    pw = hash_password(PASSWORD)

    def user(username, role, name):
        u = models.User(username=username, password_hash=pw, role=role, full_name=name,
                        email=f"{username}@test.edu")
        db.add(u)
        db.flush()
        return u

    cse = models.Department(name="Computer Science and Engineering", code="CSE")
    ece = models.Department(name="Electronics and Communication Engineering", code="ECE")
    db.add_all([cse, ece])
    db.flush()

    # Admins: the first is institution-wide; the next two become HODs of CSE and ECE.
    user("admin", "admin", "Principal Admin")
    user("hod_cse", "admin", "Dr. CSE Head")
    user("hod_ece", "admin", "Dr. ECE Head")

    def faculty(username, name, dept, code):
        f = models.Faculty(user_id=user(username, "faculty", name).id, employee_code=code,
                           department_id=dept.id, designation="Professor", office="T-1")
        db.add(f)
        db.flush()
        return f

    fac1 = faculty("fac1", "Dr. Advisor One", cse, "E1")
    fac2 = faculty("fac2", "Dr. Other Two", cse, "E2")
    fac3 = faculty("fac3", "Dr. Ece Three", ece, "E3")

    course = models.Course(name="B.Tech CSE", department_id=cse.id)
    ece_course = models.Course(name="B.Tech ECE", department_id=ece.id)
    db.add_all([course, ece_course])
    db.flush()
    s301 = models.Subject(code="CSE301", name="Data Structures", semester=5, credits=4,
                          course_id=course.id, faculty_id=fac1.id)
    s302 = models.Subject(code="CSE302", name="Databases", semester=5, credits=4,
                          course_id=course.id, faculty_id=fac2.id)
    e301 = models.Subject(code="ECE301", name="Signals", semester=5, credits=4,
                          course_id=ece_course.id, faculty_id=fac3.id)
    db.add_all([s301, s302, e301])
    db.flush()
    # Monday classes, so an OD on a Monday morning earns attendance credits.
    db.add_all([
        models.TimetableSlot(subject_id=s301.id, day_of_week="Monday", start_time="10:00", end_time="10:50", room="R1"),
        models.TimetableSlot(subject_id=s302.id, day_of_week="Monday", start_time="11:00", end_time="11:50", room="R2"),
        models.TimetableSlot(subject_id=s301.id, day_of_week="Wednesday", start_time="14:00", end_time="14:50", room="R1"),
        models.TimetableSlot(subject_id=e301.id, day_of_week="Monday", start_time="10:00", end_time="10:50", room="R3"),
    ])

    def student(username, name, dept, reg, cgpa, attended, subjects):
        st = models.Student(user_id=user(username, "student", name).id, register_number=reg,
                            department_id=dept.id, year=3, semester=5, cgpa=cgpa,
                            accommodation_type="Day Scholar")
        db.add(st)
        db.flush()
        for subj in subjects:
            db.add(models.Attendance(student_id=st.id, subject_id=subj.id, total_classes=40, attended_classes=attended))
            db.add(models.Mark(student_id=st.id, subject_id=subj.id, internal_1=20, internal_2=20, assignment=10,
                               external=35, grade="A", sgpa_contribution=9))
        db.add(models.Fee(student_id=st.id, semester=5, total_amount=100000, paid_amount=100000,
                          due_date=date.today() + timedelta(days=20), status="Paid"))
        return st

    s1 = student("stu1", "Asha Student", cse, "21CSE0001", 8.5, 36, [s301, s302])    # 90%
    student("stu2", "Bala Student", cse, "21CSE0002", 7.9, 34, [s301, s302])          # 85%
    student("stu_low", "Chitra Lowatt", cse, "21CSE0003", 6.5, 24, [s301, s302])     # 60%
    student("stu_ece", "Deepak Ece", ece, "21ECE0001", 8.0, 36, [e301])

    club = models.Club(name="Coding Club", category="Technical", description="Code", faculty_coordinator_id=fac1.id,
                       meeting_day="Monday", meeting_time="16:00")
    db.add(club)
    db.flush()
    db.add(models.ClubMembership(student_id=s1.id, club_id=club.id, joined_on=date.today() - timedelta(days=90)))
    monday = next_weekday(0)
    db.add(models.ClubEvent(club_id=club.id, title="Coding Club Hackathon", description="24h build",
                            event_date=monday, start_time="09:00", end_time="13:00", venue="Innovation Hub"))
    db.add(models.ClubEvent(club_id=club.id, title="Coding Club Workshop", description="Past",
                            event_date=date.today() - timedelta(days=20), start_time="09:00", end_time="11:00",
                            venue="Seminar Hall 1"))

    company = models.Company(name="TestCorp", role="Engineer", ctc_lpa=10, min_cgpa=7.0,
                             eligible_departments="CSE", description="x")
    db.add(company)
    db.flush()
    db.add(models.PlacementDrive(company_id=company.id, drive_date=date.today() + timedelta(days=30),
                                 application_deadline=date.today() + timedelta(days=20), status="Open"))
    db.add(models.Exam(subject_id=s301.id, exam_type="Semester End Examination",
                       exam_date=date.today() + timedelta(days=25), start_time="10:00", end_time="13:00", venue="Hall 1"))
    db.add(models.Exam(subject_id=s301.id, exam_type="Internal Assessment 2",
                       exam_date=date.today() - timedelta(days=10), start_time="10:00", end_time="11:00", venue="Hall 2"))
    db.commit()


@pytest.fixture(scope="session", autouse=True)
def _database():
    prepare_database()  # empty DB -> schema built by the real Alembic migrations
    with SessionLocal() as db:
        _build_campus(db)
    with engine.begin() as conn:
        ensure_od_foundation(conn)
    yield
    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_od():
    """Each test starts with no OD requests and the default policy."""
    with engine.begin() as conn:
        for table in ("od_attendance_credits", "od_documents", "od_audit_logs", "od_requests", "chat_history"):
            conn.execute(text(f"delete from {table}"))
        conn.execute(text(
            "update institutions set od_hours_per_semester = 40, min_attendance_pct = 75, "
            "approval_chain = 'faculty,hod', hod_threshold_hours = 8, max_hours_per_request = 16, "
            "term_start = :s, term_end = :e"),
            {"s": date.today() - timedelta(days=60), "e": date.today() + timedelta(days=120)})
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class Api:
    """Small helper: one logged-in session per username."""

    def __init__(self, client):
        self.client = client
        self._tokens = {}

    def headers(self, username):
        if username not in self._tokens:
            r = self.client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
            assert r.status_code == 200, r.text
            self._tokens[username] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._tokens[username]}"}

    def get(self, username, path, **kw):
        return self.client.get(path, headers=self.headers(username), **kw)

    def post(self, username, path, **kw):
        return self.client.post(path, headers=self.headers(username), **kw)

    def put(self, username, path, **kw):
        return self.client.put(path, headers=self.headers(username), **kw)

    # --- OD shortcuts ---
    def apply(self, username="stu1", day=None, start="09:00", end="12:00", hours=3.0, name="Tech Symposium",
              submit=True, event_id=None, files=None, **extra):
        day = day or next_weekday(0)
        data = {
            "event_name": name, "requested_hours": str(hours), "submit": "true" if submit else "false",
            "start_at": f"{day}T{start}", "end_at": f"{extra.pop('end_day', day)}T{end}",
            "reason": "Participating", "organizer": "IEEE", "venue": "Main Auditorium",
        }
        if event_id is not None:
            data["event_id"] = str(event_id)
        data.update(extra)
        return self.post(username, "/api/student/od/requests", data=data, files=files)

    def act(self, username, role, request_id, action, version, **body):
        prefix = {"student": "/api/student/od", "faculty": "/api/faculty/od", "admin": "/api/admin/od"}[role]
        return self.post(username, f"{prefix}/requests/{request_id}/{action}", json={"version": version, **body})


@pytest.fixture(scope="session")
def api(client):
    return Api(client)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def at(day: date, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime.combine(day, time(int(h), int(m)))
