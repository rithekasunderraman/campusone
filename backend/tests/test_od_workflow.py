"""OD workflow: every state transition, every validation rule, concurrency and audit."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import models, od_service as svc
from app.database import engine
from tests.conftest import next_weekday

MON = next_weekday(0)
TUE = MON + timedelta(days=1)


def audit(db, request_id):
    rows = db.query(models.ODAuditLog).filter_by(request_id=request_id).order_by(models.ODAuditLog.id).all()
    return [(r.action, r.old_state, r.new_state, r.actor_role) for r in rows]


def failed(resp):
    return {c["code"] for c in resp.json()["detail"]["checks"] if not c["ok"]}


# --------------------------------------------------------------------- submission

def test_submit_routes_to_class_advisor_and_audits_each_transition(api, db):
    r = api.apply()
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["state"] == "UnderFacultyReview"
    assert body["status"] == "Pending"                       # legacy column stays in sync
    assert body["advisor_name"] == "Dr. Advisor One"
    assert body["requires_hod"] is False
    assert body["version"] == 3                              # create(1) -> submit(2) -> route(3)
    assert audit(db, body["id"]) == [
        ("create", None, "Draft", "student"),
        ("submit", "Draft", "Submitted", "student"),
        ("route_to_faculty", "Submitted", "UnderFacultyReview", "system"),
    ]
    assert [t["new_state"] for t in body["timeline"]] == ["Draft", "Submitted", "UnderFacultyReview"]


def test_save_draft_then_submit(api, db):
    r = api.apply(submit=False)
    assert r.status_code == 201
    draft = r.json()
    assert draft["state"] == "Draft" and draft["status"] == "Draft"
    assert draft["allowed_actions"] == ["cancel", "submit"]
    assert api.get("fac1", "/api/faculty/od/queue").json()["total"] == 0   # drafts are invisible to faculty
    r = api.act("stu1", "student", draft["id"], "submit", draft["version"])
    assert r.status_code == 200 and r.json()["state"] == "UnderFacultyReview"


def test_event_details_are_taken_from_the_selected_club_event(api, db):
    event = db.query(models.ClubEvent).filter_by(title="Coding Club Hackathon").one()
    r = api.apply(day=event.event_date, start="09:00", end="13:00", hours=4, name="", event_id=event.id,
                  organizer="", venue="")
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["event_name"], body["venue"], body["organizer"]) == \
        ("Coding Club Hackathon", "Innovation Hub", "Coding Club")


# --------------------------------------------------------------------- validation

def test_overlapping_request_is_rejected(api):
    assert api.apply(start="09:00", end="12:00").status_code == 201
    r = api.apply(start="11:00", end="13:00", hours=2, name="Another Event")
    assert r.status_code == 422
    assert failed(r) == {"overlap"}
    assert "Overlaps your request" in r.json()["detail"]["message"]


def test_adjacent_requests_do_not_overlap(api):
    assert api.apply(start="09:00", end="12:00").status_code == 201
    assert api.apply(start="12:00", end="14:00", hours=2, name="Afternoon Event").status_code == 201


def test_duplicate_request_for_same_event_is_detected_by_event_id(api, db):
    event = db.query(models.ClubEvent).filter_by(title="Coding Club Hackathon").one()
    args = dict(day=event.event_date, start="09:00", end="13:00", hours=4, name="", event_id=event.id)
    assert api.apply(**args).status_code == 201
    r = api.apply(**args)
    assert r.status_code == 422 and failed(r) == {"duplicate"}


def test_duplicate_request_is_detected_by_event_name(api):
    assert api.apply(name="National Hackathon 2026").status_code == 201
    r = api.apply(name="  national   HACKATHON-2026 ", start="10:00", end="11:00", hours=1)
    assert r.status_code == 422 and failed(r) == {"duplicate"}


def test_rejected_and_cancelled_requests_do_not_block_a_new_one(api):
    first = api.apply().json()
    assert api.act("fac1", "faculty", first["id"], "reject", first["version"], comment="No proof").status_code == 200
    second = api.apply()
    assert second.status_code == 201
    second = second.json()
    assert api.act("stu1", "student", second["id"], "cancel", second["version"]).status_code == 200
    assert api.apply().status_code == 201


def test_insufficient_balance_is_rejected(api):
    api.put("admin", "/api/admin/od/policy", json={
        "od_hours_per_semester": 5, "min_attendance_pct": 75, "approval_chain": ["faculty", "hod"],
        "hod_threshold_hours": 8, "max_hours_per_request": 16})
    assert api.apply(hours=3).status_code == 201                   # reserves 3 of 5
    r = api.apply(day=TUE, hours=3, name="Second")                 # only 2 left
    assert r.status_code == 422 and failed(r) == {"balance"}
    bal = api.get("stu1", "/api/student/od/balance").json()["balance"]
    assert (bal["allowance_hours"], bal["reserved_hours"], bal["available_hours"]) == (5, 3, 2)


def test_attendance_below_threshold_blocks_submission(api):
    r = api.apply(username="stu_low")
    assert r.status_code == 422 and failed(r) == {"attendance"}
    assert "60%" in r.json()["detail"]["message"]


def test_attendance_threshold_comes_from_policy_not_a_constant(api):
    api.put("admin", "/api/admin/od/policy", json={
        "od_hours_per_semester": 40, "min_attendance_pct": 55, "approval_chain": ["faculty", "hod"],
        "hod_threshold_hours": 8, "max_hours_per_request": 16})
    assert api.apply(username="stu_low").status_code == 201


@pytest.mark.parametrize("kwargs, code", [
    (dict(start="12:00", end="09:00"), "dates"),                              # end before start
    (dict(day=svc.today() + timedelta(days=400)), "dates"),                   # outside the term
    (dict(start="09:00", end="10:00", hours=3), "hours"),                     # more hours than the window
    (dict(hours=0), "hours"),
    (dict(end_day=TUE, start="09:00", end="17:00", hours=20), "hours"),       # above per-request limit
])
def test_invalid_dates_and_hours(api, kwargs, code):
    r = api.apply(**kwargs)
    assert r.status_code == 422
    assert code in failed(r)


def test_failed_submission_leaves_nothing_behind(api, db):
    assert api.apply(username="stu_low").status_code == 422
    assert db.query(models.ODRequest).count() == 0
    assert db.query(models.ODAuditLog).count() == 0


def test_eligibility_preview_matches_submission_rules(api):
    payload = {"start_at": f"{MON}T09:00", "end_at": f"{MON}T12:00", "requested_hours": 3, "event_name": "X"}
    ok = api.post("stu1", "/api/student/od/eligibility", json=payload).json()
    assert ok["eligible"] is True and all(c["ok"] for c in ok["checks"])
    assert ok["classes_affected"] == 2                    # Monday 10:00 and 11:00 classes
    assert ok["approval_route"] == ["Class advisor"]
    assert "You can apply" in ok["explanation"]
    low = api.post("stu_low", "/api/student/od/eligibility", json=payload).json()
    assert low["eligible"] is False and "cannot submit" in low["explanation"]


# --------------------------------------------------------------------- approval

def test_faculty_approval_updates_balance_and_attendance_in_one_step(api, db):
    req = api.apply().json()
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"], comment="Enjoy")
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["state"] == "Approved" and done["status"] == "Approved"
    assert done["approved_hours"] == 3 and done["decided_at"] and done["decision_comment"] == "Enjoy"
    assert audit(db, req["id"])[-1] == ("approve", "UnderFacultyReview", "Approved", "faculty")
    # balance
    bal = api.get("stu1", "/api/student/od/balance").json()
    assert (bal["balance"]["used_hours"], bal["balance"]["reserved_hours"], bal["balance"]["available_hours"]) == (3, 0, 37)
    # attendance credits: one class each for the two Monday-morning subjects
    credits = {c["subject_code"]: c["classes"] for c in done["attendance_credits"]}
    assert credits == {"CSE301": 1, "CSE302": 1}
    subjects = {s["subject_code"]: s for s in bal["attendance"]["subjects"]}
    assert subjects["CSE301"]["od_credited_classes"] == 1
    assert subjects["CSE301"]["effective_percentage"] == 92.5      # (36 + 1) / 40
    assert subjects["CSE301"]["percentage"] == 90.0                # raw attendance untouched


def test_partial_hours_can_be_approved_but_never_more_than_requested(api):
    req = api.apply(hours=3).json()
    assert api.act("fac1", "faculty", req["id"], "approve", req["version"], approved_hours=5).status_code == 422
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"], approved_hours=2)
    assert r.status_code == 200 and r.json()["approved_hours"] == 2


def test_long_request_needs_hod_sign_off(api, db):
    req = api.apply(start="08:00", end="18:00", hours=10).json()
    assert req["requires_hod"] is True
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"], comment="Recommended")
    fwd = r.json()
    assert r.status_code == 200 and fwd["state"] == "UnderHODReview"
    assert fwd["hod_name"] == "Dr. CSE Head"
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 0   # not approved yet
    assert db.query(models.ODAttendanceCredit).count() == 0

    assert api.get("hod_cse", "/api/admin/od/queue").json()["total"] == 1
    assert api.get("hod_ece", "/api/admin/od/queue").json()["total"] == 0                    # department scoped
    assert api.act("hod_ece", "admin", req["id"], "approve", fwd["version"]).status_code == 404

    r = api.act("hod_cse", "admin", req["id"], "approve", fwd["version"], comment="Approved by HOD")
    assert r.status_code == 200 and r.json()["state"] == "Approved"
    assert audit(db, req["id"])[-2:] == [
        ("forward_to_hod", "UnderFacultyReview", "UnderHODReview", "faculty"),
        ("approve", "UnderHODReview", "Approved", "admin"),
    ]
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 10


def test_institution_wide_admin_can_act_for_any_department(api):
    req = api.apply(start="08:00", end="18:00", hours=10).json()
    fwd = api.act("fac1", "faculty", req["id"], "approve", req["version"]).json()
    r = api.act("admin", "admin", req["id"], "reject", fwd["version"], comment="Clashes with exams")
    assert r.status_code == 200 and r.json()["state"] == "Rejected"


def test_hod_step_is_skipped_when_policy_chain_is_faculty_only(api):
    api.put("admin", "/api/admin/od/policy", json={
        "od_hours_per_semester": 40, "min_attendance_pct": 75, "approval_chain": ["faculty"],
        "hod_threshold_hours": 8, "max_hours_per_request": 16})
    req = api.apply(start="08:00", end="18:00", hours=10).json()
    assert req["requires_hod"] is False
    assert api.act("fac1", "faculty", req["id"], "approve", req["version"]).json()["state"] == "Approved"


def test_admin_cannot_decide_before_the_faculty_stage(api):
    req = api.apply().json()
    assert api.act("admin", "admin", req["id"], "approve", req["version"]).status_code == 409
    assert api.act("admin", "admin", req["id"], "reject", req["version"], comment="x").status_code == 409


# --------------------------------------------------------------------- rejection / clarification / cancel

def test_rejection_requires_a_reason_and_is_terminal(api, db):
    req = api.apply().json()
    assert api.act("fac1", "faculty", req["id"], "reject", req["version"]).status_code == 422
    r = api.act("fac1", "faculty", req["id"], "reject", req["version"], comment="Event not recognised")
    rejected = r.json()
    assert r.status_code == 200 and rejected["state"] == "Rejected"
    assert rejected["decision_comment"] == "Event not recognised" and rejected["allowed_actions"] == []
    for user, role, action in [("fac1", "faculty", "approve"), ("stu1", "student", "cancel")]:
        assert api.act(user, role, req["id"], action, rejected["version"]).status_code == 409
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 0


def test_clarification_round_trip(api, db):
    req = api.apply().json()
    assert api.act("fac1", "faculty", req["id"], "request-clarification", req["version"]).status_code == 422
    r = api.act("fac1", "faculty", req["id"], "request-clarification", req["version"], comment="Attach invitation")
    asked = r.json()
    assert asked["state"] == "ClarificationRequested" and asked["clarification_requested"] is True
    assert asked["clarification_text"] == "Attach invitation"
    assert api.get("fac1", "/api/faculty/od/queue").json()["total"] == 0
    assert api.get("fac1", "/api/faculty/od/queue?state=awaiting_student").json()["total"] == 1
    # faculty cannot decide while waiting on the student
    assert api.act("fac1", "faculty", req["id"], "approve", asked["version"]).status_code == 409

    r = api.post("stu1", f"/api/student/od/requests/{req['id']}/clarification-response",
                 json={"version": asked["version"], "response": "Invitation attached"})
    back = r.json()
    assert r.status_code == 200 and back["state"] == "Resubmitted"
    assert back["clarification_requested"] is False and back["clarification_response"] == "Invitation attached"
    assert api.get("fac1", "/api/faculty/od/queue").json()["total"] == 1

    assert api.act("fac1", "faculty", req["id"], "approve", back["version"]).json()["state"] == "Approved"
    assert [a[0] for a in audit(db, req["id"])] == [
        "create", "submit", "route_to_faculty", "request_clarification", "respond_clarification", "approve"]


def test_student_can_cancel_from_every_non_terminal_state(api):
    # Draft
    d = api.apply(submit=False).json()
    assert api.act("stu1", "student", d["id"], "cancel", d["version"]).json()["state"] == "Cancelled"
    # Under faculty review
    r1 = api.apply().json()
    assert api.act("stu1", "student", r1["id"], "cancel", r1["version"]).json()["state"] == "Cancelled"
    # Clarification requested
    r2 = api.apply().json()
    r2 = api.act("fac1", "faculty", r2["id"], "request-clarification", r2["version"], comment="?").json()
    assert api.act("stu1", "student", r2["id"], "cancel", r2["version"]).json()["state"] == "Cancelled"
    # Resubmitted
    r3 = api.apply().json()
    r3 = api.act("fac1", "faculty", r3["id"], "request-clarification", r3["version"], comment="?").json()
    r3 = api.post("stu1", f"/api/student/od/requests/{r3['id']}/clarification-response",
                  json={"version": r3["version"], "response": "ok"}).json()
    assert api.act("stu1", "student", r3["id"], "cancel", r3["version"]).json()["state"] == "Cancelled"
    # Under HOD review
    r4 = api.apply(start="08:00", end="18:00", hours=10).json()
    r4 = api.act("fac1", "faculty", r4["id"], "approve", r4["version"]).json()
    done = api.act("stu1", "student", r4["id"], "cancel", r4["version"]).json()
    assert done["state"] == "Cancelled" and done["cancelled_at"]
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["reserved_hours"] == 0


def test_approved_request_cannot_be_cancelled(api):
    req = api.apply().json()
    ok = api.act("fac1", "faculty", req["id"], "approve", req["version"]).json()
    r = api.act("stu1", "student", req["id"], "cancel", ok["version"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_transition"


# --------------------------------------------------------------------- authorisation

def test_only_the_assigned_advisor_can_act(api):
    req = api.apply().json()
    assert api.act("fac2", "faculty", req["id"], "approve", req["version"]).status_code == 404
    assert api.get("fac2", f"/api/faculty/od/requests/{req['id']}").status_code == 404
    assert api.get("fac2", "/api/faculty/od/queue").json()["total"] == 0


def test_students_cannot_see_or_touch_each_others_requests(api):
    req = api.apply().json()
    assert api.get("stu2", f"/api/student/od/requests/{req['id']}").status_code == 404
    assert api.act("stu2", "student", req["id"], "cancel", req["version"]).status_code == 404
    assert api.get("stu2", "/api/student/od/requests").json()["total"] == 0


def test_role_boundaries_on_od_endpoints(api):
    req = api.apply().json()
    assert api.act("stu1", "faculty", req["id"], "approve", req["version"]).status_code == 403
    assert api.act("stu1", "admin", req["id"], "approve", req["version"]).status_code == 403
    assert api.get("fac1", "/api/admin/od/analytics").status_code == 403
    assert api.get("fac1", "/api/student/od/balance").status_code == 403
    assert api.get("admin", "/api/faculty/od/queue").status_code == 403
    assert api.client.get("/api/student/od/requests").status_code == 401


# --------------------------------------------------------------------- concurrency

def test_stale_version_is_rejected(api, db):
    req = api.apply().json()
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"] - 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "stale_request"
    assert api.get("stu1", f"/api/student/od/requests/{req['id']}").json()["state"] == "UnderFacultyReview"


def test_second_reviewer_using_the_same_version_loses(api, db):
    req = api.apply().json()
    assert api.act("fac1", "faculty", req["id"], "approve", req["version"]).status_code == 200
    r = api.act("fac1", "faculty", req["id"], "reject", req["version"], comment="too late")
    assert r.status_code == 409
    assert [a[0] for a in audit(db, req["id"])].count("approve") == 1
    assert api.get("stu1", f"/api/student/od/requests/{req['id']}").json()["state"] == "Approved"


def test_concurrent_double_approval_only_one_wins(api, db):
    """Two HOD-level reviewers approve the same request at the same instant."""
    req = api.apply(start="08:00", end="18:00", hours=10).json()
    fwd = api.act("fac1", "faculty", req["id"], "approve", req["version"]).json()
    api.headers("hod_cse"), api.headers("admin")          # log both in before the race

    def approve(username):
        return api.act(username, "admin", req["id"], "approve", fwd["version"]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(approve, ["hod_cse", "admin"]))
    assert codes == [200, 409]
    db.expire_all()
    assert [a[0] for a in audit(db, req["id"])].count("approve") == 1
    # credits and balance were applied exactly once
    assert db.query(models.ODAttendanceCredit).filter_by(request_id=req["id"]).count() == 2
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 10


def test_balance_is_rechecked_at_approval_time(api):
    req = api.apply(hours=3).json()
    api.put("admin", "/api/admin/od/policy", json={
        "od_hours_per_semester": 2, "min_attendance_pct": 75, "approval_chain": ["faculty", "hod"],
        "hod_threshold_hours": 8, "max_hours_per_request": 16})
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "balance_exceeded"
    assert api.get("stu1", f"/api/student/od/requests/{req['id']}").json()["state"] == "UnderFacultyReview"


# --------------------------------------------------------------------- atomicity and audit

def test_approval_rolls_back_completely_if_attendance_adjustment_fails(api, db, monkeypatch):
    req = api.apply().json()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure while adjusting attendance")

    monkeypatch.setattr(svc, "class_credits", boom)
    r = api.act("fac1", "faculty", req["id"], "approve", req["version"])
    assert r.status_code == 500
    monkeypatch.undo()

    after = api.get("stu1", f"/api/student/od/requests/{req['id']}").json()
    assert after["state"] == "UnderFacultyReview" and after["version"] == req["version"]
    assert after["approved_hours"] == 0 and after["decided_at"] is None
    assert [a[0] for a in audit(db, req["id"])] == ["create", "submit", "route_to_faculty"]
    assert db.query(models.ODAttendanceCredit).count() == 0
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 0
    # and the request is still actionable afterwards
    assert api.act("fac1", "faculty", req["id"], "approve", req["version"]).status_code == 200


def test_every_transition_writes_exactly_one_audit_row(api, db):
    req = api.apply(start="08:00", end="18:00", hours=10).json()                        # 3 rows
    req = api.act("fac1", "faculty", req["id"], "request-clarification", req["version"], comment="?").json()
    req = api.post("stu1", f"/api/student/od/requests/{req['id']}/clarification-response",
                   json={"version": req["version"], "response": "done"}).json()
    req = api.act("fac1", "faculty", req["id"], "approve", req["version"]).json()       # forward
    req = api.act("hod_cse", "admin", req["id"], "approve", req["version"]).json()
    rows = audit(db, req["id"])
    assert len(rows) == 7 == req["version"]            # one row per version bump (create is version 1)
    for (_, old, new, _), (_, next_old, _, _) in zip(rows, rows[1:]):
        assert new == next_old                         # the chain is unbroken
    entries = api.get("admin", f"/api/admin/od/requests/{req['id']}/audit").json()["entries"]
    assert [e["action"] for e in entries] == [r[0] for r in rows]
    assert entries[-1]["actor_username"] == "hod_cse" and entries[2]["actor_name"] == "System"


def test_audit_log_rows_are_immutable(api, db):
    req = api.apply().json()
    row = db.query(models.ODAuditLog).filter_by(request_id=req["id"]).first()
    row.comment = "tampered"
    with pytest.raises(RuntimeError, match="immutable"):
        db.commit()
    db.rollback()
    row = db.query(models.ODAuditLog).filter_by(request_id=req["id"]).first()
    db.delete(row)
    with pytest.raises(RuntimeError, match="immutable"):
        db.commit()
    db.rollback()
    assert db.query(models.ODAuditLog).filter_by(request_id=req["id"]).count() == 3


def test_status_cannot_be_written_outside_the_workflow_engine(api, db):
    req = api.apply().json()
    row = db.get(models.ODRequest, req["id"])
    with pytest.raises(models.ODStateWriteForbidden):
        row.status = "Approved"
    with pytest.raises(models.ODStateWriteForbidden):
        row.workflow_state = "Approved"
    db.rollback()
    assert api.get("stu1", f"/api/student/od/requests/{req['id']}").json()["state"] == "UnderFacultyReview"


# --------------------------------------------------------------------- lists, search, analytics, policy

def test_student_list_is_paginated_filterable_and_searchable(api):
    for i in range(5):
        day = MON + timedelta(days=7 * i)
        assert api.apply(day=day, name=f"Event {i}").status_code == 201
    first = api.apply(day=MON + timedelta(days=1), name="Robotics Expo").json()
    api.act("fac1", "faculty", first["id"], "approve", first["version"])

    page1 = api.get("stu1", "/api/student/od/requests?page=1&page_size=4").json()
    assert (page1["total"], page1["pages"], len(page1["items"])) == (6, 2, 4)
    page2 = api.get("stu1", "/api/student/od/requests?page=2&page_size=4").json()
    assert len(page2["items"]) == 2
    assert not {i["id"] for i in page1["items"]} & {i["id"] for i in page2["items"]}
    assert api.get("stu1", "/api/student/od/requests?status=Approved").json()["total"] == 1
    assert api.get("stu1", "/api/student/od/requests?status=open").json()["total"] == 5
    assert api.get("stu1", "/api/student/od/requests?q=robot").json()["total"] == 1
    assert api.get("stu1", "/api/student/od/requests?status=Nonsense").status_code == 422


def test_faculty_queue_search_and_history(api):
    a = api.apply(username="stu1", name="Alpha Meet").json()
    api.apply(username="stu2", name="Beta Meet")
    queue = api.get("fac1", "/api/faculty/od/queue").json()
    assert queue["total"] == 2
    assert api.get("fac1", "/api/faculty/od/queue?q=bala").json()["total"] == 1            # by student name
    assert api.get("fac1", "/api/faculty/od/queue?q=21CSE0001").json()["total"] == 1       # by register number
    assert api.get("fac1", "/api/faculty/od/queue?q=beta").json()["total"] == 1            # by event
    api.act("fac1", "faculty", a["id"], "approve", a["version"], comment="ok")
    history = api.get("fac1", "/api/faculty/od/history").json()
    assert history["total"] == 1 and history["items"][0]["action"] == "approve"
    stats = api.get("fac1", "/api/faculty/od/stats").json()
    assert (stats["pending"], stats["approved_this_month"], stats["advisees"]) == (1, 1, 3)


def test_analytics_by_department(api):
    a = api.apply(username="stu1", hours=3).json()
    b = api.apply(username="stu2", hours=2, end="11:00").json()
    api.apply(username="stu_ece", hours=3)
    api.act("fac1", "faculty", a["id"], "approve", a["version"])
    api.act("fac1", "faculty", b["id"], "reject", b["version"], comment="no")

    data = api.get("admin", "/api/admin/od/analytics").json()
    cse = next(d for d in data["by_department"] if d["department"] == "CSE")
    ece = next(d for d in data["by_department"] if d["department"] == "ECE")
    assert (cse["approved"], cse["rejected"], cse["pending"], cse["approval_rate_pct"]) == (1, 1, 0, 50.0)
    assert cse["approved_hours"] == 3 and cse["utilisation_pct"] == 2.5     # 3h of 3 students x 40h
    assert cse["avg_turnaround_hours"] is not None and cse["decisions_with_turnaround"] == 2
    assert (ece["pending"], ece["approval_rate_pct"]) == (1, None)
    assert data["totals"]["requests"] == 3

    scoped = api.get("hod_ece", "/api/admin/od/analytics").json()
    assert [d["department"] for d in scoped["by_department"]] == ["ECE"]
    assert api.get("hod_ece", "/api/admin/od/requests").json()["total"] == 1
    assert api.get("hod_ece", "/api/admin/od/requests?department_id=1").status_code == 403


def test_policy_can_only_be_changed_by_an_institution_wide_admin(api):
    body = {"od_hours_per_semester": 30, "min_attendance_pct": 70, "approval_chain": ["faculty"],
            "hod_threshold_hours": 6, "max_hours_per_request": 12}
    assert api.put("hod_cse", "/api/admin/od/policy", json=body).status_code == 403
    assert api.put("fac1", "/api/admin/od/policy", json=body).status_code == 403
    r = api.put("admin", "/api/admin/od/policy", json=body)
    assert r.status_code == 200 and r.json()["approval_chain"] == ["faculty"]
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["allowance_hours"] == 30
    bad = dict(body, approval_chain=["hod"])
    assert api.put("admin", "/api/admin/od/policy", json=bad).status_code == 422


def test_legacy_requests_without_workflow_history_still_count(api, db):
    """Rows imported from the old schema (no audit trail) are picked up by the bootstrap and the balance."""
    from app.od_bootstrap import ensure_od_foundation
    event = db.query(models.ClubEvent).filter_by(title="Coding Club Workshop").one()
    student = db.query(models.Student).filter_by(register_number="21CSE0001").one()
    with engine.begin() as conn:
        conn.execute(text(
            "insert into od_requests (student_id, event_id, requested_hours, approved_hours, request_date, status, version) "
            "values (:s, :e, 4, 4, :d, 'Approved', 1)"), {"s": student.id, "e": event.id, "d": event.event_date})
        assert ensure_od_foundation(conn)["od_requests_backfilled"] == 1
    listing = api.get("stu1", "/api/student/od/requests").json()
    assert listing["items"][0]["state"] == "Approved" and listing["items"][0]["event_name"] == "Coding Club Workshop"
    assert api.get("stu1", "/api/student/od/balance").json()["balance"]["used_hours"] == 4
    assert api.get("stu1", "/api/student/campus-life/od").json()["used_hours"] == 4        # old endpoint agrees
