import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import client from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, ErrorState, Pagination, Banner } from "../../components/Common";
import { ODRequest, Page, RequestDetail, RequestTable, actionLabel, errorMessage, fmtStamp } from "../../components/OD";

interface Scope { institution_wide: boolean; departments: { id: number; code: string; name: string }[] }
interface DeptStat {
  department_id: number; department: string; department_name: string; students: number; total_requests: number;
  approved: number; rejected: number; cancelled: number; pending: number; pending_hod: number;
  approval_rate_pct: number | null; approved_hours: number; utilisation_pct: number;
  avg_hours_per_student: number; avg_turnaround_hours: number | null; decisions_with_turnaround: number;
}
interface Analytics {
  term: { start: string; end: string };
  totals: { requests: number; approved: number; rejected: number; pending: number; pending_hod: number; approval_rate_pct: number | null; approved_hours: number; avg_turnaround_hours: number | null; decisions_with_turnaround: number };
  state_breakdown: { state: string; label: string; count: number }[];
  by_department: DeptStat[];
  note: string;
}
interface Policy {
  institution: string; od_hours_per_semester: number; term_start: string; term_end: string; min_attendance_pct: number;
  approval_chain: string[]; hod_threshold_hours: number; max_hours_per_request: number; can_edit: boolean;
}
interface AuditEntry { id: number; at: string; action: string; old_state: string | null; new_state: string; actor_role: string; actor_name: string; actor_username: string | null; comment: string | null }

const TABS = [
  { key: "queue", label: "Awaiting HOD decision" },
  { key: "all", label: "All requests" },
  { key: "analytics", label: "Analytics" },
  { key: "policy", label: "Policy" },
];
const STATES = [
  ["", "Any status"], ["UnderFacultyReview", "Under faculty review"], ["ClarificationRequested", "Clarification requested"],
  ["Resubmitted", "Resubmitted"], ["UnderHODReview", "Under HOD review"], ["Approved", "Approved"], ["Rejected", "Rejected"], ["Cancelled", "Cancelled"],
];
const POLL_MS = 8000;

function AuditLog({ requestId }: { requestId: number }) {
  const { data, loading, error, reload } = useFetch<{ entries: AuditEntry[] }>(`/admin/od/requests/${requestId}/audit`, [], { pollMs: POLL_MS });
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState text={error || "Could not load the audit log."} onRetry={reload} />;
  if (!data.entries.length) return <p className="text-sm text-slate">No audit entries: this request was imported from the earlier OD records.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-clean">
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>From → To</th><th>Comment</th></tr></thead>
        <tbody>
          {data.entries.map((e) => (
            <tr key={e.id}>
              <td className="whitespace-nowrap">{fmtStamp(e.at)}</td>
              <td>{e.actor_name}<span className="block text-xs text-slate">{e.actor_username ? `${e.actor_username} · ${e.actor_role}` : "system"}</span></td>
              <td>{actionLabel(e.action)}</td>
              <td className="text-xs">{e.old_state || "—"} → {e.new_state}</td>
              <td className="text-slate">{e.comment || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PolicyForm() {
  const { data, loading, error, reload } = useFetch<Policy>("/admin/od/policy");
  const [form, setForm] = useState<Policy | null>(null);
  const [message, setMessage] = useState<{ text: string; tone: "good" | "bad" } | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (data) setForm(data); }, [data]);
  if (loading && !form) return <Loading />;
  if (error || !form) return <ErrorState text={error || "Could not load the policy."} onRetry={reload} />;

  const num = (key: keyof Policy, label: string, hint: string) => (
    <div>
      <label htmlFor={`pol-${key}`} className="block text-xs text-slate mb-1">{label}</label>
      <input id={`pol-${key}`} type="number" className="input" disabled={!form.can_edit} value={String(form[key])}
        onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })} />
      <p className="text-[11px] text-slate mt-1">{hint}</p>
    </div>
  );
  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await client.put("/admin/od/policy", {
        od_hours_per_semester: form.od_hours_per_semester, min_attendance_pct: form.min_attendance_pct,
        approval_chain: form.approval_chain, hod_threshold_hours: form.hod_threshold_hours, max_hours_per_request: form.max_hours_per_request,
      });
      setForm(res.data);
      setMessage({ text: "Policy saved. It applies to new submissions and decisions from now on.", tone: "good" });
    } catch (err) {
      setMessage({ text: errorMessage(err), tone: "bad" });
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="card p-6 max-w-3xl">
      <p className="font-display text-lg text-ink">{form.institution} — OD policy</p>
      <p className="text-sm text-slate mt-1">Current term: {form.term_start} to {form.term_end}. These settings drive every eligibility check and approval route.</p>
      {message && <div className="mt-4"><Banner text={message.text} tone={message.tone} onClose={() => setMessage(null)} /></div>}
      {!form.can_edit && <p className="text-sm text-slate mt-3">You head a department, so this policy is read-only for you. An institution-wide administrator can change it.</p>}
      <div className="grid sm:grid-cols-2 gap-4 mt-5">
        {num("od_hours_per_semester", "OD hours per student per semester", "Total a student may have approved in one term.")}
        {num("min_attendance_pct", "Minimum attendance to apply (%)", "Students below this cannot submit OD requests.")}
        {num("max_hours_per_request", "Maximum hours in one request", "Longer events need separate requests.")}
        <div>
          <label htmlFor="pol-chain" className="block text-xs text-slate mb-1">Approval chain</label>
          <select id="pol-chain" className="input" disabled={!form.can_edit} value={form.approval_chain.join(",")}
            onChange={(e) => setForm({ ...form, approval_chain: e.target.value.split(",") })}>
            <option value="faculty">Class advisor only</option>
            <option value="faculty,hod">Class advisor, then HOD for long requests</option>
          </select>
          <p className="text-[11px] text-slate mt-1">Who must sign off before a request is approved.</p>
        </div>
        {form.approval_chain.includes("hod") &&
          num("hod_threshold_hours", "HOD sign-off above (hours)", "Requests longer than this go to the HOD after the class advisor. 0 = every request.")}
      </div>
      {form.can_edit && <button className="btn-primary mt-5" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save policy"}</button>}
    </div>
  );
}

