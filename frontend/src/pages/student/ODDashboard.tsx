import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, StatCard, Loading, EmptyState, ErrorState, Pagination, Banner } from "../../components/Common";
import { ODBalance, ODRequest, Page, RequestTable } from "../../components/OD";

interface BalanceData {
  balance: ODBalance;
  attendance: { threshold_pct: number; overall_pct: number; effective_pct: number; can_miss_overall: number };
  policy: { od_hours_per_semester: number; min_attendance_pct: number; hod_threshold_hours: number; approval_chain: string[] };
  advisor_name: string | null;
  counts: { open: number; needs_action: number; approved: number; rejected: number; draft: number };
}

const FILTERS = [
  { value: "", label: "All requests" },
  { value: "open", label: "Awaiting decision" },
  { value: "ClarificationRequested", label: "Needs my response" },
  { value: "Approved", label: "Approved" },
  { value: "Rejected", label: "Rejected" },
  { value: "Cancelled", label: "Cancelled" },
  { value: "Draft", label: "Drafts" },
];

const POLL_MS = 8000;

export default function StudentODDashboard() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const summary = useFetch<BalanceData>("/student/od/balance", [], { pollMs: POLL_MS });
  const params = new URLSearchParams({ page: String(page), page_size: "8" });
  if (status) params.set("status", status);
  if (search.trim()) params.set("q", search.trim());
  const list = useFetch<Page<ODRequest>>(`/student/od/requests?${params}`, [], { pollMs: POLL_MS });

  const applyButton = (
    <Link to="/student/od/new" className="btn-primary">
      Apply for OD
    </Link>
  );

  if (summary.loading && !summary.data) return <Loading />;
  if (summary.error || !summary.data) return <ErrorState text={summary.error || "Could not load your OD details."} onRetry={summary.reload} />;

  const { balance, attendance, policy, counts, advisor_name } = summary.data;
  const attendanceOk = attendance.effective_pct >= attendance.threshold_pct;

  return (
    <div>
      <PageHeader
        title="On-Duty (OD)"
        subtitle={`Apply for OD and track approvals${advisor_name ? ` · Class advisor: ${advisor_name}` : ""}`}
        action={applyButton}
      />

      {counts.needs_action > 0 && (
        <Banner tone="info" text={`Your class advisor asked for clarification on ${counts.needs_action} request${counts.needs_action > 1 ? "s" : ""}. Open it below to respond.`} />
      )}
      {!attendanceOk && (
        <Banner tone="bad" text={`Your attendance is ${attendance.effective_pct}%, below the ${attendance.threshold_pct}% needed to apply for OD.`} />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Available to request" value={`${balance.available_hours}h`} hint={`of ${balance.allowance_hours}h this semester`} accent="leaf" />
        <StatCard label="Used" value={`${balance.used_hours}h`} hint="Approved OD" accent="navy" />
        <StatCard label="Awaiting decision" value={`${balance.reserved_hours}h`} hint={`${counts.open} open request${counts.open === 1 ? "" : "s"}`} accent="brass" />
        <StatCard label="Attendance" value={`${attendance.effective_pct}%`} hint={`Minimum ${attendance.threshold_pct}% to apply`} accent={attendanceOk ? "leaf" : "clay"} />
      </div>

      <div className="card p-5 mt-6">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
          <p className="font-display text-lg text-ink">My requests</p>
          <div className="flex gap-2 flex-wrap">
            <label className="sr-only" htmlFor="od-status">Filter by status</label>
            <select id="od-status" className="input w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              {FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            <label className="sr-only" htmlFor="od-search">Search by event name</label>
            <input id="od-search" className="input w-56" placeholder="Search by event name" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        </div>

        {list.loading && !list.data ? (
          <Loading />
        ) : list.error || !list.data ? (
          <ErrorState text={list.error || "Could not load your requests."} onRetry={list.reload} />
        ) : list.data.total === 0 ? (
          <EmptyState text={status || search ? "No requests match this filter." : "You have not applied for OD yet. Use “Apply for OD” to start."} />
        ) : (
          <>
            <RequestTable rows={list.data.items} showStudent={false} onSelect={(r) => navigate(`/student/od/${r.id}`)} />
            <Pagination page={list.data.page} pages={list.data.pages} total={list.data.total} pageSize={list.data.page_size} onPage={setPage} />
          </>
        )}
      </div>

      <p className="text-xs text-slate mt-4">
        Policy: {policy.od_hours_per_semester} OD hours per semester · requests longer than {policy.hod_threshold_hours} hours
        {policy.approval_chain.includes("hod") ? " also need HOD approval" : " are decided by your class advisor"} ·
        this page updates automatically.
      </p>
    </div>
  );
}
