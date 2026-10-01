import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, Pill } from "../../components/Common";

type Club = { club_id: number; club_name: string; category: string; role: string; meeting: string; description: string };
type Event = { event_id: number; club_name: string; title: string; date: string; start_time?: string; end_time?: string; venue?: string };
type Volunteer = Event & { responsibility: string; hours: number; status: string };
type OD = { annual_entitlement_hours: number; used_hours: number; remaining_hours: number; requests: { request_id:number; event_title:string|null; requested_hours:number; approved_hours:number; status:string }[] };
type Profile = { accommodation_type: string; hostel: null | { name:string; block:string; room_type:string; room_number:string; bed_number:string; academic_year:string } };

export default function CampusLife() {
  const clubs = useFetch<Club[]>("/student/campus-life/clubs");
  const upcoming = useFetch<Event[]>("/student/campus-life/events/upcoming");
  const attended = useFetch<Event[]>("/student/campus-life/events/attended");
  const volunteered = useFetch<Volunteer[]>("/student/campus-life/events/volunteered");
  const od = useFetch<OD>("/student/campus-life/od");
  const profile = useFetch<Profile>("/student/campus-life/profile");

  const loading = [clubs, upcoming, attended, volunteered, od, profile].some(x => x.loading);
  if (loading) return <Loading />;
  if (!clubs.data || !upcoming.data || !attended.data || !volunteered.data || !od.data || !profile.data)
    return <EmptyState text="Could not load campus-life data right now." />;

  return (
    <div>
      <PageHeader title="Campus Life" subtitle="Your clubs, events, accommodation and On-Duty activity" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="My Clubs" value={clubs.data.length} hint="Active memberships" accent="navy" />
        <StatCard label="Events Attended" value={attended.data.length} hint="Club events" accent="leaf" />
        <StatCard label="Events Volunteered" value={volunteered.data.length} hint={`${volunteered.data.reduce((a,v)=>a+v.hours,0)} volunteer hours`} accent="brass" />
        <StatCard label="OD Remaining" value={`${od.data.remaining_hours}h`} hint={`${od.data.used_hours}h used of ${od.data.annual_entitlement_hours}h`} accent="clay" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">Accommodation</p>
          <Pill text={profile.data.accommodation_type} />
          {profile.data.hostel ? (
            <div className="mt-4 text-sm space-y-1 text-slate">
              <p className="text-ink font-medium">{profile.data.hostel.name} · {profile.data.hostel.block}</p>
              <p>Room {profile.data.hostel.room_number}, Bed {profile.data.hostel.bed_number}</p>
              <p>{profile.data.hostel.room_type} · Academic year {profile.data.hostel.academic_year}</p>
            </div>
          ) : <p className="text-sm text-slate mt-3">No hostel allocation — you are a day scholar.</p>}
        </section>

        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">OD Summary</p>
          <div className="flex justify-between text-sm mb-2"><span className="text-slate">Used</span><b>{od.data.used_hours}h</b></div>
          <div className="h-2 bg-black/5 rounded-full overflow-hidden">
            <div className="h-full bg-brass" style={{width: `${Math.min(100, (od.data.used_hours / od.data.annual_entitlement_hours) * 100)}%`}} />
          </div>
          <p className="text-xs text-slate mt-2">{od.data.remaining_hours} hours remaining</p>
          <div className="mt-4 space-y-2">
            {od.data.requests.slice(0,3).map(r => <div key={r.request_id} className="flex justify-between text-xs border-b border-black/5 pb-2"><span>{r.event_title || "OD request"} · {r.requested_hours}h</span><Pill text={r.status} /></div>)}
          </div>
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">My Clubs</p>
          <div className="space-y-3">
            {clubs.data.map(c => <div key={c.club_id} className="border-b border-black/5 pb-3 last:border-0"><div className="flex justify-between gap-3"><div><p className="text-sm font-medium">{c.club_name}</p><p className="text-xs text-slate">{c.category} · {c.meeting}</p></div><Pill text={c.role} /></div></div>)}
          </div>
        </section>

        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">Upcoming Club Events</p>
          <div className="space-y-3">
            {upcoming.data.slice(0,8).map(e => <div key={e.event_id} className="border-b border-black/5 pb-3 last:border-0"><div className="flex justify-between gap-3"><div><p className="text-sm font-medium">{e.title}</p><p className="text-xs text-slate">{e.club_name} · {e.venue}</p></div><Pill text={e.date} /></div></div>)}
            {!upcoming.data.length && <p className="text-sm text-slate">No upcoming club events.</p>}
          </div>
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">Events Attended</p>
          <div className="space-y-2">
            {attended.data.slice(0,10).map(e => <div key={e.event_id} className="flex justify-between text-sm border-b border-black/5 pb-2"><span>{e.title}<span className="text-xs text-slate block">{e.club_name} · {e.venue}</span></span><Pill text={e.date} /></div>)}
          </div>
        </section>
        <section className="card p-5">
          <p className="font-display text-lg text-ink mb-4">Volunteering</p>
          <div className="space-y-2">
            {volunteered.data.slice(0,10).map(v => <div key={v.event_id} className="flex justify-between text-sm border-b border-black/5 pb-2"><span>{v.title}<span className="text-xs text-slate block">{v.responsibility} · {v.hours}h</span></span><Pill text={v.status} /></div>)}
          </div>
        </section>
      </div>
    </div>
  );
}
