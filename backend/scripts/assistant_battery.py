"""
Assistant query battery against the full 6,025-user dataset.

Runs every example question for all three roles through the real HTTP API and
checks each answer against a value computed independently with SQL. It talks
only to the end-to-end test backend (a throwaway copy of the database) and
refuses to run against anything else.

    terminal 1:  python -m scripts.e2e_server
    terminal 2:  python -m scripts.assistant_battery

Writes docs/ASSISTANT_BATTERY.md with question, expected fact, actual answer and verdict.
"""
import json
import math
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8001/api"
DB = BACKEND / "e2e" / "e2e.db"
OUT = BACKEND.parent / "docs" / "ASSISTANT_BATTERY.md"
LOGINS = {"student1": "student123", "faculty1": "faculty123", "admin": "admin123", "admin2": "admin123"}


def http(method, path, token=None, body=None, form=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    if form is not None:
        boundary = "----battery"
        data = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                        for k, v in form.items()) + f"--{boundary}--\r\n".encode()
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, data, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def sql(query, *args):
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(query, args).fetchall()
    finally:
        con.close()


def main() -> int:
    status, health = http("GET", "/health")
    if status != 200 or health.get("instance") != "e2e":
        print("Refusing to run: http://127.0.0.1:8001 is not the e2e test backend. Start it with "
              "'python -m scripts.e2e_server'.")
        return 2
    tokens = {u: http("POST", "/auth/login", body={"username": u, "password": p})[1]["access_token"]
              for u, p in LOGINS.items()}
    results = []

    def check(role, user, question, expected, note=""):
        """expected: one string or a list of strings that must all appear in the answer."""
        _, out = http("POST", "/ai/chat", tokens[user], {"message": question})
        answer = out["response"]
        needles = [expected] if isinstance(expected, str) else expected
        ok = all(n in answer for n in needles)
        results.append({"role": role, "user": user, "q": question, "expected": " … ".join(needles), "note": note,
                        "actual": answer, "intent": out["intent"], "source": out["source"], "ok": ok})
        print(("PASS" if ok else "FAIL"), f"[{user}] {question}")
        if not ok:
            print("     expected:", needles, "\n     actual:  ", answer[:300])

    # ------------------------------------------------------------ independent facts (student1 = student id 1)
    att = sql("select s.name, a.attended_classes, a.total_classes from attendance a join subjects s on s.id = a.subject_id "
              "where a.student_id = 1 order by a.id")
    attended, total = sum(r[1] for r in att), sum(r[2] for r in att)
    overall = round(attended / total * 100, 1)
    cgpa = sql("select cgpa from students where id = 1")[0][0]
    can_miss = [(n, math.floor(a / 0.75 - t + 1e-9)) for n, a, t in att]
    today = date.today().isoformat()
    next_exam = sql("select s.name, e.exam_date from exams e join subjects s on s.id = e.subject_id "
                    "where e.subject_id in (select subject_id from attendance where student_id = 1) and e.exam_date >= ? "
                    "order by e.exam_date limit 1", today)
    past_exam = sql("select e.exam_date from exams e where e.subject_id in (select subject_id from attendance "
                    "where student_id = 1) and e.exam_date < ? order by e.exam_date limit 1", today)
    drives = [r[0] for r in sql(
        "select c.name from placement_drives d join companies c on c.id = d.company_id where d.status = 'Open' "
        "and c.min_cgpa <= ? and (',' || c.eligible_departments || ',') like '%,CSE,%'", cgpa)]
    clubs = [r[0] for r in sql("select c.name from clubs c join club_memberships m on m.club_id = c.id where m.student_id = 1")]

    S, F, A = "Student", "Faculty", "Admin"
    # ------------------------------------------------------------ student, before any OD activity
    check(S, "student1", "What is my attendance?", f"{overall}% ({attended}/{total} classes attended)")
    check(S, "student1", "What is my CGPA?", f"Your current CGPA is {cgpa}.")
    check(S, "student1", "How many more classes can I miss while staying above 75%?",
          [f"{n} (" for n, _ in can_miss] + [f"you can miss {c} more class" for _, c in can_miss],
          "floor(attended / 0.75 - total) per subject")
    check(S, "student1", "When are my exams?", [next_exam[0][0], next_exam[0][1]], "earliest exam dated today or later")
    if past_exam:
        _, out = http("POST", "/ai/chat", tokens["student1"], {"message": "When is my next exam?"})
        ok = past_exam[0][0] not in out["response"]
        results.append({"role": S, "user": "student1", "q": "When is my next exam? (must not list past exams)",
                        "expected": f"does not contain past exam date {past_exam[0][0]}", "note": "", "actual": out["response"],
                        "intent": out["intent"], "source": out["source"], "ok": ok})
        print("PASS" if ok else "FAIL", "[student1] next exam excludes past exams")
    check(S, "student1", "Which placement drives am I eligible for?", drives, "open drives, CSE eligible, min CGPA met")
    check(S, "student1", "What clubs am I part of?", clubs)
    check(S, "student1", "How many OD hours do I have left?", "used 0 OD hours and have 40 hours remaining out of 40")
    check(S, "student1", "Can I apply for OD tomorrow?", ["Yes, you can apply for OD tomorrow", "40 of 40 OD hours available",
                                                        f"attendance is {overall:g}%"])
    check(S, "student1", "What is the status of my last OD application?", "You have not submitted any OD requests yet.")
    check(S, "student1", "Why was my last OD application rejected?", "None of your OD requests has been rejected.")

    # ------------------------------------------------------------ faculty / admin, before OD activity
    queue = sql("select count(*) from od_requests where advisor_faculty_id = 1 and workflow_state in "
                "('UnderFacultyReview','Resubmitted')")[0][0]
    taught = sql("select count(distinct student_id) from attendance where subject_id in (select id from subjects where faculty_id = 1)")[0][0]
    low = sql("select s.name, count(*) from attendance a join subjects s on s.id = a.subject_id where s.faculty_id = 1 "
              "and a.attended_classes * 100.0 / a.total_classes < 75 group by s.id order by s.id")
    check(F, "faculty1", "How many OD requests are pending my approval?", f"You have {queue} OD request(s) waiting for your decision")
    check(F, "faculty1", "How many OD requests have I approved this month?", "This month you approved 0 OD request(s)")
    check(F, "faculty1", "How many students do I teach?", f"You currently teach {taught} unique students")
    check(F, "faculty1", "Which students are below 75% attendance?", [f"{n}: {c} students below 75%" for n, c in low])
    check(F, "faculty1", "What subjects do I teach?", [r[0] for r in sql("select code from subjects where faculty_id = 1")])

    by_dept = sql(
        "select d.code, count(o.id), sum(o.workflow_state = 'Approved'), sum(o.workflow_state = 'Rejected'), "
        "sum(o.workflow_state in ('Submitted','UnderFacultyReview','ClarificationRequested','Resubmitted','UnderHODReview')), "
        "sum(case when o.workflow_state = 'Approved' then o.approved_hours else 0 end), "
        "(select count(*) from students s2 where s2.department_id = d.id) "
        "from departments d join students s on s.department_id = d.id join od_requests o on o.student_id = s.id "
        "group by d.id order by d.id")
    pending_total = sum(r[4] for r in by_dept)
    top = max(by_dept, key=lambda r: r[5] / (r[6] * 40))
    check(A, "admin", "Show department-wise OD statistics",
          [f"- {c}: {n:,} requests, {a:,} approved, {r:,} rejected, {p:,} pending" for c, n, a, r, p, _, _ in by_dept])
    check(A, "admin", "How many OD requests are pending?", f"{pending_total} OD request(s) are awaiting a decision")
    check(A, "admin", "Which department has the highest OD utilisation?", f"{top[0]} has the highest OD utilisation",
          "max of approved hours / (students x 40)")
    check(A, "admin", "How many students are in CSE?", f"There are {sql('select count(*) from students where department_id = 1')[0][0]} students in")
    check(A, "admin", "How many students are placed?",
          f"{sql('select count(distinct student_id) from applications where status = ?', 'Offered')[0][0]} students have been placed")
    cse = by_dept[0]
    check(A, "admin2", "How many OD requests are pending?", f"{cse[4]} OD request(s) are awaiting a decision in your department",
          "admin2 heads CSE only: must see CSE's count, not the institution's")
    check(A, "admin2", "Show department-wise OD statistics", "- CSE:", "department head scope")
    _, out = http("POST", "/ai/chat", tokens["admin2"], {"message": "Show department-wise OD statistics for all departments"})
    ok = "ECE:" not in out["response"] and "MECH:" not in out["response"]
    results.append({"role": A, "user": "admin2", "q": "Show department-wise OD statistics for all departments",
                    "expected": "no ECE or MECH rows (scope is enforced server-side)", "note": "", "actual": out["response"],
                    "intent": out["intent"], "source": out["source"], "ok": ok})
    print("PASS" if ok else "FAIL", "[admin2] scope cannot be widened by the question")

    # ------------------------------------------------------------ live OD activity, then ask again
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 14)

    def apply(day, name, hours="3"):
        s, body = http("POST", "/student/od/requests", tokens["student1"], form={
            "event_name": name, "start_at": f"{day}T09:00", "end_at": f"{day}T12:00", "requested_hours": hours,
            "reason": "Battery run", "submit": "true"})
        assert s == 201, body
        return body

    first = apply(monday, "Battery Rejected Event")
    http("POST", f"/faculty/od/requests/{first['id']}/reject", tokens["faculty1"],
         {"version": first["version"], "comment": "Event is not recognised by the department"})
    second = apply(monday + timedelta(days=1), "Battery Approved Event")
    http("POST", f"/faculty/od/requests/{second['id']}/approve", tokens["faculty1"],
         {"version": second["version"], "comment": "Approved"})
    third = apply(monday + timedelta(days=2), "Battery Pending Event")

    check(S, "student1", "Why was my last OD application rejected?",
          [f"#{first['id']} \"Battery Rejected Event\"", "Reason: Event is not recognised by the department."],
          "after faculty1 rejected a request with that reason")
    check(S, "student1", "How many OD hours do I have left?",
          ["used 3 OD hours and have 37 hours remaining out of 40", "so 34 hours are available"],
          "3h approved, 3h in a pending request")
    check(S, "student1", "What is the status of my last OD application?",
          [f"#{third['id']} \"Battery Pending Event\"", "Status: Under faculty review"])
    check(S, "student1", f"Can I apply for OD on {(monday + timedelta(days=1)).isoformat()}?",
          ["You already have an OD request", f"#{second['id']}"], "that day already has an approved request")
    check(F, "faculty1", "How many OD requests are pending my approval?",
          f"You have {queue + 1} OD request(s) waiting for your decision", "one more than before")
    check(F, "faculty1", "How many OD requests have I approved this month?",
          "This month you approved 1 OD request(s), recommended 0 to the HOD, rejected 1")
    check(A, "admin", "How many OD requests are pending?", f"{pending_total + 1} OD request(s) are awaiting a decision")

    # ------------------------------------------------------------ report
    passed = sum(r["ok"] for r in results)
    OUT.parent.mkdir(exist_ok=True)
    lines = [
        "# Assistant query battery — evidence log", "",
        f"Run: {datetime.now():%Y-%m-%d %H:%M} against a copy of the full dataset "
        f"({sql('select count(*) from users')[0][0]:,} users). "
        f"LLM configured: {'yes' if any(r['source'] != 'database' and r['source'] != 'help' for r in results) else 'no (deterministic path)'}.", "",
        f"**Result: {passed} of {len(results)} checks passed.**", "",
        "Each expected value was computed independently with SQL (see `backend/scripts/assistant_battery.py`), "
        "not copied from the assistant.", "",
        "| # | Role (user) | Question | Expected (must appear) | Intent | Verdict |", "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['role']} ({r['user']}) | {r['q']} | {r['expected'].replace('|', '/')}"
                     f"{' — ' + r['note'] if r['note'] else ''} | `{r['intent']}` | {'PASS' if r['ok'] else '**FAIL**'} |")
    lines += ["", "## Actual responses", ""]
    for i, r in enumerate(results, 1):
        lines += [f"**{i}. [{r['user']}] {r['q']}**", "", "```", r["actual"], "```", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{passed}/{len(results)} passed. Report: {OUT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
