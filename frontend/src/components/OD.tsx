import { useState, type ReactNode } from "react";
import { AlertTriangle, Check, FileText, Info, X } from "lucide-react";
import client from "../api/client";
import { Pill } from "./Common";

// ---------------------------------------------------------------- types

export interface ODFlag {
  code: string;
  severity: "info" | "warning";
  message: string;
  source?: string;
}

export interface ExtractedField {
  value: string | null;
  source: "extracted" | "inferred" | "not_found";
  confidence: "high" | "medium" | "low" | "none";
}

export interface ODDocument {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  extraction_status: string;
  extracted_fields: null | { engine: string; fields: Record<string, ExtractedField> };
  extracted_text_preview: string | null;
}

export interface ODTimelineEntry {
  id: number;
  action: string;
  old_state: string | null;
  new_state: string;
  new_state_label: string;
  actor_role: string;
  actor_name: string;
  comment: string | null;
  at: string;
}

export interface ODRequest {
  id: number;
  version: number;
  state: string;
  state_label: string;
  status: string;
  event_id: number | null;
  event_name: string;
  organizer: string | null;
  venue: string | null;
  start_at: string | null;
  end_at: string | null;
  requested_hours: number;
  approved_hours: number;
  reason: string | null;
  created_at: string | null;
  submitted_at: string | null;
  decided_at: string | null;
  cancelled_at: string | null;
  requires_hod: boolean;
  clarification_requested: boolean;
  clarification_text: string | null;
  clarification_response: string | null;
  decision_comment: string | null;
  student: { id: number; full_name: string; register_number: string; department_code: string; semester: number };
  advisor_name: string | null;
  hod_name: string | null;
  document_count: number;
  allowed_actions: string[];
  flags?: ODFlag[];
  documents?: ODDocument[];
  timeline?: ODTimelineEntry[];
  attendance_credits?: { subject_code: string; subject_name: string; classes: number }[];
  student_balance?: ODBalance;
  student_attendance?: { threshold_pct: number; overall_pct: number; effective_pct: number };
}

export interface ODBalance {
  allowance_hours: number;
  used_hours: number;
  reserved_hours: number;
  remaining_hours: number;
  available_hours: number;
  term_start: string;
  term_end: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ---------------------------------------------------------------- helpers

/** Event times are entered as local wall-clock time. */
export function fmtWhen(start: string | null, end: string | null): string {
  if (!start) return "—";
  const s = new Date(start);
  const day = s.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  const t = (d: Date) => d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (!end) return `${day}, ${t(s)}`;
  const e = new Date(end);
  if (s.toDateString() === e.toDateString()) return `${day}, ${t(s)} – ${t(e)}`;
  return `${day} ${t(s)} – ${e.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${t(e)}`;
}

/** Server timestamps (submitted, decided, audit) are stored in UTC. */
export function fmtStamp(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value.endsWith("Z") ? value : value + "Z");
  return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function errorMessage(err: any, fallback = "Something went wrong. Please try again."): string {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail) && detail[0]?.msg) return detail.map((d: any) => d.msg).join("; ");
  return fallback;
}

export function stateTone(state: string): "neutral" | "good" | "warn" | "bad" {
  if (state === "Approved") return "good";
  if (state === "Rejected") return "bad";
  if (state === "Cancelled" || state === "Draft") return "neutral";
  return "warn";
}

export function StatePill({ req }: { req: { state: string; state_label: string } }) {
  return <Pill text={req.state_label} tone={stateTone(req.state)} />;
}

