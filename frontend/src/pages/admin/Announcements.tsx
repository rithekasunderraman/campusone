import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";
import client from "../../api/client";

interface Announcement { id: number; title: string; body: string; audience: string; posted_on: string }
interface EventRow { id: number; title: string; description: string; date: string; venue: string }

export default function AdminAnnouncements() {
  const { data: announcements, loading: l1, reload: reloadAnn } = useFetch<Announcement[]>("/announcements");
  const { data: events, loading: l2, reload: reloadEv } = useFetch<EventRow[]>("/events");

  const [annForm, setAnnForm] = useState({ title: "", body: "", audience: "all" });
  const [evForm, setEvForm] = useState({ title: "", description: "", event_date: "", venue: "" });
  const [message, setMessage] = useState("");

  const postAnnouncement = async () => {
    try {
      await client.post("/admin/announcements", annForm);
      setMessage("Announcement posted.");
      setAnnForm({ title: "", body: "", audience: "all" });
      reloadAnn();
    } catch {
      setMessage("Could not post announcement.");
    }
  };

  const postEvent = async () => {
    try {
      await client.post("/admin/events", evForm);
      setMessage("Event created.");
      setEvForm({ title: "", description: "", event_date: "", venue: "" });
      reloadEv();
    } catch {
      setMessage("Could not create event.");
    }
  };

  return (
    <div>
      <PageHeader title="Announcements & Events" subtitle="Post updates and manage campus events" />
      {message && <div className="card p-3.5 mb-4 text-sm text-ink bg-brass/10 border-brass/20">{message}</div>}

      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <div className="card p-5 mb-4">
            <p className="font-display text-lg text-ink mb-3">Post an announcement</p>
            <div className="space-y-2">
              <input className="input" placeholder="Title" value={annForm.title} onChange={(e) => setAnnForm({ ...annForm, title: e.target.value })} />
              <textarea className="input" placeholder="Message" value={annForm.body} onChange={(e) => setAnnForm({ ...annForm, body: e.target.value })} />
              <select className="input" value={annForm.audience} onChange={(e) => setAnnForm({ ...annForm, audience: e.target.value })}>
                <option value="all">Everyone</option>
                <option value="student">Students only</option>
                <option value="faculty">Faculty only</option>
              </select>
              <button className="btn-primary text-xs py-2 px-3" onClick={postAnnouncement}>Post</button>
            </div>
          </div>
          <p className="font-display text-lg text-ink mb-3">Recent announcements</p>
          {l1 ? <Loading /> : !announcements || announcements.length === 0 ? (
            <EmptyState text="No announcements yet." />
          ) : (
            <div className="space-y-3">
              {announcements.map((a) => (
                <div key={a.id} className="card p-4">
                  <p className="text-sm font-medium text-ink">{a.title}</p>
                  <p className="text-sm text-slate mt-1.5">{a.body}</p>
                  <p className="text-xs text-slate/70 mt-2 capitalize">{a.audience} · {new Date(a.posted_on).toLocaleDateString()}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="card p-5 mb-4">
            <p className="font-display text-lg text-ink mb-3">Create an event</p>
            <div className="space-y-2">
              <input className="input" placeholder="Title" value={evForm.title} onChange={(e) => setEvForm({ ...evForm, title: e.target.value })} />
              <textarea className="input" placeholder="Description" value={evForm.description} onChange={(e) => setEvForm({ ...evForm, description: e.target.value })} />
              <div className="grid grid-cols-2 gap-2">
                <input className="input" type="date" value={evForm.event_date} onChange={(e) => setEvForm({ ...evForm, event_date: e.target.value })} />
                <input className="input" placeholder="Venue" value={evForm.venue} onChange={(e) => setEvForm({ ...evForm, venue: e.target.value })} />
              </div>
              <button className="btn-primary text-xs py-2 px-3" onClick={postEvent}>Create</button>
            </div>
          </div>
          <p className="font-display text-lg text-ink mb-3">Upcoming events</p>
          {l2 ? <Loading /> : !events || events.length === 0 ? (
            <EmptyState text="No events yet." />
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
