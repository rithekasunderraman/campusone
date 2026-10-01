import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface AttendanceReportRow { subject_code: string; subject_name: string; avg_attendance_pct: number; students: number }
interface AcademicReportRow { subject_code: string; subject_name: string; avg_marks_pct: number; grade_distribution: Record<string, number> }

export default function AdminReports() {
  const { data: attendance, loading: l1 } = useFetch<AttendanceReportRow[]>("/admin/reports/attendance");
  const { data: academic, loading: l2 } = useFetch<AcademicReportRow[]>("/admin/reports/academic");

  return (
    <div>
      <PageHeader title="Reports & Analytics" subtitle="Institution-wide attendance and academic performance by subject" />

      <div className="card p-5 mb-6">
        <p className="font-display text-lg text-ink mb-4">Average attendance by subject</p>
        {l1 ? <Loading /> : !attendance || attendance.length === 0 ? (
          <EmptyState text="No attendance data available." />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={attendance}>
              <CartesianGrid strokeDasharray="3 3" stroke="#12233D0D" />
              <XAxis dataKey="subject_code" tick={{ fontSize: 11, fill: "#5B6B7C" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5B6B7C" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="avg_attendance_pct" name="Avg. Attendance %" fill="#0F2A4A" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card p-5">
        <p className="font-display text-lg text-ink mb-4">Average academic performance by subject</p>
        {l2 ? <Loading /> : !academic || academic.length === 0 ? (
          <EmptyState text="No academic data available." />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={academic}>
              <CartesianGrid strokeDasharray="3 3" stroke="#12233D0D" />
              <XAxis dataKey="subject_code" tick={{ fontSize: 11, fill: "#5B6B7C" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5B6B7C" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="avg_marks_pct" name="Avg. Marks %" fill="#B98B3E" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
