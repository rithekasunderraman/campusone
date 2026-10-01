import { useState } from "react";
import client from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, ErrorState, Pagination, Banner, Pill } from "../../components/Common";
import { ODRequest, Page, RequestDetail, RequestTable, actionLabel, errorMessage, fmtStamp } from "../../components/OD";

interface Stats {
  advisees: number; pending: number; awaiting_student: number; with_hod: number;
  approved_this_month: number; forwarded_this_month: number; rejected_this_month: number;
}
interface HistoryRow {
  id: number; request_id: number; action: string; new_state_label: string; comment: string | null; at: string;
  event_name: string; student_name: string; register_number: string; requested_hours: number; current_state_label: string;
}

const TABS = [
  { key: "pending", label: "Awaiting my decision" },
  { key: "awaiting_student", label: "Waiting on student" },
  { key: "with_hod", label: "With HOD" },
  { key: "history", label: "My decisions" },
];
const POLL_MS = 8000;

export default function FacultyODQueue() {
  const [tab, setTab] = useState("pending");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "good" | "bad" } | null>(null);

  const stats = useFetch<Stats>("/faculty/od/stats", [], { pollMs: POLL_MS });
  const params = new URLSearchParams({ page: String(page), page_size: "8" });
  if (tab !== "history") params.set("state", tab);
  if (search.trim() && tab !== "history") params.set("q", search.trim());
  const listUrl = tab === "history" ? `/faculty/od/history?${params}` : `/faculty/od/queue?${params}`;
  const list = useFetch<Page<any>>(listUrl, [], { pollMs: POLL_MS });
  const detail = useFetch<ODRequest>(selected ? `/faculty/od/requests/${selected}` : null, [], { pollMs: POLL_MS });

  const switchTab = (key: string) => { setTab(key); setPage(1); setSelected(null); setMessage(null); };

  const act = async (action: string, done: string) => {
    if (!detail.data) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await client.post(`/faculty/od/requests/${detail.data.id}/${action}`, { version: detail.data.version, comment: comment.trim() || null });
      setMessage({ text: `${done} (${res.data.state_label}).`, tone: "good" });
      setComment("");
    } catch (err) {
      setMessage({ text: errorMessage(err), tone: "bad" });
    } finally {
      setBusy(false);
      detail.refresh();
      list.refresh();
      stats.refresh();
    }
  };

  const req = detail.data;
  const canDecide = !!req && req.allowed_actions.includes("reject");

  return (
    <div>
      <PageHeader title="OD Approvals" subtitle="Requests from the students you advise — the list updates automatically" />

      {stats.data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Awaiting my decision" value={stats.data.pending} hint={`${stats.data.advisees} advisees`} accent="brass" />
          <StatCard label="Waiting on student" value={stats.data.awaiting_student} hint="Clarification requested" accent="navy" />
          <StatCard label="With HOD" value={stats.data.with_hod} hint="Recommended by me" accent="navy" />
          <StatCard label="Approved this month" value={stats.data.approved_this_month + stats.data.forwarded_this_month} hint={`${stats.data.rejected_this_month} rejected`} accent="leaf" />
        </div>
      )}

      {message && <Banner text={message.text} tone={message.tone} onClose={() => setMessage(null)} />}

      <div className="grid xl:grid-cols-5 gap-6 items-start">
        <div className="card p-5 xl:col-span-3">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            <div className="flex gap-1 flex-wrap" role="tablist" aria-label="OD request lists">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  role="tab"
                  aria-selected={tab === t.key}
                  className={`text-xs px-3 py-1.5 rounded-full border ${tab === t.key ? "bg-navy text-paper border-navy" : "border-black/10 text-slate hover:bg-black/[0.03]"}`}
                  onClick={() => switchTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {tab !== "history" && (
              <>
                <label htmlFor="fq-search" className="sr-only">Search by student, register number or event</label>
                <input id="fq-search" className="input w-60" placeholder="Search student, reg. no. or event" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
              </>
            )}
          </div>

          {list.loading && !list.data ? (
            <Loading />
          ) : list.error || !list.data ? (
            <ErrorState text={list.error || "Could not load requests."} onRetry={list.reload} />
          ) : list.data.total === 0 ? (
            <EmptyState text={tab === "pending" ? (search ? "No pending requests match your search." : "Nothing is waiting for your decision.") : tab === "history" ? "You have not made any OD decisions yet." : "No requests here."} />
          ) : tab === "history" ? (
            <div className="overflow-x-auto">
              <table className="w-full table-clean">
                <thead><tr><th>When</th><th>Student</th><th>Event</th><th>My action</th><th>Now</th></tr></thead>
                <tbody>
                  {(list.data.items as HistoryRow[]).map((h) => (
                    <tr key={h.id} className="cursor-pointer hover:bg-black/[0.02]" onClick={() => setSelected(h.request_id)}>
                      <td className="whitespace-nowrap">{fmtStamp(h.at)}</td>
                      <td className="font-medium">{h.student_name}<span className="block text-xs text-slate font-normal">{h.register_number}</span></td>
                      <td>{h.event_name}<span className="block text-xs text-slate">#{h.request_id} · {h.requested_hours}h</span></td>
                      <td>{actionLabel(h.action)}{h.comment && <span className="block text-xs text-slate">“{h.comment}”</span>}</td>
                      <td><Pill text={h.current_state_label} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <RequestTable rows={list.data.items as ODRequest[]} showStudent selectedId={selected} onSelect={(r) => { setSelected(r.id); setComment(""); setMessage(null); }} />
          )}
          {list.data && <Pagination page={list.data.page} pages={list.data.pages} total={list.data.total} pageSize={list.data.page_size} onPage={setPage} />}
        </div>

        <div className="xl:col-span-2">
          {!selected ? (
            <EmptyState text="Select a request to see its details and decide." />
          ) : detail.loading && !req ? (
            <div className="card p-5"><Loading /></div>
          ) : detail.error || !req ? (
            <ErrorState text={detail.error || "Could not load this request."} onRetry={detail.reload} />
          ) : (
            <div className="card p-5">
              <RequestDetail req={req} role="faculty" />
              {canDecide && (
                <div className="mt-5 pt-5 border-t border-black/5">
                  <label htmlFor="fq-comment" className="block text-xs text-slate mb-1">
                    Comment (required to reject or ask for clarification)
                  </label>
                  <textarea id="fq-comment" className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
                  {req.requires_hod && (
                    <p className="text-xs text-slate mt-2">This request is over the HOD threshold: approving it sends it to the HOD for the final decision.</p>
                  )}
                  <div className="flex gap-2 flex-wrap mt-3">
                    <button className="btn-primary" disabled={busy} onClick={() => act("approve", req.requires_hod ? "Recommended and sent to HOD" : "Request approved")}>
                      {req.requires_hod ? "Recommend to HOD" : "Approve"}
                    </button>
                    <button className="btn-secondary" disabled={busy || !comment.trim()} onClick={() => act("request-clarification", "Clarification requested")}>
                      Ask for clarification
                    </button>
                    <button className="btn-secondary text-clay" disabled={busy || !comment.trim()} onClick={() => act("reject", "Request rejected")}>
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
