"""
Seeds the SQLite database with realistic, internally-connected demo data.
Run with: python -m app.seed
"""
import random
from datetime import date, timedelta, datetime

from .database import Base, engine, SessionLocal
from . import models
from .auth import hash_password

random.seed(42)


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


FIRST_NAMES = [
    "Aarav", "Vihaan", "Ishaan", "Kabir", "Rohan", "Aditi", "Priya", "Sneha",
    "Ananya", "Diya", "Karthik", "Meera", "Sanjay", "Divya", "Arjun", "Neha",
    "Rahul", "Pooja", "Vikram", "Lakshmi", "Aryan", "Advait", "Reyansh", "Sai",
    "Krishna", "Aditya", "Vivaan", "Atharv", "Dhruv", "Yash", "Ayaan", "Devansh",
    "Riya", "Saanvi", "Aadhya", "Myra", "Anika", "Ira", "Kavya", "Tanvi",
    "Sanya", "Ishita", "Navya", "Pari", "Zara", "Amaira", "Anaya", "Siya",
    "Rehan", "Farhan", "Zoya", "Imran", "Ayesha", "Kiran", "Nikhil", "Varun",
    "Harsha", "Gowtham", "Deepika", "Swathi", "Ramesh", "Suresh", "Ganesh", "Mahesh",
    "Lavanya", "Pranav", "Om", "Sarthak", "Manasa", "Bhavya", "Nithin", "Yogesh",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Menon", "Rao", "Verma",
    "Pillai", "Krishnan", "Desai", "Kapoor", "Chatterjee", "Naidu", "Bose", "Mukherjee",
    "Joshi", "Shah", "Agarwal", "Bhat", "Pandey", "Mishra", "Chauhan", "Malhotra",
    "Kulkarni", "Deshmukh", "Patil", "Rana", "Thakur", "Yadav", "Chopra", "Bhatt",
    "Ranganathan", "Subramaniam", "Venkatesh", "Balasubramanian", "Raghavan", "Padmanabhan",
    "Sundaram", "Natarajan", "Krishnamurthy", "Ramamoorthy", "Varadarajan", "Seshadri",
]


