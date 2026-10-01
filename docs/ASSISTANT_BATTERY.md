# Assistant query battery — evidence log

Run: 2026-10-01 13:21 against a copy of the full dataset (6,025 users). LLM configured: no (deterministic path).

**Result: 31 of 31 checks passed.**

Each expected value was computed independently with SQL (see `backend/scripts/assistant_battery.py`), not copied from the assistant.

| # | Role (user) | Question | Expected (must appear) | Intent | Verdict |
|---|---|---|---|---|---|
| 1 | Student (student1) | What is my attendance? | 87.6% (190/217 classes attended) | `attendance` | PASS |
| 2 | Student (student1) | What is my CGPA? | Your current CGPA is 8.42. | `cgpa` | PASS |
| 3 | Student (student1) | How many more classes can I miss while staying above 75%? | Data Structures and Algorithms ( … Database Management Systems ( … Operating Systems ( … Computer Networks ( … Software Engineering ( … you can miss 7 more class … you can miss 6 more class … you can miss 9 more class … you can miss 3 more class … you can miss 11 more class — floor(attended / 0.75 - total) per subject | `attendance_headroom` | PASS |
| 4 | Student (student1) | When are my exams? | Data Structures and Algorithms … 2026-10-21 — earliest exam dated today or later | `exams` | PASS |
| 5 | Student (student1) | When is my next exam? (must not list past exams) | does not contain past exam date 2026-09-21 | `exams` | PASS |
| 6 | Student (student1) | Which placement drives am I eligible for? | TechNova Solutions … Quantum Analytics … Infinite Systems … Nimbus Cloud Labs — open drives, CSE eligible, min CGPA met | `placement` | PASS |
| 7 | Student (student1) | What clubs am I part of? | Sports Club … Football Club | `campus_life` | PASS |
| 8 | Student (student1) | How many OD hours do I have left? | used 0 OD hours and have 40 hours remaining out of 40 | `od_balance` | PASS |
| 9 | Student (student1) | Can I apply for OD tomorrow? | Yes, you can apply for OD tomorrow … 40 of 40 OD hours available … attendance is 87.6% | `od_can_apply` | PASS |
| 10 | Student (student1) | What is the status of my last OD application? | You have not submitted any OD requests yet. | `od_last_status` | PASS |
| 11 | Student (student1) | Why was my last OD application rejected? | None of your OD requests has been rejected. | `od_rejection_reason` | PASS |
| 12 | Faculty (faculty1) | How many OD requests are pending my approval? | You have 4 OD request(s) waiting for your decision | `od_faculty_pending` | PASS |
| 13 | Faculty (faculty1) | How many OD requests have I approved this month? | This month you approved 0 OD request(s) | `od_faculty_month` | PASS |
| 14 | Faculty (faculty1) | How many students do I teach? | You currently teach 1667 unique students | `faculty_student_count` | PASS |
| 15 | Faculty (faculty1) | Which students are below 75% attendance? | Data Structures and Algorithms: 814 students below 75% … Operating Systems: 866 students below 75% … Software Engineering: 829 students below 75% | `faculty_low_attendance` | PASS |
| 16 | Faculty (faculty1) | What subjects do I teach? | CSE301 … CSE303 … CSE305 | `faculty_subjects` | PASS |
| 17 | Admin (admin) | Show department-wise OD statistics | - CSE: 3,477 requests, 3,194 approved, 140 rejected, 143 pending … - ECE: 3,515 requests, 3,199 approved, 170 rejected, 146 pending … - MECH: 3,510 requests, 3,225 approved, 134 rejected, 151 pending | `od_admin_department_stats` | PASS |
| 18 | Admin (admin) | How many OD requests are pending? | 440 OD request(s) are awaiting a decision | `od_admin_pending` | PASS |
| 19 | Admin (admin) | Which department has the highest OD utilisation? | MECH has the highest OD utilisation — max of approved hours / (students x 40) | `od_admin_top_utilisation` | PASS |
| 20 | Admin (admin) | How many students are in CSE? | There are 1667 students in | `admin_student_count` | PASS |
| 21 | Admin (admin) | How many students are placed? | 1261 students have been placed | `admin_placed` | PASS |
| 22 | Admin (admin2) | How many OD requests are pending? | 143 OD request(s) are awaiting a decision in your department — admin2 heads CSE only: must see CSE's count, not the institution's | `od_admin_pending` | PASS |
| 23 | Admin (admin2) | Show department-wise OD statistics | - CSE: — department head scope | `od_admin_department_stats` | PASS |
| 24 | Admin (admin2) | Show department-wise OD statistics for all departments | no ECE or MECH rows (scope is enforced server-side) | `od_admin_department_stats` | PASS |
| 25 | Student (student1) | Why was my last OD application rejected? | #10503 "Battery Rejected Event" … Reason: Event is not recognised by the department. — after faculty1 rejected a request with that reason | `od_rejection_reason` | PASS |
| 26 | Student (student1) | How many OD hours do I have left? | used 3 OD hours and have 37 hours remaining out of 40 … so 34 hours are available — 3h approved, 3h in a pending request | `od_balance` | PASS |
| 27 | Student (student1) | What is the status of my last OD application? | #10505 "Battery Pending Event" … Status: Under faculty review | `od_last_status` | PASS |
| 28 | Student (student1) | Can I apply for OD on 2026-10-20? | You already have an OD request … #10504 — that day already has an approved request | `od_can_apply` | PASS |
| 29 | Faculty (faculty1) | How many OD requests are pending my approval? | You have 5 OD request(s) waiting for your decision — one more than before | `od_faculty_pending` | PASS |
| 30 | Faculty (faculty1) | How many OD requests have I approved this month? | This month you approved 1 OD request(s), recommended 0 to the HOD, rejected 1 | `od_faculty_month` | PASS |
| 31 | Admin (admin) | How many OD requests are pending? | 441 OD request(s) are awaiting a decision | `od_admin_pending` | PASS |

## Actual responses

**1. [student1] What is my attendance?**

```
Your overall attendance is 87.6% (190/217 classes attended). You are meeting the 75% requirement in all subjects.
```

**2. [student1] What is my CGPA?**

```
Your current CGPA is 8.42.
```

**3. [student1] How many more classes can I miss while staying above 75%?**

```
Your overall attendance is 87.6%. To stay at or above 75% in each subject (counting each missed class as held):
- Data Structures and Algorithms (87%): you can miss 7 more classes
- Database Management Systems (85.7%): you can miss 6 more classes
- Operating Systems (90.7%): you can miss 9 more classes
- Computer Networks (80.5%): you can miss 3 more classes
- Software Engineering (93.3%): you can miss 11 more classes
```

**4. [student1] When are my exams?**

```
Your next exams are:
- Data Structures and Algorithms (Semester End Examination) on 2026-10-21 at Exam Hall 5
- Operating Systems (Semester End Examination) on 2026-10-22 at Exam Hall 4
- Database Management Systems (Semester End Examination) on 2026-10-23 at Exam Hall 1
- Computer Networks (Semester End Examination) on 2026-10-27 at Exam Hall 5
- Software Engineering (Semester End Examination) on 2026-10-31 at Exam Hall 1
```

**5. [student1] When is my next exam? (must not list past exams)**

```
Your next exams are:
- Data Structures and Algorithms (Semester End Examination) on 2026-10-21 at Exam Hall 5
- Operating Systems (Semester End Examination) on 2026-10-22 at Exam Hall 4
- Database Management Systems (Semester End Examination) on 2026-10-23 at Exam Hall 1
- Computer Networks (Semester End Examination) on 2026-10-27 at Exam Hall 5
- Software Engineering (Semester End Examination) on 2026-10-31 at Exam Hall 1
```

**6. [student1] Which placement drives am I eligible for?**

```
You are eligible for these open placement drives:
- TechNova Solutions (Software Engineer), CTC 12.5 LPA, apply by 2026-10-14
- Quantum Analytics (Data Analyst), CTC 9.0 LPA, apply by 2026-10-03
- Infinite Systems (Full Stack Developer), CTC 8.5 LPA, apply by 2026-10-18
- Nimbus Cloud Labs (Cloud Support Engineer), CTC 10.0 LPA, apply by 2026-09-30
```

**7. [student1] What clubs am I part of?**

```
You are part of these clubs:
- Football Club (Sports) — Member
- Sports Club (Sports) — Member
```

**8. [student1] How many OD hours do I have left?**

```
You have used 0 OD hours and have 40 hours remaining out of 40 this semester.
```

**9. [student1] Can I apply for OD tomorrow?**

```
Yes, you can apply for OD tomorrow. You have 40 of 40 OD hours available, your attendance is 87.6% (minimum 75%), and you have no other OD request that day. Requests over 8 hours also need HOD approval.
```

**10. [student1] What is the status of my last OD application?**

```
You have not submitted any OD requests yet.
```

**11. [student1] Why was my last OD application rejected?**

```
None of your OD requests has been rejected.
```

**12. [faculty1] How many OD requests are pending my approval?**

```
You have 4 OD request(s) waiting for your decision:
- #45 Mahesh Raghavan (21CSE1049): Toastmasters & Public Speaking Inter-Club Competition 2026, 28 Oct 2026, 09:00-11:00, 2h
- #68 Devansh Yadav (21CSE1053): Toastmasters & Public Speaking Guest Session 2026, 14 Oct 2026, 17:30-19:30, 2h
- #116 Meera Mukherjee (21CSE1059): Web & App Development Club Bootcamp 2026, 27 Nov 2026, 14:00-16:00, 2h
- #156 Bhavya Bhatt (21CSE1065): CodeChef Campus Chapter Meetup 2026, 09 Dec 2026, 10:00-12:00, 4h
```

**13. [faculty1] How many OD requests have I approved this month?**

```
This month you approved 0 OD request(s), recommended 0 to the HOD, rejected 0 and asked for clarification on 0.
```

**14. [faculty1] How many students do I teach?**

```
You currently teach 1667 unique students across 3 subjects.
```

**15. [faculty1] Which students are below 75% attendance?**

```
Students below the attendance threshold in your classes:
- Data Structures and Algorithms: 814 students below 75%
- Operating Systems: 866 students below 75%
- Software Engineering: 829 students below 75%
Lowest five:
- Vikram Menon (21CSE1532), CSE301: 52.6%
- Devansh Agarwal (21CSE2562), CSE303: 52.6%
- Navya Gupta (21CSE1296), CSE303: 53.3%
- Swathi Iyer (21CSE1456), CSE303: 53.3%
- Neha Rana (21CSE1646), CSE305: 53.3%
```

**16. [faculty1] What subjects do I teach?**

```
You are teaching:
- CSE301: Data Structures and Algorithms (Semester 5, 4 credits)
- CSE303: Operating Systems (Semester 5, 3 credits)
- CSE305: Software Engineering (Semester 5, 3 credits)
```

**17. [admin] Show department-wise OD statistics**

```
Department-wise OD statistics for this term:
- CSE: 3,477 requests, 3,194 approved, 140 rejected, 143 pending; approval rate 95.8%; 9,455.2 hours (14.18% of allowance)
- ECE: 3,515 requests, 3,199 approved, 170 rejected, 146 pending; approval rate 95%; 9,581.6 hours (14.38% of allowance)
- MECH: 3,510 requests, 3,225 approved, 134 rejected, 151 pending; approval rate 96%; 9,748.5 hours (14.62% of allowance)
```

**18. [admin] How many OD requests are pending?**

```
440 OD request(s) are awaiting a decision, 0 of them waiting for the HOD:
- CSE: 143 awaiting a decision (0 with the HOD)
- ECE: 146 awaiting a decision (0 with the HOD)
- MECH: 151 awaiting a decision (0 with the HOD)
```

**19. [admin] Which department has the highest OD utilisation?**

```
MECH has the highest OD utilisation: 14.62% of its allowance (9,748.5 approved hours across 1,667 students, 5.85h per student).
```

**20. [admin] How many students are in CSE?**

```
There are 1667 students in Computer Science and Engineering (CSE).
```

**21. [admin] How many students are placed?**

```
1261 students have been placed so far this year.
```

**22. [admin2] How many OD requests are pending?**

```
143 OD request(s) are awaiting a decision in your department, 0 of them waiting for the HOD:
- CSE: 143 awaiting a decision (0 with the HOD)
```

**23. [admin2] Show department-wise OD statistics**

```
Department-wise OD statistics for this term in your department:
- CSE: 3,477 requests, 3,194 approved, 140 rejected, 143 pending; approval rate 95.8%; 9,455.2 hours (14.18% of allowance)
```

**24. [admin2] Show department-wise OD statistics for all departments**

```
Department-wise OD statistics for this term in your department:
- CSE: 3,477 requests, 3,194 approved, 140 rejected, 143 pending; approval rate 95.8%; 9,455.2 hours (14.18% of allowance)
```

**25. [student1] Why was my last OD application rejected?**

```
Your most recent rejected OD request is #10503 "Battery Rejected Event" (19 Oct 2026, 09:00-12:00). It was rejected on 01 Oct 2026. Reason: Event is not recognised by the department.
```

**26. [student1] How many OD hours do I have left?**

```
You have used 3 OD hours and have 37 hours remaining out of 40 this semester. 3 more hours are in requests awaiting a decision, so 34 hours are available for a new request.
```

**27. [student1] What is the status of my last OD application?**

```
Your latest OD request is #10505 "Battery Pending Event" (21 Oct 2026, 09:00-12:00, 3h). Status: Under faculty review. It is with your class advisor, Dr. Anand Subramaniam.
```

**28. [student1] Can I apply for OD on 2026-10-20?**

```
You already have an OD request on Tuesday, 20 Oct 2026: Overlaps your request #10504 "Battery Approved Event" (20 Oct 2026 09:00 to 20 Oct 2026 12:00, Approved). You can still apply for hours that do not overlap it; you have 34 OD hours available.
```

**29. [faculty1] How many OD requests are pending my approval?**

```
You have 5 OD request(s) waiting for your decision:
- #45 Mahesh Raghavan (21CSE1049): Toastmasters & Public Speaking Inter-Club Competition 2026, 28 Oct 2026, 09:00-11:00, 2h
- #68 Devansh Yadav (21CSE1053): Toastmasters & Public Speaking Guest Session 2026, 14 Oct 2026, 17:30-19:30, 2h
- #116 Meera Mukherjee (21CSE1059): Web & App Development Club Bootcamp 2026, 27 Nov 2026, 14:00-16:00, 2h
- #156 Bhavya Bhatt (21CSE1065): CodeChef Campus Chapter Meetup 2026, 09 Dec 2026, 10:00-12:00, 4h
- #10505 Manish Kumar (21CSE1042): Battery Pending Event, 21 Oct 2026, 09:00-12:00, 3h
```

**30. [faculty1] How many OD requests have I approved this month?**

```
This month you approved 1 OD request(s), recommended 0 to the HOD, rejected 1 and asked for clarification on 0.
```

**31. [admin] How many OD requests are pending?**

```
441 OD request(s) are awaiting a decision, 0 of them waiting for the HOD:
- CSE: 144 awaiting a decision (0 with the HOD)
- ECE: 146 awaiting a decision (0 with the HOD)
- MECH: 151 awaiting a decision (0 with the HOD)
```