export async function openDocument(doc: { id: number }) {
  const res = await client.get(`/od/documents/${doc.id}`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  window.open(url, "_blank", "noopener");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

const ACTION_LABELS: Record<string, string> = {
  create: "Draft created",
  submit: "Submitted",
  route_to_faculty: "Sent to class advisor",
  request_clarification: "Clarification requested",
  respond_clarification: "Student responded",
  forward_to_hod: "Recommended and sent to HOD",
  approve: "Approved",
  reject: "Rejected",
  cancel: "Cancelled by student",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action;
}

// ---------------------------------------------------------------- progress + timeline

/** Where a request is on its way to a decision. */
export function ProgressSteps({ req }: { req: ODRequest }) {
  const steps = ["Submitted", "Class advisor", ...(req.requires_hod ? ["HOD"] : []), "Decision"];
  const position: Record<string, number> = {
    Draft: -1,
    Submitted: 0,
    UnderFacultyReview: 1,
    ClarificationRequested: 1,
    Resubmitted: 1,
    UnderHODReview: 2,
    Approved: steps.length - 1,
    Rejected: steps.length - 1,
    Cancelled: steps.length - 1,
  };
  const current = Math.min(position[req.state] ?? 0, steps.length - 1);
  const closed = ["Approved", "Rejected", "Cancelled"].includes(req.state);
  const last = req.state === "Approved" ? "Approved" : req.state === "Rejected" ? "Rejected" : req.state === "Cancelled" ? "Cancelled" : "Decision";
  return (
    <ol className="flex items-center gap-2 flex-wrap" aria-label={`Progress: ${req.state_label}`}>
      {steps.map((label, i) => {
        const done = i < current || (closed && i <= current);
        const active = i === current && !closed;
        const bad = closed && i === steps.length - 1 && req.state !== "Approved";
        const dot = bad ? "bg-clay text-white" : done ? "bg-leaf text-white" : active ? "bg-brass text-white" : "bg-black/10 text-slate";
        return (
          <li key={label} className="flex items-center gap-2">
            <span className={`h-6 w-6 rounded-full flex items-center justify-center text-[11px] font-medium ${dot}`} aria-hidden="true">
              {bad ? <X size={13} /> : done ? <Check size={13} /> : i + 1}
            </span>
            <span className={`text-xs ${active || done ? "text-ink font-medium" : "text-slate"}`}>
              {i === steps.length - 1 ? last : label}
              {active && req.state === "ClarificationRequested" ? " (waiting for you)" : ""}
            </span>
            {i < steps.length - 1 && <span className="w-6 h-px bg-black/15" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

export function Timeline({ entries }: { entries: ODTimelineEntry[] }) {
  if (!entries.length) {
    return <p className="text-sm text-slate">Imported from the earlier OD records — no step-by-step history was kept for this request.</p>;
  }
  return (
    <ol className="space-y-3">
      {entries.map((e) => (
        <li key={e.id} className="flex gap-3">
          <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${e.new_state === "Approved" ? "bg-leaf" : e.new_state === "Rejected" ? "bg-clay" : "bg-brass"}`} aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-sm text-ink">
              <span className="font-medium">{actionLabel(e.action)}</span>
              <span className="text-slate"> · {e.actor_name}{e.actor_role !== "system" ? ` (${e.actor_role === "admin" ? "HOD / admin" : e.actor_role})` : ""}</span>
            </p>
            <p className="text-xs text-slate">{fmtStamp(e.at)}</p>
            {e.comment && <p className="text-sm text-ink mt-1 bg-black/[0.03] rounded-lg px-3 py-2">“{e.comment}”</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------- documents + flags

const FIELD_LABELS: Record<string, string> = { event_name: "Event", organizer: "Organiser", date: "Date", venue: "Venue" };

function extractionLabel(status: string): { text: string; tone: "neutral" | "good" | "warn" | "bad" } {
  switch (status) {
    case "done":
      return { text: "Text read", tone: "good" };
    case "pending":
    case "processing":
      return { text: "Reading…", tone: "warn" };
    case "needs_ocr":
      return { text: "Image – not machine-read", tone: "neutral" };
    case "no_text":
      return { text: "No readable text", tone: "neutral" };
    default:
      return { text: "Could not be read", tone: "bad" };
  }
}

export function DocumentList({ docs, showExtraction }: { docs: ODDocument[]; showExtraction: boolean }) {
  const [busy, setBusy] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  if (!docs.length) return <p className="text-sm text-slate">No supporting document was attached.</p>;
  return (
    <div className="space-y-3">
      {failed && <p className="text-xs text-clay" role="alert">The document could not be opened.</p>}
      {docs.map((d) => {
        const ex = extractionLabel(d.extraction_status);
        return (
          <div key={d.id} className="border border-black/5 rounded-lg p-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <button
                className="flex items-center gap-2 text-sm text-navy font-medium hover:underline text-left"
                disabled={busy === d.id}
                onClick={async () => {
                  setBusy(d.id);
                  setFailed(false);
                  try {
                    await openDocument(d);
                  } catch {
                    setFailed(true);
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                <FileText size={15} aria-hidden="true" />
                {d.filename}
                <span className="text-xs text-slate font-normal">({Math.max(1, Math.round(d.size_bytes / 1024))} KB)</span>
              </button>
              <Pill text={ex.text} tone={ex.tone} />
            </div>
            {showExtraction && d.extracted_fields && (
              <div className="mt-3">
                <p className="text-[11px] uppercase tracking-wide text-slate mb-1.5">
                  Read from the document ({d.extracted_fields.engine === "llm" ? "AI reading" : "automatic text matching"})
                </p>
                <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                  {Object.entries(d.extracted_fields.fields).map(([key, f]) => (
                    <div key={key} className="flex items-baseline justify-between gap-2 border-b border-black/5 pb-1">
                      <dt className="text-slate text-xs">{FIELD_LABELS[key] || key}</dt>
                      <dd className="text-right">
                        <span className="text-ink">{f.value || "Not found"}</span>
                        {f.value && (
                          <span className="block text-[11px] text-slate">
                            {f.source === "extracted" ? "stated in document" : "inferred"} · {f.confidence} confidence
                          </span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function FlagList({ flags }: { flags: ODFlag[] }) {
  if (!flags.length) return null;
  return (
    <div className="rounded-lg border border-brass/30 bg-brass/10 p-3" role="note" aria-label="Automatic review notes">
      <p className="text-xs font-medium text-ink mb-2">Automatic checks — for your review only, no decision has been made</p>
      <ul className="space-y-1.5">
        {flags.map((f, i) => (
          <li key={i} className="flex gap-2 text-sm text-ink">
            {f.severity === "warning" ? (
              <AlertTriangle size={15} className="text-clay shrink-0 mt-0.5" aria-label="Warning" />
            ) : (
              <Info size={15} className="text-slate shrink-0 mt-0.5" aria-label="Note" />
            )}
            <span>{f.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- detail

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate">{label}</dt>
      <dd className="text-sm text-ink mt-0.5">{children}</dd>
    </div>
  );
}

/** Read-only view of one request, shared by the student, faculty and admin pages. */
export function RequestDetail({ req, role }: { req: ODRequest; role: "student" | "faculty" | "admin" }) {
  const approver = role !== "student";
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="font-display text-xl text-ink">{req.event_name}</p>
          <p className="text-xs text-slate mt-0.5">
            Request #{req.id}
            {approver && ` · ${req.student.full_name} (${req.student.register_number}, ${req.student.department_code})`}
          </p>
        </div>
        <StatePill req={req} />
      </div>

      <ProgressSteps req={req} />

      {approver && req.flags && <FlagList flags={req.flags} />}

      <dl className="grid sm:grid-cols-2 gap-4">
        <Field label="When">{fmtWhen(req.start_at, req.end_at)}</Field>
        <Field label="Hours">
          {req.requested_hours} requested{req.state === "Approved" ? ` · ${req.approved_hours} approved` : ""}
        </Field>
        <Field label="Organiser">{req.organizer || "—"}</Field>
        <Field label="Venue">{req.venue || "—"}</Field>
        <Field label="Class advisor">{req.advisor_name || "—"}</Field>
        <Field label="Approval route">{req.requires_hod ? `Class advisor, then HOD${req.hod_name ? ` (${req.hod_name})` : ""}` : "Class advisor"}</Field>
        <div className="sm:col-span-2">
          <Field label="Purpose">{req.reason || "—"}</Field>
        </div>
      </dl>

      {approver && req.student_balance && req.student_attendance && (
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-black/[0.03] p-3">
            <p className="text-xs text-slate">Student's OD balance</p>
            <p className="text-ink mt-0.5">
              {req.student_balance.remaining_hours}h left of {req.student_balance.allowance_hours}h
              <span className="text-slate"> · {req.student_balance.used_hours}h used</span>
            </p>
          </div>
          <div className="rounded-lg bg-black/[0.03] p-3">
            <p className="text-xs text-slate">Student's attendance</p>
            <p className={req.student_attendance.effective_pct >= req.student_attendance.threshold_pct ? "text-ink mt-0.5" : "text-clay mt-0.5"}>
              {req.student_attendance.effective_pct}%
              <span className="text-slate"> · minimum {req.student_attendance.threshold_pct}%</span>
            </p>
          </div>
        </div>
      )}

      {req.clarification_text && (
        <div className="rounded-lg border border-black/10 p-3 text-sm">
          <p className="text-xs text-slate">Clarification asked by the class advisor</p>
          <p className="text-ink mt-0.5">{req.clarification_text}</p>
          {req.clarification_response && (
            <>
              <p className="text-xs text-slate mt-2">Student's response</p>
              <p className="text-ink mt-0.5">{req.clarification_response}</p>
            </>
          )}
        </div>
      )}

      {req.decision_comment && (
        <div className={`rounded-lg p-3 text-sm ${req.state === "Rejected" ? "bg-clay/10" : "bg-leaf/10"}`}>
          <p className="text-xs text-slate">{req.state === "Rejected" ? "Reason for rejection" : "Approver's note"}</p>
          <p className="text-ink mt-0.5">{req.decision_comment}</p>
        </div>
      )}

      {req.attendance_credits && req.attendance_credits.length > 0 && (
        <div>
          <p className="text-sm font-medium text-ink mb-1.5">Attendance credited</p>
          <p className="text-sm text-slate">
            {req.attendance_credits.map((c) => `${c.subject_code} (${c.classes} class${c.classes > 1 ? "es" : ""})`).join(", ")}
          </p>
        </div>
      )}

      <div>
        <p className="text-sm font-medium text-ink mb-2">Supporting documents</p>
        <DocumentList docs={req.documents || []} showExtraction />
      </div>

      <div>
        <p className="text-sm font-medium text-ink mb-2">Status timeline</p>
        <Timeline entries={req.timeline || []} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- table

export function RequestTable({
  rows,
  showStudent,
  selectedId,
  onSelect,
}: {
  rows: ODRequest[];
  showStudent: boolean;
  selectedId?: number | null;
  onSelect: (req: ODRequest) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-clean">
        <thead>
          <tr>
            {showStudent && <th>Student</th>}
            <th>Event</th>
            <th>When</th>
            <th>Hours</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              className={`cursor-pointer hover:bg-black/[0.02] ${selectedId === r.id ? "bg-brass/10" : ""}`}
              onClick={() => onSelect(r)}
            >
              {showStudent && (
                <td className="font-medium">
                  {r.student.full_name}
                  <span className="block text-xs text-slate font-normal">
                    {r.student.register_number} · {r.student.department_code}
                  </span>
                </td>
              )}
              <td>
                <button
                  className="text-left text-navy hover:underline font-medium"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(r);
                  }}
                >
                  {r.event_name}
                </button>
                {r.flags && r.flags.some((f) => f.severity === "warning") && (
                  <span className="ml-2 inline-flex items-center gap-1 text-[11px] text-clay">
                    <AlertTriangle size={12} aria-hidden="true" /> check
                  </span>
                )}
                <span className="block text-xs text-slate">#{r.id}{r.document_count ? ` · ${r.document_count} document${r.document_count > 1 ? "s" : ""}` : ""}</span>
              </td>
              <td className="whitespace-nowrap">{fmtWhen(r.start_at, r.end_at)}</td>
              <td>{r.requested_hours}</td>
              <td>
                <StatePill req={r} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
