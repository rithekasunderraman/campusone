import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Slot { day: string; start_time: string; end_time: string; room: string; subject_code: string; subject_name: string }
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

export default function FacultyTimetable() {
  const { data, loading } = useFetch<Slot[]>("/faculty/timetable");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No timetable published for your subjects yet." />;

  return (
    <div>
      <PageHeader title="Teaching Timetable" subtitle="Your weekly teaching schedule" />
      <div className="grid md:grid-cols-5 gap-4">
        {DAYS.map((day) => {
          const sessions = data.filter((s) => s.day === day).sort((a, b) => a.start_time.localeCompare(b.start_time));
          return (
            <div key={day} className="card p-4">
              <p className="font-display text-base text-ink mb-3">{day}</p>
              {sessions.length === 0 ? (
                <p className="text-xs text-slate">No classes</p>
              ) : (
                <div className="space-y-2.5">
                  {sessions.map((s, i) => (
                    <div key={i} className="rounded-lg bg-navy/[0.04] px-3 py-2.5">
                      <p className="text-xs text-brass font-medium">{s.start_time} – {s.end_time}</p>
                      <p className="text-sm text-ink font-medium mt-0.5">{s.subject_code}</p>
                      <p className="text-xs text-slate mt-0.5">{s.room}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
