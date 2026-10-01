import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  type LucideIcon,
  LayoutGrid, CalendarCheck, GraduationCap, ClipboardCheck, Users, BookOpen,
  Wallet, Library, Megaphone, CalendarDays, Briefcase, Bot, LogOut, Building2, BarChart3, UsersRound, FileCheck,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV: Record<string, NavItem[]> = {
  student: [
    { to: "/student", label: "Dashboard", icon: LayoutGrid },
    { to: "/student/attendance", label: "Attendance", icon: CalendarCheck },
    { to: "/student/marks", label: "Marks & Grades", icon: GraduationCap },
    { to: "/student/exams", label: "Exams", icon: ClipboardCheck },
    { to: "/student/timetable", label: "Timetable", icon: CalendarDays },
    { to: "/student/fees", label: "Fees", icon: Wallet },
    { to: "/student/library", label: "Library", icon: Library },
    { to: "/student/placement", label: "Placement", icon: Briefcase },
    { to: "/student/announcements", label: "Announcements & Events", icon: Megaphone },
    { to: "/student/campus-life", label: "Campus Life", icon: UsersRound },
    { to: "/student/od", label: "On-Duty (OD)", icon: FileCheck },
    { to: "/student/assistant", label: "AI Assistant", icon: Bot },
  ],
  faculty: [
    { to: "/faculty", label: "Dashboard", icon: LayoutGrid },
    { to: "/faculty/subjects", label: "My Subjects", icon: BookOpen },
    { to: "/faculty/students", label: "Students", icon: Users },
    { to: "/faculty/attendance", label: "Attendance", icon: CalendarCheck },
    { to: "/faculty/marks", label: "Marks Entry", icon: GraduationCap },
    { to: "/faculty/exams", label: "Exams", icon: ClipboardCheck },
    { to: "/faculty/timetable", label: "Timetable", icon: CalendarDays },
    { to: "/faculty/od", label: "OD Approvals", icon: FileCheck },
    { to: "/faculty/announcements", label: "Announcements", icon: Megaphone },
    { to: "/faculty/assistant", label: "AI Assistant", icon: Bot },
  ],
  admin: [
    { to: "/admin", label: "Dashboard", icon: LayoutGrid },
    { to: "/admin/students", label: "Students", icon: Users },
    { to: "/admin/faculty", label: "Faculty", icon: GraduationCap },
    { to: "/admin/departments", label: "Departments", icon: Building2 },
    { to: "/admin/courses", label: "Courses & Subjects", icon: BookOpen },
    { to: "/admin/placement", label: "Placement Portal", icon: Briefcase },
    { to: "/admin/od", label: "OD Oversight", icon: FileCheck },
    { to: "/admin/reports", label: "Reports & Analytics", icon: BarChart3 },
    { to: "/admin/announcements", label: "Announcements & Events", icon: Megaphone },
    { to: "/admin/assistant", label: "AI Assistant", icon: Bot },
  ],
};

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;
  const items = NAV[user.role];

  return (
    <div className="min-h-screen flex bg-paper">
      <aside className="w-64 shrink-0 bg-navy text-paper flex flex-col">
        <div className="px-5 py-6 border-b border-white/10">
          <p className="font-display text-lg leading-tight">CampusOne <span className="text-brassLight">AI</span></p>
          <p className="text-[11px] text-paper/50 mt-0.5 capitalize">{user.role} portal</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === `/${user.role}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive ? "bg-white/10 text-white font-medium" : "text-paper/70 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <item.icon size={17} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-4 border-t border-white/10">
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-paper/70 hover:bg-white/5 hover:text-white w-full"
          >
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-black/5 bg-white flex items-center justify-between px-8">
          <div />
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-ink leading-tight">{user.full_name}</p>
              <p className="text-xs text-slate capitalize">{user.role}</p>
            </div>
            <div className="h-9 w-9 rounded-full bg-brass/20 text-brass flex items-center justify-center font-display font-medium">
              {user.full_name.charAt(0)}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
