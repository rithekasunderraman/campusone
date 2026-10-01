from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, Date, DateTime, Text, Boolean,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # student | faculty | admin
    full_name = Column(String, nullable=False)
    email = Column(String)

    student_profile = relationship("Student", back_populates="user", uselist=False)
    faculty_profile = relationship("Faculty", back_populates="user", uselist=False)


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False)

    students = relationship("Student", back_populates="department")
    faculty = relationship("Faculty", back_populates="department")
    courses = relationship("Course", back_populates="department")


class Faculty(Base):
    __tablename__ = "faculty"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    employee_code = Column(String, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    designation = Column(String)
    office = Column(String)

    user = relationship("User", back_populates="faculty_profile")
    department = relationship("Department", back_populates="faculty")
    subjects = relationship("Subject", back_populates="faculty")


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    register_number = Column(String, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    year = Column(Integer)
    semester = Column(Integer)
    cgpa = Column(Float, default=0.0)
    accommodation_type = Column(String, nullable=False, default="Day Scholar")  # Day Scholar / Hosteller

    user = relationship("User", back_populates="student_profile")
    department = relationship("Department", back_populates="students")
    attendance_records = relationship("Attendance", back_populates="student")
    marks = relationship("Mark", back_populates="student")
    fees = relationship("Fee", back_populates="student")
    library_records = relationship("LibraryRecord", back_populates="student")
    applications = relationship("Application", back_populates="student")
    hostel = relationship("HostelAllocation", back_populates="student", uselist=False)
    club_memberships = relationship("ClubMembership", back_populates="student")
    event_attendance = relationship("EventAttendance", back_populates="student")
    event_volunteering = relationship("EventVolunteer", back_populates="student")
    od_requests = relationship("ODRequest", back_populates="student")


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # e.g. B.Tech CSE
    department_id = Column(Integer, ForeignKey("departments.id"))

    department = relationship("Department", back_populates="courses")
    subjects = relationship("Subject", back_populates="course")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    semester = Column(Integer)
    credits = Column(Integer, default=3)
    course_id = Column(Integer, ForeignKey("courses.id"))
    faculty_id = Column(Integer, ForeignKey("faculty.id"))

    course = relationship("Course", back_populates="subjects")
    faculty = relationship("Faculty", back_populates="subjects")
    attendance_records = relationship("Attendance", back_populates="subject")
    marks = relationship("Mark", back_populates="subject")
    exams = relationship("Exam", back_populates="subject")
    timetable_slots = relationship("TimetableSlot", back_populates="subject")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    total_classes = Column(Integer, default=0)
    attended_classes = Column(Integer, default=0)

    student = relationship("Student", back_populates="attendance_records")
    subject = relationship("Subject", back_populates="attendance_records")


class Mark(Base):
    __tablename__ = "marks"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    internal_1 = Column(Float, default=0)
    internal_2 = Column(Float, default=0)
    assignment = Column(Float, default=0)
    external = Column(Float, default=0)
    grade = Column(String, default="-")
    sgpa_contribution = Column(Float, default=0)

    student = relationship("Student", back_populates="marks")
    subject = relationship("Subject", back_populates="marks")


class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    exam_type = Column(String)  # Internal 1 / Internal 2 / Semester
    exam_date = Column(Date)
    start_time = Column(String)
    end_time = Column(String)
    venue = Column(String)

    subject = relationship("Subject", back_populates="exams")


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    day_of_week = Column(String)  # Monday..Saturday
    start_time = Column(String)
    end_time = Column(String)
    room = Column(String)

    subject = relationship("Subject", back_populates="timetable_slots")


class Fee(Base):
    __tablename__ = "fees"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    semester = Column(Integer)
    total_amount = Column(Float)
    paid_amount = Column(Float, default=0)
    due_date = Column(Date)
    status = Column(String, default="Pending")

    student = relationship("Student", back_populates="fees")


class LibraryRecord(Base):
    __tablename__ = "library_records"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    book_title = Column(String)
    issue_date = Column(Date)
    due_date = Column(Date)
    return_date = Column(Date, nullable=True)
    status = Column(String, default="Issued")

    student = relationship("Student", back_populates="library_records")


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    body = Column(Text)
    audience = Column(String, default="all")  # all|student|faculty
    posted_on = Column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    event_date = Column(Date)
    venue = Column(String)


class Hostel(Base):
    __tablename__ = "hostels"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    block = Column(String, nullable=False)
    room_type = Column(String, nullable=False)  # Single / Double / Triple / Four Sharing
    address = Column(String)
    capacity = Column(Integer, default=0)

    allocations = relationship("HostelAllocation", back_populates="hostel")


class HostelAllocation(Base):
    __tablename__ = "hostel_allocations"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), unique=True, nullable=False)
    hostel_id = Column(Integer, ForeignKey("hostels.id"), nullable=False)
    room_number = Column(String, nullable=False)
    bed_number = Column(String)
    academic_year = Column(String, nullable=False)

    student = relationship("Student", back_populates="hostel")
    hostel = relationship("Hostel", back_populates="allocations")


