import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, Pill } from "../../components/Common";

interface FacultyDashboardData {
  profile: { full_name: string; employee_code: string; designation: string; department: string; office: string };
  subjects_count: number;
  students_taught: number;
  average_class_performance_pct: number;
  upcoming_exams: { subject: string; type: string; date: string; venue: string }[];
}

export default function FacultyDashboard() {
  const { data, loading } = useFetch<FacultyDashboardData>("/faculty/dashboard");

  if (loading) return <Loading />;
  if (!data) return <EmptyState text="Could not load your dashboard right now." />;

  return (
    <div>
      <PageHeader
        title={`Welcome, ${data.profile.full_name}`}
        subtitle={`${data.profile.designation} · ${data.profile.department} · ${data.profile.employee_code} · ${data.profile.office}`}
      />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="Subjects Taught" value={data.subjects_count} accent="navy" />
        <StatCard label="Students Taught" value={data.students_taught} accent="brass" />
        <StatCard label="Avg. Class Performance" value={`${data.average_class_performance_pct}%`} accent="leaf" />
      </div>

      <div className="card p-5 mt-6">
        <p className="font-display text-lg text-ink mb-3">Upcoming exams for your subjects</p>
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
    </div>
  );
}
