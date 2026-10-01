import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, Pill } from "../../components/Common";
import { useAuth } from "../../context/AuthContext";

interface DashboardData {
  profile: { full_name: string; register_number: string; department: string; year: number; semester: number; cgpa: number };
  attendance_overall_pct: number;
  subjects_count: number;
  average_marks_pct: number;
  fees_status: string;
  upcoming_exams: { subject: string; type: string; date: string; venue: string }[];
  placement_applications: number;
  placement_offers: number;
}

export default function StudentDashboard() {
  const { user } = useAuth();
  const { data, loading } = useFetch<DashboardData>("/student/dashboard");

  if (loading) return <Loading />;
  if (!data) return <EmptyState text="Could not load your dashboard right now." />;

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user?.full_name.split(" ")[0]}`}
        subtitle={`${data.profile.register_number} · ${data.profile.department} · Year ${data.profile.year}, Semester ${data.profile.semester}`}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Overall Attendance" value={`${data.attendance_overall_pct}%`}
          hint={data.attendance_overall_pct >= 75 ? "Meeting requirement" : "Below 75% requirement"}
          accent={data.attendance_overall_pct >= 75 ? "leaf" : "clay"} />
        <StatCard label="Current CGPA" value={data.profile.cgpa} hint={`Avg. marks this sem: ${data.average_marks_pct}%`} accent="brass" />
        <StatCard label="Fees Status" value={data.fees_status} accent={data.fees_status === "Paid" ? "leaf" : "clay"} />
        <StatCard label="Placement Applications" value={data.placement_applications}
          hint={`${data.placement_offers} offer(s) received`} accent="navy" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
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
                    <p className="text-xs text-slate mt-0.5">{e.type} · {e.venue}</p>
                  </div>
                  <Pill text={e.date} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-5">
          <p className="font-display text-lg text-ink mb-3">Enrolled subjects</p>
          <p className="text-sm text-slate">
            You are currently enrolled in <span className="font-medium text-ink">{data.subjects_count} subjects</span> this
            semester. Visit Attendance or Marks & Grades from the sidebar for a full subject-wise breakdown, or ask
            the AI Assistant a quick question about any of them.
          </p>
        </div>
      </div>
    </div>
  );
}
