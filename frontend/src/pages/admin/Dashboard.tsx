import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState } from "../../components/Common";

interface DeptStat { department: string; code: string; students: number; avg_attendance_pct: number; avg_cgpa: number }
interface AdminDashboardData {
  total_students: number; total_faculty: number; total_departments: number;
  overall_attendance_pct: number; average_marks_pct: number;
  upcoming_exams: { subject: string; type: string; date: string }[];
  placement_offers: number; open_drives: number;
  department_stats: DeptStat[];
}

export default function AdminDashboard() {
  const { data, loading } = useFetch<AdminDashboardData>("/admin/dashboard");

  if (loading) return <Loading />;
  if (!data) return <EmptyState text="Could not load the dashboard right now." />;

  return (
    <div>
      <PageHeader title="Institution Overview" subtitle="Live snapshot across all departments" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Students" value={data.total_students} accent="navy" />
        <StatCard label="Total Faculty" value={data.total_faculty} accent="brass" />
        <StatCard label="Overall Attendance" value={`${data.overall_attendance_pct}%`} accent={data.overall_attendance_pct >= 75 ? "leaf" : "clay"} />
        <StatCard label="Avg. Academic Performance" value={`${data.average_marks_pct}%`} accent="leaf" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        <StatCard label="Departments" value={data.total_departments} accent="navy" />
        <StatCard label="Open Placement Drives" value={data.open_drives} accent="brass" />
        <StatCard label="Offers Made" value={data.placement_offers} accent="leaf" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <div className="card p-5">
          <p className="font-display text-lg text-ink mb-3">Department performance</p>
          <table className="w-full table-clean">
            <thead>
              <tr><th>Department</th><th>Students</th><th>Attendance</th><th>Avg. CGPA</th></tr>
            </thead>
            <tbody>
              {data.department_stats.map((d) => (
                <tr key={d.code}>
                  <td className="font-medium">{d.code}</td>
                  <td>{d.students}</td>
                  <td>{d.avg_attendance_pct}%</td>
                  <td>{d.avg_cgpa}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card p-5">
          <p className="font-display text-lg text-ink mb-3">Upcoming exams</p>
          {data.upcoming_exams.length === 0 ? (
            <p className="text-sm text-slate">No exams scheduled right now.</p>
          ) : (
            <div className="space-y-3">
              {data.upcoming_exams.map((e, i) => (
                <div key={i} className="flex items-center justify-between border-b border-black/5 pb-3 last:border-0 last:pb-0">
                  <div>
                    <p className="text-sm font-medium text-ink">{e.subject}</p>
                    <p className="text-xs text-slate mt-0.5">{e.type}</p>
                  </div>
                  <span className="text-xs text-slate">{e.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