def rand_name(used):
    """
    Returns a random full name. Prefers a name not already used, but - unlike a
    hard uniqueness requirement - never blocks: with ~3,000 first/last combinations
    and 5,000+ students, some repeated names are inevitable and realistic (real
    universities absolutely have students who share a name, distinguished by
    register number). We try a bounded number of times to avoid an obvious repeat,
    then just accept one rather than looping forever.
    """
    for _ in range(20):
        n = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if n not in used:
            used.add(n)
            return n
    # Pool is saturated - accept a repeat rather than looping indefinitely.
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def run():
    reset_db()
    db = SessionLocal()
    used_names = set()
    student_password_hash = hash_password("student123")
    faculty_password_hash = hash_password("faculty123")
    admin_password_hash = hash_password("admin123")

    # ---------------- Departments ----------------
    dept_defs = [("Computer Science and Engineering", "CSE"),
                 ("Electronics and Communication Engineering", "ECE"),
                 ("Mechanical Engineering", "MECH")]
    departments = []
    for name, code in dept_defs:
        d = models.Department(name=name, code=code)
        db.add(d)
        departments.append(d)
    db.commit()

    dept_cse, dept_ece, dept_mech = departments

    # ---------------- Courses ----------------
    course_cse = models.Course(name="B.Tech Computer Science and Engineering", department_id=dept_cse.id)
    course_ece = models.Course(name="B.Tech Electronics and Communication Engineering", department_id=dept_ece.id)
    course_mech = models.Course(name="B.Tech Mechanical Engineering", department_id=dept_mech.id)
    db.add_all([course_cse, course_ece, course_mech])
    db.commit()

    # ---------------- Admins (25) ----------------
    admin_names = [
        "Dr. Ramesh Venkataraman", "Dr. Priya Narayanan", "Dr. Arvind Krishnan",
        "Dr. Meera Srinivasan", "Dr. Sandeep Raj", "Dr. Nithya Balaji",
        "Dr. Karthik Raman", "Dr. Anjali Menon", "Dr. Vivek Subramanian",
        "Dr. Deepa Kumar", "Dr. Hari Prasad", "Dr. Shalini Rao",
        "Dr. Mohan Das", "Dr. Rekha Iyer", "Dr. Ashwin Nair",
        "Dr. Swetha Pillai", "Dr. Naveen Reddy", "Dr. Divya Shah",
        "Dr. Prakash Menon", "Dr. Lakshmi Anand", "Dr. Gokul Raj",
        "Dr. Asha Varma", "Dr. Rohit Kumar", "Dr. Sneha Joseph", "Dr. Ajay Rao"
    ]
    admin_users = []
    for i, name in enumerate(admin_names, start=1):
        username = "admin" if i == 1 else f"admin{i}"
        u = models.User(username=username, password_hash=admin_password_hash,
                        role="admin", full_name=name, email=f"{username}@campusone.edu")
        db.add(u)
        admin_users.append(u)
    db.commit()

    # ---------------- Faculty (1,000) ----------------
    faculty_defs = [
        ("faculty1", "Dr. Anand Subramaniam", dept_cse, "Associate Professor", "AB1-405"),
        ("faculty2", "Dr. Kavitha Raman", dept_cse, "Assistant Professor", "AB1-312"),
        ("faculty3", "Dr. Suresh Kumar", dept_ece, "Professor", "AB2-201"),
        ("faculty4", "Dr. Meenakshi Pillai", dept_ece, "Assistant Professor", "AB2-210"),
        ("faculty5", "Dr. Vijay Anand", dept_mech, "Associate Professor", "AB3-101"),
    ]
    faculty_list = []
    for i in range(1, 1001):
        if i <= len(faculty_defs):
            uname, fname, dept, desig, office = faculty_defs[i - 1]
        else:
            dept = [dept_cse, dept_ece, dept_mech][(i-1)%3]
            uname = f"faculty{i}"
            fname = f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            desig = random.choice(["Assistant Professor", "Associate Professor", "Professor", "Lecturer"])
            office = f"AB{1 + ((i-1) % 3)}-{200 + ((i * 7) % 250)}"
        u = models.User(username=uname, password_hash=faculty_password_hash,
                        role="faculty", full_name=fname, email=f"{uname}@campusone.edu")
        db.add(u)
        db.flush()
        f = models.Faculty(user_id=u.id, employee_code=f"EMP{1000+i}",
                           department_id=dept.id, designation=desig, office=office)
        db.add(f)
        faculty_list.append(f)
    db.commit()

    fac_anand, fac_kavitha, fac_suresh, fac_meenakshi, fac_vijay = faculty_list[:5]

    # ---------------- Subjects ----------------
    subject_defs = [
        ("CSE301", "Data Structures and Algorithms", 5, 4, course_cse, fac_anand),
        ("CSE302", "Database Management Systems", 5, 4, course_cse, fac_kavitha),
        ("CSE303", "Operating Systems", 5, 3, course_cse, fac_anand),
        ("CSE304", "Computer Networks", 5, 3, course_cse, fac_kavitha),
        ("CSE305", "Software Engineering", 5, 3, course_cse, fac_anand),
        ("ECE301", "Digital Signal Processing", 5, 4, course_ece, fac_suresh),
        ("ECE302", "VLSI Design", 5, 4, course_ece, fac_meenakshi),
        ("ECE303", "Microprocessors and Microcontrollers", 5, 3, course_ece, fac_suresh),
        ("MECH301", "Thermodynamics", 5, 4, course_mech, fac_vijay),
        ("MECH302", "Fluid Mechanics", 5, 3, course_mech, fac_vijay),
    ]
    subjects = []
    for code, name, sem, credits, course, fac in subject_defs:
        s = models.Subject(code=code, name=name, semester=sem, credits=credits,
                            course_id=course.id, faculty_id=fac.id)
        db.add(s)
        subjects.append(s)
    db.commit()

    subj_by_dept = {
        dept_cse.id: [s for s in subjects if s.code.startswith("CSE")],
        dept_ece.id: [s for s in subjects if s.code.startswith("ECE")],
        dept_mech.id: [s for s in subjects if s.code.startswith("MECH")],
    }

    # ---------------- Hostel inventory ----------------
    hostels = []
    for i in range(1, 13):
        h = models.Hostel(
            name=f"Campus Hostel {i}",
            block=f"Block {chr(64+i)}",
            room_type=random.choice(["Single", "Double", "Triple", "Four Sharing"]),
            address=f"North Campus Residential Zone - Block {chr(64+i)}",
            capacity=random.choice([240, 300, 360, 420]),
        )
        db.add(h)
        hostels.append(h)
    db.commit()

    # ---------------- Students ----------------
    # student1 is the flagship demo account; rest are class roster for realistic analytics
    dept_cycle = [dept_cse, dept_ece, dept_mech]
    students = []

    demo_student_user = models.User(username="student1", password_hash=student_password_hash,
                                     role="student", full_name="Manish Kumar", email="student1@campusone.edu")
    db.add(demo_student_user)
    db.commit()
    demo_student = models.Student(user_id=demo_student_user.id, register_number="21CSE1042",
                                   department_id=dept_cse.id, year=3, semester=5, cgpa=8.42,
                                   accommodation_type="Hosteller")
    db.add(demo_student)
    db.commit()
    students.append(demo_student)
    used_names.add("Manish Kumar")

    # Per-department sequential register-number counters. The CSE counter starts one
    # above 1042 because that value is already taken by the hardcoded demo account -
    # this makes uniqueness guaranteed by construction instead of by coincidence.
    dept_reg_seq = {dept_cse.id: 1042, dept_ece.id: 1000, dept_mech.id: 1000}

    for i in range(2, 5001):  # student2..student5000
        dept = dept_cycle[i % 3]
        code_prefix = dept.code
        uname = f"student{i}"
        fname = rand_name(used_names)
        u = models.User(username=uname, password_hash=student_password_hash,
                         role="student", full_name=fname, email=f"{uname}@campusone.edu")
        db.add(u)
        db.flush()
        dept_reg_seq[dept.id] += 1
        reg = f"21{code_prefix}{dept_reg_seq[dept.id]}"
        # ~55% of students live on campus - a realistic hosteller/day-scholar split
        # for a university that draws students from both the home city and elsewhere.
        accommodation = "Hosteller" if random.random() < 0.55 else "Day Scholar"
        st = models.Student(user_id=u.id, register_number=reg, department_id=dept.id,
                             year=3, semester=5, cgpa=round(random.uniform(6.2, 9.4), 2),
                             accommodation_type=accommodation)
        db.add(st)
        if i % 500 == 0:
            db.flush()
        students.append(st)

    db.commit()

    # ---------------- Attendance ----------------
    for st in students:
        dept_subjects = subj_by_dept[st.department_id]
        for subj in dept_subjects:
            total = random.randint(38, 46)
            if st.id == demo_student.id:
                pct = random.uniform(0.72, 0.94)
            else:
                pct = random.uniform(0.55, 0.98)
            attended = int(total * pct)
            db.add(models.Attendance(student_id=st.id, subject_id=subj.id,
                                      total_classes=total, attended_classes=attended))
    db.commit()

    # ---------------- Marks ----------------
    def grade_from_total(total_100):
        if total_100 >= 90: return "S"
        if total_100 >= 80: return "A"
        if total_100 >= 70: return "B"
        if total_100 >= 60: return "C"
        if total_100 >= 50: return "D"
        if total_100 >= 40: return "E"
        return "F"

    for st in students:
        dept_subjects = subj_by_dept[st.department_id]
        for subj in dept_subjects:
            base = random.uniform(0.55, 0.95) if st.id != demo_student.id else random.uniform(0.72, 0.9)
            i1 = round(base * 25 + random.uniform(-3, 3), 1)
            i2 = round(base * 25 + random.uniform(-3, 3), 1)
            asg = round(base * 10 + random.uniform(-1, 1), 1)
            ext = round(base * 40 + random.uniform(-5, 5), 1)
            i1, i2, asg, ext = [max(0, v) for v in (i1, i2, asg, ext)]
            total = i1 + i2 + asg + ext
            grade = grade_from_total(total)
            gp = {"S": 10, "A": 9, "B": 8, "C": 7, "D": 6, "E": 5, "F": 0}[grade]
            db.add(models.Mark(student_id=st.id, subject_id=subj.id, internal_1=i1, internal_2=i2,
                                assignment=asg, external=ext, grade=grade, sgpa_contribution=gp))
    db.commit()

    # ---------------- Exams ----------------
    today = date.today()
    for subj in subjects:
        db.add(models.Exam(subject_id=subj.id, exam_type="Internal Assessment 2",
                            exam_date=today + timedelta(days=random.randint(3, 12)),
                            start_time="09:30", end_time="11:00", venue=f"Exam Hall {random.randint(1,6)}"))
        db.add(models.Exam(subject_id=subj.id, exam_type="Semester End Examination",
                            exam_date=today + timedelta(days=random.randint(35, 55)),
                            start_time="10:00", end_time="13:00", venue=f"Exam Hall {random.randint(1,6)}"))
    db.commit()

    # ---------------- Timetable ----------------
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    slots = [("08:50", "09:40"), ("09:40", "10:30"), ("10:50", "11:40"),
             ("11:40", "12:30"), ("13:30", "14:20"), ("14:20", "15:10")]
    for dept_id, dept_subjects in subj_by_dept.items():
        slot_pool = [(d, s) for d in days for s in slots]
        random.shuffle(slot_pool)
        used_slots = set()
        for subj in dept_subjects:
            for _ in range(2):  # 2 sessions/week per subject
                while True:
                    day, (st_t, en_t) = slot_pool.pop()
                    key = (day, st_t)
                    if key not in used_slots:
                        used_slots.add(key)
                        break
                db.add(models.TimetableSlot(subject_id=subj.id, day_of_week=day,
                                             start_time=st_t, end_time=en_t,
                                             room=f"Room {random.randint(200,499)}"))
    db.commit()

    # ---------------- Fees ----------------
    for st in students:
        total = 125000.0
        paid = total if st.id != demo_student.id and random.random() > 0.3 else random.choice([total, total * 0.5, 0])
        status = "Paid" if paid >= total else ("Partially Paid" if paid > 0 else "Pending")
        db.add(models.Fee(student_id=st.id, semester=st.semester, total_amount=total,
                           paid_amount=paid, due_date=today + timedelta(days=20), status=status))
    db.commit()

    # ---------------- Library ----------------
    # A meaningful slice of the student body has borrowing history - not just a
    # fixed handful - so library stats are actually representative at 5,000+ students.
    books = ["Introduction to Algorithms", "Clean Code", "Computer Networking: A Top-Down Approach",
             "Operating System Concepts", "Digital Design", "Fluid Mechanics and Hydraulics",
             "Database System Concepts", "Software Engineering: A Practitioner's Approach",
             "Artificial Intelligence: A Modern Approach", "Compilers: Principles, Techniques and Tools",
             "Discrete Mathematics and Its Applications", "Design Patterns", "The Pragmatic Programmer",
             "Computer Organization and Design", "Linear Algebra and Its Applications"]
    library_borrowers = [demo_student] + random.sample(
        [s for s in students if s.id != demo_student.id], k=int(len(students) * 0.22)
    )
    library_rows = []
    for st in library_borrowers:
        for _ in range(random.choices([1, 2, 3], weights=[60, 30, 10])[0]):
            book = random.choice(books)
            issue = today - timedelta(days=random.randint(2, 45))
            due = issue + timedelta(days=14)
            returned = random.random() > 0.45
            library_rows.append(models.LibraryRecord(
                student_id=st.id, book_title=book, issue_date=issue,
                due_date=due, return_date=(due - timedelta(days=random.randint(0, 5))) if returned else None,
                status="Returned" if returned else ("Overdue" if due < today else "Issued"),
            ))
    db.bulk_save_objects(library_rows)
    db.commit()

    # ---------------- Announcements ----------------
    announcements = [
        ("Odd Semester Internal Assessment 2 Schedule Released", "Internal Assessment 2 for all departments will be held from next week. Check the exam timetable module for subject-wise dates and venues.", "student"),
        ("Placement Drive: TechNova Solutions", "TechNova Solutions will be visiting campus for a placement drive. Eligible students can apply through the Placement Portal.", "student"),
        ("Faculty Development Program on AI in Education", "All faculty members are invited to a two-day FDP on integrating AI tools in teaching, organized by the Center for Academic Excellence.", "faculty"),
        ("Library Fine Waiver Week", "Students can return overdue books without fine penalties during this week only.", "student"),
        ("Fee Payment Deadline Reminder", "Students who have not cleared their semester fees are requested to do so before the due date to avoid late fee charges.", "student"),
    ]
    for title, body, aud in announcements:
        db.add(models.Announcement(title=title, body=body, audience=aud,
                                    posted_on=datetime.utcnow() - timedelta(days=random.randint(0, 10))))
    db.commit()

    # ---------------- Events ----------------
    events = [
        ("TechFest 2026 - Annual Technical Symposium", "A three-day technical symposium featuring hackathons, project expos, and guest lectures from industry leaders.", 18),
        ("Inter-Department Sports Meet", "Annual sports meet with events across athletics, football, basketball, and cricket.", 25),
        ("Guest Lecture: Careers in AI and Machine Learning", "Industry expert session on career paths in AI/ML, hosted by the CSE department.", 9),
        ("Cultural Fest - Rhythms 2026", "College-wide cultural festival with music, dance, and drama competitions.", 40),
    ]
    for title, desc, days_ahead in events:
        db.add(models.Event(title=title, description=desc, event_date=today + timedelta(days=days_ahead),
                             venue="Main Auditorium"))
    db.commit()

    # ---------------- Student Life: Clubs, events, participation & OD ----------------
    club_defs = [
        ("CodeChef Campus Chapter", "Technical", "Competitive programming, coding contests and peer learning."),
        ("AI & Robotics Club", "Technical", "Hands-on AI, robotics and automation projects."),
        ("Web & App Development Club", "Technical", "Build modern web and mobile applications."),
        ("Cyber Security Club", "Technical", "Security workshops, CTFs and ethical hacking awareness."),
        ("IoT Innovation Club", "Technical", "Connected devices, embedded systems and smart-campus ideas."),
        ("Entrepreneurship Cell", "Professional", "Startup ideation, founder talks and pitch competitions."),
        ("Finance & Investment Club", "Professional", "Financial literacy, markets and investment simulations."),
        ("Toastmasters & Public Speaking", "Professional", "Communication, leadership and public speaking practice."),
        ("Design & Creative Club", "Creative", "UI/UX, graphic design, illustration and creative workshops."),
        ("Photography Club", "Creative", "Photography walks, exhibitions and campus storytelling."),
        ("Film & Media Club", "Creative", "Short films, editing, screenings and media production."),
        ("Music Club", "Cultural", "Vocal and instrumental music practice and performances."),
        ("Dance Club", "Cultural", "Contemporary, classical and western dance activities."),
        ("Dramatics Club", "Cultural", "Stage plays, improv and theatre workshops."),
        ("Literary Club", "Cultural", "Debates, creative writing, quizzes and literary events."),
        ("Quiz Club", "Academic", "Inter-college and campus quiz competitions."),
        ("Eco Club", "Social", "Sustainability, tree planting and environmental campaigns."),
        ("NSS Student Volunteers", "Social", "Community outreach and volunteering initiatives."),
        ("Sports Club", "Sports", "Campus sports leagues, fitness and recreation."),
        ("Football Club", "Sports", "Football training, tournaments and fan activities."),
        ("Basketball Club", "Sports", "Basketball practice, leagues and coaching."),
        ("Badminton Club", "Sports", "Badminton practice and inter-department tournaments."),
        ("Chess Club", "Sports", "Chess coaching, ladders and tournaments."),
        ("Table Tennis Club", "Sports", "Table tennis practice and competitive matches."),
        ("Coding for Social Good", "Social", "Technology projects solving community problems."),
        ("Google Developer Student Community", "Technical", "Developer talks, study jams and community projects."),
        ("Open Source Club", "Technical", "Open-source contribution and Git collaboration."),
        ("Astronomy Club", "Academic", "Stargazing, astronomy talks and science outreach."),
        ("Math & Data Science Club", "Academic", "Problem solving, analytics and applied mathematics."),
        ("Campus Wellness Club", "Wellness", "Peer activities around wellbeing, mindfulness and healthy habits."),
    ]
    clubs = []
    for i, (name, category, desc) in enumerate(club_defs):
        c = models.Club(name=name, category=category, description=desc,
                        faculty_coordinator_id=faculty_list[(i * 31) % len(faculty_list)].id,
                        meeting_day=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][i % 5],
                        meeting_time=["16:00", "16:30", "17:00", "17:30"][i % 4])
        db.add(c)
        clubs.append(c)
    db.commit()

    # Every student joins 1-4 clubs; membership is department/year independent and deterministic.
    memberships = []
    for idx, st in enumerate(students):
        count = random.choices([1, 2, 3, 4], weights=[20, 45, 25, 10])[0]
        selected = random.sample(clubs, count)
        for j, club in enumerate(selected):
            memberships.append(models.ClubMembership(
                student_id=st.id, club_id=club.id,
                joined_on=today - timedelta(days=random.randint(20, 500)),
                role=random.choices(["Member", "Core Member", "Secretary", "Event Lead"], [75, 17, 5, 3])[0]
            ))
    db.bulk_save_objects(memberships)
    db.commit()

    # Generate multiple past and upcoming events per club.
    club_events = []
    event_titles = [
        "Workshop", "Meetup", "Bootcamp", "Campus Challenge", "Guest Session",
        "Inter-Club Competition", "Community Drive", "Open Mic", "Showcase", "Training Day"
    ]
    for ci, club in enumerate(clubs):
        for k in range(12):
            offset = (k - 5) * 14 + (ci % 7)
            event_date = today + timedelta(days=offset)
            ev = models.ClubEvent(
                club_id=club.id,
                title=f"{club.name} {event_titles[(ci+k) % len(event_titles)]} {2026 + (1 if event_date.year > 2026 else 0)}",
                description=f"Student-led {club.category.lower()} activity hosted by {club.name}.",
                event_date=event_date,
                start_time=["09:00", "10:00", "14:00", "16:00", "17:30"][(ci+k) % 5],
                end_time=["11:00", "12:00", "16:00", "18:00", "19:30"][(ci+k) % 5],
                venue=["Innovation Hub", "Main Auditorium", "Seminar Hall 1", "Sports Complex", "Student Activity Centre"][(ci+k) % 5],
                registration_required=True,
                max_volunteers=random.randint(10, 40)
            )
            db.add(ev)
            club_events.append(ev)
    db.commit()

    # Create event attendance/volunteering only for events tied to clubs the student belongs to.
    membership_map = {}
    for mem in memberships:
        membership_map.setdefault(mem.student_id, []).append(mem.club_id)

    event_by_club = {}
    for ev in club_events:
        event_by_club.setdefault(ev.club_id, []).append(ev)

    attend_rows, volunteer_rows = [], []
    for st in students:
        for club_id in membership_map.get(st.id, []):
            evs = event_by_club[club_id]
            past = [e for e in evs if e.event_date <= today]
            for ev in random.sample(past, k=min(len(past), random.randint(2, 6))):
                attend_rows.append(models.EventAttendance(
                    student_id=st.id, event_id=ev.id,
                    attended_on=datetime.combine(ev.event_date, datetime.min.time())
                ))
            # 0-3 volunteering records, weighted toward confirmed/completed.
            if random.random() < 0.65:
                candidates = past + [e for e in evs if e.event_date > today][:2]
                for ev in random.sample(candidates, k=min(len(candidates), random.randint(1, 3))):
                    volunteer_rows.append(models.EventVolunteer(
                        student_id=st.id, event_id=ev.id,
                        responsibility=random.choice(["Registration Desk", "Logistics", "Technical Support", "Hospitality", "Media"]),
                        hours=random.choice([2, 3, 4, 5, 6]),
                        status=random.choice(["Completed", "Completed", "Confirmed"])
                    ))
    db.bulk_save_objects(attend_rows)
    db.bulk_save_objects(volunteer_rows)
    db.commit()

    # OD entitlement and requests. Entitlement is derived from the student's semester.
    # Grouped lookups instead of per-student full-table scans - O(n) not O(n^2) at 5,000 students.
    volunteer_by_student = {}
    for v in volunteer_rows:
        volunteer_by_student.setdefault(v.student_id, []).append(v)
    event_by_id = {e.id: e for e in club_events}

    future_club_events = [e for e in club_events if e.event_date > today]

    od_rows = []
    for st in students:
        my_volunteering = volunteer_by_student.get(st.id, [])
        volunteer_hours = sum(v.hours for v in my_volunteering if v.status in ("Completed", "Confirmed"))
        used_target = min(40.0, round(volunteer_hours * random.uniform(0.35, 0.85), 1))

        # Store the used amount as approved OD requests, tied to the events this
        # student actually volunteered for (real connection, not an arbitrary event).
        if used_target > 0 and my_volunteering:
            left = used_target
            source_events = random.sample(my_volunteering, k=min(3, len(my_volunteering)))
            for v in source_events:
                if left <= 0:
                    break
                hours = min(left, random.choice([2, 3, 4, 5]))
                ev = event_by_id[v.event_id]
                od_rows.append(models.ODRequest(
                    student_id=st.id, event_id=v.event_id, requested_hours=hours,
                    approved_hours=hours,
                    request_date=datetime.combine(ev.event_date, datetime.min.time()) - timedelta(days=5),
                    status="Approved", reason="Club event participation / volunteering",
                ))
                left = round(left - hours, 1)

        if future_club_events and random.random() < 0.18:
            ev = random.choice(future_club_events)
            od_rows.append(models.ODRequest(
                student_id=st.id, event_id=ev.id, requested_hours=random.choice([2, 3, 4]),
                approved_hours=0, request_date=datetime.utcnow(),
                status=random.choice(["Pending", "Rejected"]),
                reason="Request for upcoming student activity",
            ))
    db.bulk_save_objects(od_rows)
    db.commit()

    # Hostel allocations for hostellers only.
    hosteller_students = [st for st in students if st.accommodation_type == "Hosteller"]
    allocations = []
    for idx, st in enumerate(hosteller_students):
        h = hostels[idx % len(hostels)]
        room = 100 + ((idx // 4) % 90)
        bed = str((idx % 4) + 1)
        allocations.append(models.HostelAllocation(
            student_id=st.id, hostel_id=h.id, room_number=str(room),
            bed_number=bed, academic_year="2026-27"
        ))
    db.bulk_save_objects(allocations)
    db.commit()

    # ---------------- Placement: Companies & Drives ----------------
    companies = [
        ("TechNova Solutions", "Software Engineer", 12.5, 7.5, "CSE,ECE",
         "A fast-growing product company building cloud-native SaaS platforms."),
        ("Quantum Analytics", "Data Analyst", 9.0, 7.0, "CSE,ECE,MECH",
         "Analytics and business intelligence consultancy serving global clients."),
        ("NextGen Semiconductors", "VLSI Design Engineer", 14.0, 7.8, "ECE",
         "Semiconductor design house specializing in low-power chip design."),
        ("Infinite Systems", "Full Stack Developer", 8.5, 6.5, "CSE",
         "Enterprise software services company with a strong campus hiring program."),
        ("Meridian Auto Works", "Design Engineer", 7.5, 6.5, "MECH",
         "Automotive component manufacturer with an in-house R&D division."),
        ("Nimbus Cloud Labs", "Cloud Support Engineer", 10.0, 7.0, "CSE,ECE",
         "Cloud infrastructure and DevOps services provider."),
    ]
    company_objs = []
    for name, role, ctc, min_cgpa, depts, desc in companies:
        c = models.Company(name=name, role=role, ctc_lpa=ctc, min_cgpa=min_cgpa,
                            eligible_departments=depts, description=desc)
        db.add(c)
        company_objs.append(c)
    db.commit()

    drives = []
    for i, c in enumerate(company_objs):
        drive_date = today + timedelta(days=random.randint(10, 45))
        deadline = drive_date - timedelta(days=5)
        status = "Open" if deadline > today else "Closed"
        d = models.PlacementDrive(company_id=c.id, drive_date=drive_date,
                                   application_deadline=deadline, status=status)
        db.add(d)
        drives.append(d)
    db.commit()

    # ---------------- Applications ----------------
    for st in students:
        dept_code = departments[0].code if st.department_id == dept_cse.id else (
            departments[1].code if st.department_id == dept_ece.id else departments[2].code)
        for d in drives:
            comp = d.company
            eligible_depts = comp.eligible_departments.split(",")
            if dept_code in eligible_depts and st.cgpa >= comp.min_cgpa and random.random() > 0.4:
                status = random.choice(["Applied", "Shortlisted", "Interview", "Offered", "Rejected"])
                db.add(models.Application(student_id=st.id, drive_id=d.id, status=status,
                                           applied_on=datetime.utcnow() - timedelta(days=random.randint(1, 15))))
    db.commit()

    db.close()

    # Institution policy, class advisors, department heads and OD workflow columns.
    from .od_bootstrap import ensure_od_foundation
    with engine.begin() as conn:
        ensure_od_foundation(conn)

    print("Database seeded successfully.")
    print("Demo accounts:")
    print("  Admin:   admin / admin123")
    print("  Faculty: faculty1 / faculty123  (Dr. Anand Subramaniam, CSE)")
    print("  Student: student1 / student123  (Manish Kumar, 21CSE1042)")


if __name__ == "__main__":
    # Seeding DROPS every table first. Refuse to do that to a database that
    # already holds data unless it is asked for explicitly, and never in production.
    import sys
    from sqlalchemy import inspect, text
    from . import config

    if config.IS_PRODUCTION:
        sys.exit("Refusing to seed: APP_ENV=production.")
    has_users = False
    if "users" in inspect(engine).get_table_names():
        with engine.connect() as _conn:
            has_users = bool(_conn.execute(text("select count(*) from users")).scalar())
    if has_users and "--force-reset" not in sys.argv:
        sys.exit("This database already contains data. Seeding would DELETE all of it. "
                 "Back it up first, then re-run with:  python -m app.seed --force-reset")
    run()