function AnalyticsView() {
  const { data, loading, error, reload } = useFetch<Analytics>("/admin/od/analytics", [], { pollMs: 15000 });
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState text={error || "Could not load analytics."} onRetry={reload} />;
  const t = data.totals;
  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Requests this term" value={t.requests.toLocaleString()} hint={`${data.term.start} to ${data.term.end}`} accent="navy" />
        <StatCard label="Approval rate" value={t.approval_rate_pct === null ? "—" : `${t.approval_rate_pct}%`} hint={`${t.approved.toLocaleString()} approved · ${t.rejected.toLocaleString()} rejected`} accent="leaf" />
        <StatCard label="Awaiting decision" value={t.pending.toLocaleString()} hint={`${t.pending_hod} with HOD`} accent="brass" />
        <StatCard label="Average turnaround" value={t.avg_turnaround_hours === null ? "—" : `${t.avg_turnaround_hours}h`} hint={`from ${t.decisions_with_turnaround} workflow decision${t.decisions_with_turnaround === 1 ? "" : "s"}`} accent="clay" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <div className="card p-5">
          <p className="font-display text-lg text-ink mb-4">Requests by department</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_department}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0000000f" />
                <XAxis dataKey="department" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="approved" name="Approved" stackId="a" fill="#3D7A5C" />
                <Bar dataKey="pending" name="Awaiting decision" stackId="a" fill="#B98B3E" />
                <Bar dataKey="rejected" name="Rejected" stackId="a" fill="#B5573C" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card p-5">
          <p className="font-display text-lg text-ink mb-4">OD utilisation by department</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_department}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0000000f" />
                <XAxis dataKey="department" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} unit="%" />
                <Tooltip formatter={(v) => `${v}%`} />
                <Bar dataKey="utilisation_pct" name="Share of OD allowance used" fill="#0F2A4A" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card p-5 mt-6 overflow-x-auto">
        <p className="font-display text-lg text-ink mb-3">Department summary</p>
        <table className="w-full table-clean">
          <thead>
            <tr><th>Department</th><th>Students</th><th>Requests</th><th>Approved</th><th>Rejected</th><th>Awaiting</th><th>Approval rate</th><th>Approved hours</th><th>Utilisation</th><th>Avg. turnaround</th></tr>
          </thead>
          <tbody>
            {data.by_department.map((d) => (
              <tr key={d.department_id}>
                <td className="font-medium">{d.department}<span className="block text-xs text-slate font-normal">{d.department_name}</span></td>
                <td>{d.students.toLocaleString()}</td>
                <td>{d.total_requests.toLocaleString()}</td>
                <td>{d.approved.toLocaleString()}</td>
                <td>{d.rejected.toLocaleString()}</td>
                <td>{d.pending.toLocaleString()}</td>
                <td>{d.approval_rate_pct === null ? "—" : `${d.approval_rate_pct}%`}</td>
                <td>{d.approved_hours.toLocaleString()}</td>
                <td>{d.utilisation_pct}%</td>
                <td>{d.avg_turnaround_hours === null ? "—" : `${d.avg_turnaround_hours}h`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-slate mt-3">{data.note}</p>
      </div>
    </div>
  );
}

export default function AdminODOversight() {
  const [tab, setTab] = useState("queue");
  const [department, setDepartment] = useState("");
  const [state, setState] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "good" | "bad" } | null>(null);

  const scope = useFetch<Scope>("/admin/od/scope");
  const listTab = tab === "queue" || tab === "all";
  const params = new URLSearchParams({ page: String(page), page_size: "8" });
  if (department) params.set("department_id", department);
  if (search.trim()) params.set("q", search.trim());
  if (tab === "all" && state) params.set("state", state);
  const list = useFetch<Page<ODRequest>>(listTab ? `/admin/od/${tab === "queue" ? "queue" : "requests"}?${params}` : null, [], { pollMs: POLL_MS });
  const detail = useFetch<ODRequest>(selected && listTab ? `/admin/od/requests/${selected}` : null, [], { pollMs: POLL_MS });

  const switchTab = (key: string) => { setTab(key); setPage(1); setSelected(null); setShowAudit(false); setMessage(null); };

  const act = async (action: string, done: string) => {
    if (!detail.data) return;
    setBusy(true);
    setMessage(null);
    try {
      await client.post(`/admin/od/requests/${detail.data.id}/${action}`, { version: detail.data.version, comment: comment.trim() || null });
      setMessage({ text: done, tone: "good" });
      setComment("");
    } catch (err) {
      setMessage({ text: errorMessage(err), tone: "bad" });
    } finally {
      setBusy(false);
      detail.refresh();
      list.refresh();
    }
  };

  const req = detail.data;
  const canDecide = !!req && req.state === "UnderHODReview";
  const scopeText = scope.data
    ? scope.data.institution_wide ? "All departments" : `Your department${scope.data.departments.length > 1 ? "s" : ""}: ${scope.data.departments.map((d) => d.code).join(", ")}`
    : "";

  return (
    <div>
      <PageHeader title="OD Oversight" subtitle={`HOD approvals, analytics and audit trail${scopeText ? ` · ${scopeText}` : ""}`} />

      <div className="flex gap-1 flex-wrap mb-5" role="tablist" aria-label="OD oversight sections">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key}
            className={`text-xs px-3 py-1.5 rounded-full border ${tab === t.key ? "bg-navy text-paper border-navy" : "border-black/10 text-slate hover:bg-black/[0.03]"}`}
            onClick={() => switchTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {message && <Banner text={message.text} tone={message.tone} onClose={() => setMessage(null)} />}

      {tab === "analytics" && <AnalyticsView />}
      {tab === "policy" && <PolicyForm />}

      {listTab && (
        <div className="grid xl:grid-cols-5 gap-6 items-start">
          <div className="card p-5 xl:col-span-3">
            <div className="flex gap-2 flex-wrap mb-4">
              <label htmlFor="ao-dept" className="sr-only">Department</label>
              <select id="ao-dept" className="input w-44" value={department} onChange={(e) => { setDepartment(e.target.value); setPage(1); }}>
                <option value="">{scope.data?.institution_wide === false ? "My departments" : "All departments"}</option>
                {(scope.data?.departments || []).map((d) => <option key={d.id} value={d.id}>{d.code}</option>)}
              </select>
              {tab === "all" && (
                <>
                  <label htmlFor="ao-state" className="sr-only">Status</label>
                  <select id="ao-state" className="input w-52" value={state} onChange={(e) => { setState(e.target.value); setPage(1); }}>
                    {STATES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </>
              )}
              <label htmlFor="ao-search" className="sr-only">Search by student, register number or event</label>
              <input id="ao-search" className="input w-60" placeholder="Search student, reg. no. or event" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
            </div>
            {list.loading && !list.data ? (
              <Loading />
            ) : list.error || !list.data ? (
              <ErrorState text={list.error || "Could not load requests."} onRetry={list.reload} />
            ) : list.data.total === 0 ? (
              <EmptyState text={tab === "queue" ? "No requests are waiting for an HOD decision." : "No requests match these filters."} />
            ) : (
              <>
                <RequestTable rows={list.data.items} showStudent selectedId={selected} onSelect={(r) => { setSelected(r.id); setShowAudit(false); setComment(""); setMessage(null); }} />
                <Pagination page={list.data.page} pages={list.data.pages} total={list.data.total} pageSize={list.data.page_size} onPage={setPage} />
              </>
            )}
          </div>

          <div className="xl:col-span-2">
            {!selected ? (
              <EmptyState text="Select a request to see its details and audit log." />
            ) : detail.loading && !req ? (
              <div className="card p-5"><Loading /></div>
            ) : detail.error || !req ? (
              <ErrorState text={detail.error || "Could not load this request."} onRetry={detail.reload} />
            ) : (
              <div className="card p-5">
                <RequestDetail req={req} role="admin" />
                {canDecide && (
                  <div className="mt-5 pt-5 border-t border-black/5">
                    <label htmlFor="ao-comment" className="block text-xs text-slate mb-1">Comment (required to reject)</label>
                    <textarea id="ao-comment" className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
                    <div className="flex gap-2 flex-wrap mt-3">
                      <button className="btn-primary" disabled={busy} onClick={() => act("approve", "Request approved.")}>Approve</button>
                      <button className="btn-secondary text-clay" disabled={busy || !comment.trim()} onClick={() => act("reject", "Request rejected.")}>Reject</button>
                    </div>
                  </div>
                )}
                <div className="mt-5 pt-5 border-t border-black/5">
                  <button className="btn-secondary text-xs py-1.5 px-3" aria-expanded={showAudit} onClick={() => setShowAudit((s) => !s)}>
                    {showAudit ? "Hide audit log" : "View audit log"}
                  </button>
                  {showAudit && <div className="mt-4"><AuditLog requestId={req.id} /></div>}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
