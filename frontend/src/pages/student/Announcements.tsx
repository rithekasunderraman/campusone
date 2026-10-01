import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Announcement { id: number; title: string; body: string; posted_on: string }
interface EventRow { id: number; title: string; description: string; date: string; venue: string }

export default function StudentAnnouncements() {
  const { data: announcements, loading: l1 } = useFetch<Announcement[]>("/announcements");
  const { data: events, loading: l2 } = useFetch<EventRow[]>("/events");

  return (
    <div>
      <PageHeader title="Announcements & Events" subtitle="Campus-wide updates and upcoming events" />
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <p className="font-display text-lg text-ink mb-3">Announcements</p>
          {l1 ? <Loading /> : !announcements || announcements.length === 0 ? (
            <EmptyState text="No announcements right now." />
          ) : (
            <div className="space-y-3">
              {announcements.map((a) => (
                <div key={a.id} className="card p-4">
                  <p className="text-sm font-medium text-ink">{a.title}</p>
                  <p className="text-sm text-slate mt-1.5">{a.body}</p>
                  <p className="text-xs text-slate/70 mt-2">{new Date(a.posted_on).toLocaleDateString()}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div>
          <p className="font-display text-lg text-ink mb-3">Campus events</p>
          {l2 ? <Loading /> : !events || events.length === 0 ? (
            <EmptyState text="No upcoming events." />
          ) : (
            <div className="space-y-3">
              {events.map((e) => (
                <div key={e.id} className="card p-4 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{e.title}</p>
                    <p className="text-sm text-slate mt-1.5">{e.description}</p>
                    <p className="text-xs text-slate/70 mt-2">{e.venue}</p>
                  </div>
                  <span className="font-display text-brass whitespace-nowrap">{e.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
