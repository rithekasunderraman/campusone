import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, ProgressBar, Pill } from "../../components/Common";

interface AttendanceRow {
  subject_code: string;
  subject_name: string;
  total_classes: number;
  attended_classes: number;
  percentage: number;
  status: "Safe" | "At Risk" | "Shortage";
}

export default function StudentAttendance() {
  const { data, loading } = useFetch<AttendanceRow[]>("/student/attendance");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No attendance records found." />;

  const overall = Math.round(
    (data.reduce((s, r) => s + r.attended_classes, 0) / data.reduce((s, r) => s + r.total_classes, 0)) * 100
  );

  return (
    <div>
      <PageHeader title="Attendance" subtitle={`Overall attendance across all subjects: ${overall}%`} />
      <div className="card p-5">
        <table className="w-full table-clean">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Classes attended</th>
              <th>Percentage</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.subject_code}>
                <td>
                  <p className="font-medium">{r.subject_name}</p>
                  <p className="text-xs text-slate">{r.subject_code}</p>
                </td>
                <td>{r.attended_classes} / {r.total_classes}</td>
                <td className="w-48">
                  <div className="flex items-center gap-2.5">
                    <div className="flex-1"><ProgressBar pct={r.percentage} /></div>
                    <span className="text-xs text-slate w-10">{r.percentage}%</span>
                  </div>
                </td>
                <td>
                  <Pill
                    text={r.status}
                    tone={r.status === "Safe" ? "good" : r.status === "At Risk" ? "warn" : "bad"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
