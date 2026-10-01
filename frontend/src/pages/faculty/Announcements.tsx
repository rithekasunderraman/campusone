import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Announcement { id: number; title: string; body: string; posted_on: string }

export default function FacultyAnnouncements() {
  const { data, loading } = useFetch<Announcement[]>("/announcements");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No announcements right now." />;

  return (
    <div>
      <PageHeader title="Announcements" subtitle="Updates from the administration" />
      <div className="space-y-3 max-w-2xl">
        {data.map((a) => (
          <div key={a.id} className="card p-4">
            <p className="text-sm font-medium text-ink">{a.title}</p>
            <p className="text-sm text-slate mt-1.5">{a.body}</p>
            <p className="text-xs text-slate/70 mt-2">{new Date(a.posted_on).toLocaleDateString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
