import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import DashboardLayout from "./layouts/DashboardLayout";

import StudentDashboard from "./pages/student/Dashboard";
import StudentAttendance from "./pages/student/Attendance";
import StudentMarks from "./pages/student/Marks";
import StudentExams from "./pages/student/Exams";
import StudentTimetable from "./pages/student/Timetable";
import StudentFees from "./pages/student/Fees";
import StudentLibrary from "./pages/student/Library";
import StudentPlacement from "./pages/student/Placement";
import StudentAnnouncements from "./pages/student/Announcements";
import CampusLife from "./pages/student/CampusLife";
import StudentODDashboard from "./pages/student/ODDashboard";
import StudentODApply from "./pages/student/ODApply";
import StudentODDetail from "./pages/student/ODDetail";

import FacultyDashboard from "./pages/faculty/Dashboard";
import FacultySubjects from "./pages/faculty/Subjects";
import FacultyStudents from "./pages/faculty/Students";
import FacultyAttendance from "./pages/faculty/Attendance";
import FacultyMarks from "./pages/faculty/Marks";
import FacultyExams from "./pages/faculty/Exams";
import FacultyTimetable from "./pages/faculty/Timetable";
import FacultyAnnouncements from "./pages/faculty/Announcements";
import FacultyODQueue from "./pages/faculty/ODQueue";

import AdminDashboard from "./pages/admin/Dashboard";
import AdminStudents from "./pages/admin/Students";
import AdminFaculty from "./pages/admin/Faculty";
import AdminDepartments from "./pages/admin/Departments";
import AdminCourses from "./pages/admin/Courses";
import AdminPlacement from "./pages/admin/Placement";
import AdminReports from "./pages/admin/Reports";
import AdminAnnouncements from "./pages/admin/Announcements";
import AdminODOversight from "./pages/admin/ODOversight";

import AIAssistant from "./pages/AIAssistant";

function ProtectedRoute({ role, children }: { role: "student" | "faculty" | "admin"; children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={`/${user.role}`} replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={`/${user.role}`} replace /> : <Login />} />

      <Route
        path="/student"
        element={
          <ProtectedRoute role="student">
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<StudentDashboard />} />
        <Route path="attendance" element={<StudentAttendance />} />
        <Route path="marks" element={<StudentMarks />} />
        <Route path="exams" element={<StudentExams />} />
        <Route path="timetable" element={<StudentTimetable />} />
        <Route path="fees" element={<StudentFees />} />
        <Route path="library" element={<StudentLibrary />} />
        <Route path="placement" element={<StudentPlacement />} />
        <Route path="announcements" element={<StudentAnnouncements />} />
        <Route path="campus-life" element={<CampusLife />} />
        <Route path="od" element={<StudentODDashboard />} />
        <Route path="od/new" element={<StudentODApply />} />
        <Route path="od/:id" element={<StudentODDetail />} />
        <Route path="assistant" element={<AIAssistant />} />
      </Route>

      <Route
        path="/faculty"
        element={
          <ProtectedRoute role="faculty">
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<FacultyDashboard />} />
        <Route path="subjects" element={<FacultySubjects />} />
        <Route path="students" element={<FacultyStudents />} />
        <Route path="attendance" element={<FacultyAttendance />} />
        <Route path="marks" element={<FacultyMarks />} />
        <Route path="exams" element={<FacultyExams />} />
        <Route path="timetable" element={<FacultyTimetable />} />
        <Route path="announcements" element={<FacultyAnnouncements />} />
        <Route path="od" element={<FacultyODQueue />} />
        <Route path="assistant" element={<AIAssistant />} />
      </Route>

      <Route
        path="/admin"
        element={
          <ProtectedRoute role="admin">
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="students" element={<AdminStudents />} />
        <Route path="faculty" element={<AdminFaculty />} />
        <Route path="departments" element={<AdminDepartments />} />
        <Route path="courses" element={<AdminCourses />} />
        <Route path="placement" element={<AdminPlacement />} />
        <Route path="reports" element={<AdminReports />} />
        <Route path="announcements" element={<AdminAnnouncements />} />
        <Route path="od" element={<AdminODOversight />} />
        <Route path="assistant" element={<AIAssistant />} />
      </Route>

      <Route path="/" element={<Navigate to={user ? `/${user.role}` : "/login"} replace />} />
      <Route path="*" element={<Navigate to={user ? `/${user.role}` : "/login"} replace />} />
    </Routes>
  );
}
