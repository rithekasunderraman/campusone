"""Authentication, role boundaries, paginated lists, institution profile and configuration."""
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from jose import jwt

from app import config
from tests.conftest import PASSWORD

BACKEND = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------- authentication

@pytest.mark.parametrize("username, role, name", [
    ("admin", "admin", "Principal Admin"), ("fac1", "faculty", "Dr. Advisor One"), ("stu1", "student", "Asha Student"),
])
def test_login_returns_a_token_for_each_role(client, username, role, name):
    r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert (body["role"], body["full_name"], body["token_type"]) == (role, name, "bearer")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == username


@pytest.mark.parametrize("payload", [
    {"username": "stu1", "password": "wrong"},
    {"username": "nobody", "password": PASSWORD},
    {"username": "stu1' OR '1'='1", "password": "x"},
])
def test_login_rejects_bad_credentials(client, payload):
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 401 and r.json()["detail"] == "Invalid username or password"


def _token(**claims):
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def test_missing_malformed_expired_and_forged_tokens_are_rejected(client, api):
    path = "/api/student/dashboard"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    expired = _token(sub="stu1", role="student", exp=datetime.utcnow() - timedelta(minutes=1))
    assert client.get(path, headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = jwt.encode({"sub": "stu1", "role": "student", "exp": datetime.utcnow() + timedelta(hours=1)},
                        "some-other-secret", algorithm="HS256")
    assert client.get(path, headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    ghost = _token(sub="deleted-user", role="admin", exp=datetime.utcnow() + timedelta(hours=1))
    assert client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401
    assert api.get("stu1", path).status_code == 200


def test_role_claim_in_the_token_is_not_trusted(client):
    """A student token that claims role=admin is still a student: the role is read from the database."""
    lying = _token(sub="stu1", role="admin", exp=datetime.utcnow() + timedelta(hours=1))
    headers = {"Authorization": f"Bearer {lying}"}
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 403
    assert client.get("/api/admin/od/analytics", headers=headers).status_code == 403
    assert client.get("/api/student/dashboard", headers=headers).status_code == 200


ROLE_MATRIX = [
    # path, roles allowed
    ("/api/student/dashboard", {"student"}),
    ("/api/student/attendance", {"student"}),
    ("/api/student/campus-life/od", {"student"}),
    ("/api/student/od/balance", {"student"}),
    ("/api/student/od/requests", {"student"}),
    ("/api/placement/eligible", {"student"}),
    ("/api/faculty/dashboard", {"faculty"}),
    ("/api/faculty/students", {"faculty"}),
    ("/api/faculty/od/queue", {"faculty"}),
    ("/api/faculty/od/history", {"faculty"}),
    ("/api/admin/dashboard", {"admin"}),
    ("/api/admin/students", {"admin"}),
    ("/api/admin/od/queue", {"admin"}),
    ("/api/admin/od/analytics", {"admin"}),
    ("/api/admin/od/policy", {"admin"}),
    ("/api/placement/admin/applications", {"admin"}),
    ("/api/announcements", {"student", "faculty", "admin"}),
    ("/api/ai/history", {"student", "faculty", "admin"}),
]


@pytest.mark.parametrize("path, allowed", ROLE_MATRIX)
def test_role_matrix(api, path, allowed):
    for user, role in (("stu1", "student"), ("fac1", "faculty"), ("admin", "admin")):
        status = api.get(user, path).status_code
        assert status == (200 if role in allowed else 403), f"{role} -> {path} gave {status}"
    assert api.client.get(path).status_code == 401


def test_faculty_cannot_edit_another_facultys_records(api, db):
    from app import models
    other = db.query(models.Attendance).join(models.Subject).filter(models.Subject.code == "CSE302").first()
    r = api.post("fac1", "/api/faculty/attendance", json={
        "attendance_id": other.id, "total_classes": 1, "attended_classes": 1})
    assert r.status_code == 404
    subject = db.query(models.Subject).filter_by(code="CSE302").one()
    assert api.get("fac1", f"/api/faculty/attendance?subject_id={subject.id}").status_code == 404


# --------------------------------------------------------------------- paginated lists

def test_admin_students_pagination_and_search(api):
    full = api.get("admin", "/api/admin/students").json()
    assert isinstance(full, list) and len(full) == 4                      # original shape without `page`
    page1 = api.get("admin", "/api/admin/students?page=1&page_size=3").json()
    assert (page1["total"], page1["pages"], len(page1["items"])) == (4, 2, 3)
    page2 = api.get("admin", "/api/admin/students?page=2&page_size=3").json()
    assert len(page2["items"]) == 1
    assert [s["id"] for s in page1["items"] + page2["items"]] == [s["id"] for s in full]
    assert api.get("admin", "/api/admin/students?page=1&q=lowatt").json()["total"] == 1
    assert api.get("admin", "/api/admin/students?page=1&q=21ECE").json()["total"] == 1
    assert api.get("admin", "/api/admin/students?page=1&q=ece").json()["total"] == 1       # department code
    assert api.get("admin", "/api/admin/students?page=1&q=zzz").json()["total"] == 0
    assert api.get("admin", "/api/admin/students?page=1&page_size=100000").json()["page_size"] == 100   # capped


def test_admin_faculty_and_placement_lists(api):
    fac = api.get("admin", "/api/admin/faculty?page=1&page_size=2").json()
    assert (fac["total"], len(fac["items"])) == (3, 2) and "subjects_count" in fac["items"][0]
    assert api.get("admin", "/api/admin/faculty?page=1&q=electronics").json()["total"] == 1
    assert len(api.get("admin", "/api/admin/faculty").json()) == 3

    drive = api.get("stu1", "/api/placement/eligible").json()[0]["id"]
    assert api.post("stu1", f"/api/placement/apply/{drive}").status_code == 200
    apps = api.get("admin", "/api/placement/admin/applications?page=1").json()
    assert apps["total"] == 1 and apps["items"][0]["student_name"] == "Asha Student"
    assert api.get("admin", "/api/placement/admin/applications?page=1&q=testcorp").json()["total"] == 1
    assert api.get("admin", "/api/placement/admin/applications?page=1&status=Offered").json()["total"] == 0
    assert isinstance(api.get("admin", "/api/placement/admin/applications").json(), list)


def test_faculty_lists_are_paginated_and_scoped(api, db):
    from app import models
    subject = db.query(models.Subject).filter_by(code="CSE301").one()
    students = api.get("fac1", "/api/faculty/students?page=1&page_size=2").json()
    assert (students["total"], len(students["items"])) == (3, 2)
    assert api.get("fac1", "/api/faculty/students?page=1&q=bala").json()["total"] == 1
    att = api.get("fac1", f"/api/faculty/attendance?subject_id={subject.id}&page=1&page_size=2").json()
    assert (att["total"], len(att["items"])) == (3, 2) and "attendance_id" in att["items"][0]
    assert api.get("fac1", f"/api/faculty/attendance?subject_id={subject.id}&page=1&q=21CSE0003").json()["total"] == 1
    marks = api.get("fac1", f"/api/faculty/marks?subject_id={subject.id}&page=2&page_size=2").json()
    assert len(marks["items"]) == 1 and marks["items"][0]["grade"] == "A"
    assert len(api.get("fac1", f"/api/faculty/marks?subject_id={subject.id}").json()) == 3


# --------------------------------------------------------------------- institution + health

def test_institution_profile(api):
    public = api.client.get("/api/institution")
    assert public.status_code == 200 and public.json()["name"] == "CampusOne University"
    assert "od_hours_per_semester" not in public.json()                 # branding only
    body = {"name": "Test Institute of Technology", "short_name": "TIT", "support_email": "help@tit.edu"}
    assert api.put("hod_cse", "/api/admin/institution", json=body).status_code == 403
    assert api.put("stu1", "/api/admin/institution", json=body).status_code == 403
    assert api.put("admin", "/api/admin/institution", json={"name": "  "}).status_code == 422
    assert api.put("admin", "/api/admin/institution", json=body).json()["name"] == "Test Institute of Technology"
    assert api.get("admin", "/api/admin/od/policy").json()["institution"] == "Test Institute of Technology"
    api.put("admin", "/api/admin/institution", json={"name": "CampusOne University", "short_name": "CampusOne"})


def test_every_new_table_carries_institution_id(db):
    from app import models
    for model in (models.AdvisorAssignment, models.DepartmentHead, models.ODDocument, models.ODAuditLog,
                  models.ODAttendanceCredit, models.StoredFile, models.ODRequest):
        assert "institution_id" in model.__table__.columns, model.__tablename__
    assert db.query(models.Institution).count() == 1


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["database"] == "ok"


def test_cors_allows_only_the_configured_origin(client):
    ok = client.options("/api/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/auth/login", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


# --------------------------------------------------------------------- configuration

def _config_exit(env: dict):
    base = {"PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
            "JWT_SECRET": " ", "DATABASE_URL": " ", "CORS_ORIGINS": " ", "ANTHROPIC_API_KEY": " "}
    base.update(env)
    proc = subprocess.run([sys.executable, "-c", "import app.config"], cwd=BACKEND, env=base,
                          capture_output=True, text=True)
    return proc.returncode, proc.stderr


def test_production_refuses_to_start_without_real_secrets():
    strong = "s" * 48
    code, err = _config_exit({"APP_ENV": "production"})
    assert code != 0 and "JWT_SECRET is required" in err
    code, err = _config_exit({"APP_ENV": "production", "JWT_SECRET": "short"})
    assert code != 0 and "too weak" in err
    code, err = _config_exit({"APP_ENV": "production", "JWT_SECRET": "campusone-ai-dev-secret-key-change-in-production"})
    assert code != 0 and "too weak" in err
    code, err = _config_exit({"APP_ENV": "production", "JWT_SECRET": strong})
    assert code != 0 and "DATABASE_URL is required" in err
    code, err = _config_exit({"APP_ENV": "production", "JWT_SECRET": strong, "DATABASE_URL": "postgresql://u:p@h/d",
                              "CORS_ORIGINS": "*"})
    assert code != 0 and "not '*'" in err
    code, err = _config_exit({"APP_ENV": "production", "JWT_SECRET": strong, "DATABASE_URL": "postgres://u:p@h/d",
                              "CORS_ORIGINS": "https://app.example.com"})
    assert code == 0, err


@pytest.mark.skipif(not config.IS_SQLITE, reason="copies the SQLite test database file")
def test_seed_refuses_to_wipe_a_populated_database(tmp_path):
    """python -m app.seed must not drop tables that already hold data unless explicitly forced."""
    import shutil
    import sqlite3
    copy = tmp_path / "copy.db"
    src = sqlite3.connect(config.DATABASE_URL.replace("sqlite:///", ""))
    dst = sqlite3.connect(copy)
    src.backup(dst)
    src.close()
    dst.close()
    env = dict(__import__("os").environ, DATABASE_URL=f"sqlite:///{copy.as_posix()}")
    proc = subprocess.run([sys.executable, "-m", "app.seed"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert proc.returncode != 0 and "already contains data" in proc.stderr
    con = sqlite3.connect(copy)
    assert con.execute("select count(*) from users").fetchone()[0] == 10
    con.close()
    shutil.rmtree(tmp_path, ignore_errors=True)