class Club(Base):
    __tablename__ = "clubs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)
    description = Column(Text)
    faculty_coordinator_id = Column(Integer, ForeignKey("faculty.id"))
    meeting_day = Column(String)
    meeting_time = Column(String)

    faculty_coordinator = relationship("Faculty", foreign_keys=[faculty_coordinator_id])
    memberships = relationship("ClubMembership", back_populates="club")
    events = relationship("ClubEvent", back_populates="club")


class ClubMembership(Base):
    __tablename__ = "club_memberships"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    joined_on = Column(Date, nullable=False)
    role = Column(String, default="Member")

    __table_args__ = (
        UniqueConstraint("student_id", "club_id", name="uq_student_club"),
        Index("ix_club_memberships_student", "student_id"),
        Index("ix_club_memberships_club", "club_id"),
    )

    student = relationship("Student", back_populates="club_memberships")
    club = relationship("Club", back_populates="memberships")


class ClubEvent(Base):
    __tablename__ = "club_events"
    id = Column(Integer, primary_key=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    event_date = Column(Date, nullable=False)
    start_time = Column(String)
    end_time = Column(String)
    venue = Column(String)
    registration_required = Column(Boolean, default=True)
    max_volunteers = Column(Integer, default=20)

    club = relationship("Club", back_populates="events")

    __table_args__ = (
        Index("ix_club_events_club_date", "club_id", "event_date"),
        Index("ix_club_events_date", "event_date"),
    )
    attendance = relationship("EventAttendance", back_populates="event")
    volunteers = relationship("EventVolunteer", back_populates="event")


class EventAttendance(Base):
    __tablename__ = "event_attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("club_events.id"), nullable=False)
    attended_on = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "event_id", name="uq_student_event_attendance"),
        Index("ix_event_attendance_student", "student_id"),
    )

    student = relationship("Student", back_populates="event_attendance")
    event = relationship("ClubEvent", back_populates="attendance")


class EventVolunteer(Base):
    __tablename__ = "event_volunteers"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("club_events.id"), nullable=False)
    responsibility = Column(String)
    hours = Column(Float, default=0)
    status = Column(String, default="Confirmed")  # Pending / Confirmed / Completed / Cancelled

    __table_args__ = (
        UniqueConstraint("student_id", "event_id", name="uq_student_event_volunteer"),
        Index("ix_event_volunteers_student", "student_id"),
    )

    student = relationship("Student", back_populates="event_volunteering")
    event = relationship("ClubEvent", back_populates="volunteers")


class ODRequest(Base):
    __tablename__ = "od_requests"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("club_events.id"))
    requested_hours = Column(Float, nullable=False)
    approved_hours = Column(Float, default=0)
    request_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="Pending")  # Pending / Approved / Rejected / Cancelled
    reason = Column(Text)
    reviewed_by_faculty_id = Column(Integer, ForeignKey("faculty.id"))

    student = relationship("Student", back_populates="od_requests")
    event = relationship("ClubEvent")
    reviewed_by = relationship("Faculty", foreign_keys=[reviewed_by_faculty_id])


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    role = Column(String)
    ctc_lpa = Column(Float)
    min_cgpa = Column(Float)
    eligible_departments = Column(String)  # comma separated dept codes
    description = Column(Text)

    drives = relationship("PlacementDrive", back_populates="company")


class PlacementDrive(Base):
    __tablename__ = "placement_drives"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    drive_date = Column(Date)
    application_deadline = Column(Date)
    status = Column(String, default="Open")  # Open|Closed|Completed

    company = relationship("Company", back_populates="drives")
    applications = relationship("Application", back_populates="drive")


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    drive_id = Column(Integer, ForeignKey("placement_drives.id"))
    status = Column(String, default="Applied")  # Applied|Shortlisted|Interview|Offered|Rejected
    applied_on = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="applications")
    drive = relationship("PlacementDrive", back_populates="applications")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text)
    response = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
