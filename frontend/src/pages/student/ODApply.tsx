import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, X } from "lucide-react";
import client from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, Banner, Pill } from "../../components/Common";
import { ODBalance, errorMessage, fmtWhen } from "../../components/OD";

interface ClubEvent { event_id: number; title: string; club_name: string; date: string; start_time: string; end_time: string; venue: string }
interface Eligibility {
  eligible: boolean;
  checks: { code: string; ok: boolean; message: string }[];
  balance: ODBalance;
  attendance: { threshold_pct: number; effective_pct: number };
  requires_hod: boolean;
  approval_route: string[];
  classes_affected: number;
  explanation: string;
}

const STEPS = ["Event details", "Document", "Eligibility", "Review & submit"];
const CHECK_TITLES: Record<string, string> = {
  dates: "Dates", hours: "Hours", balance: "OD balance", duplicate: "Duplicate request", overlap: "Overlap", attendance: "Attendance",
};

const empty = { event_id: "", event_name: "", organizer: "", venue: "", start_at: "", end_at: "", requested_hours: "", reason: "" };

function hoursBetween(a: string, b: string): string {
  if (!a || !b) return "";
  const h = (new Date(b).getTime() - new Date(a).getTime()) / 3_600_000;
  return h > 0 ? String(Math.round(h * 2) / 2) : "";
}

export default function StudentODApply() {
  const navigate = useNavigate();
  const { data: events } = useFetch<ClubEvent[]>("/student/od/events");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(empty);
  const [file, setFile] = useState<File | null>(null);
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (patch: Partial<typeof empty>) => setForm((f) => ({ ...f, ...patch }));

  const pickEvent = (id: string) => {
    const ev = (events || []).find((e) => String(e.event_id) === id);
    if (!ev) return set({ event_id: "" });
    const start = `${ev.date}T${ev.start_time || "09:00"}`;
    const end = `${ev.date}T${ev.end_time || "17:00"}`;
    set({ event_id: id, event_name: ev.title, organizer: ev.club_name, venue: ev.venue || "", start_at: start, end_at: end, requested_hours: hoursBetween(start, end) });
  };

  const detailsProblem = (): string => {
    if (!form.event_name.trim()) return "Enter the event name.";
    if (!form.start_at || !form.end_at) return "Enter the start and end date and time.";
    if (new Date(form.end_at) <= new Date(form.start_at)) return "The end must be after the start.";
    if (!(Number(form.requested_hours) > 0)) return "Enter the number of OD hours you need.";
    if (!form.reason.trim()) return "Say briefly why you need OD for this event.";
    return "";
  };

  // Eligibility is recalculated by the server every time the student reaches that step.
  useEffect(() => {
    if (step !== 2) return;
    setChecking(true);
    setError("");
    client
      .post("/student/od/eligibility", {
        start_at: form.start_at, end_at: form.end_at, requested_hours: Number(form.requested_hours),
        event_id: form.event_id ? Number(form.event_id) : null, event_name: form.event_name,
      })
      .then((res) => setEligibility(res.data))
      .catch((err) => setError(errorMessage(err, "Eligibility could not be checked.")))
      .finally(() => setChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const next = () => {
    if (step === 0) {
      const problem = detailsProblem();
      if (problem) return setError(problem);
    }
    setError("");
    setStep((s) => s + 1);
  };

  const send = async (submit: boolean) => {
    setBusy(true);
    setError("");
    const body = new FormData();
    Object.entries(form).forEach(([k, v]) => v !== "" && body.append(k, v));
    body.append("submit", submit ? "true" : "false");
    if (file) body.append("file", file);
    try {
      const res = await client.post("/student/od/requests", body);
      navigate(`/student/od/${res.data.id}`);
    } catch (err) {
      setError(errorMessage(err, "The request could not be saved."));
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Apply for OD" subtitle="Four short steps — nothing is sent until you submit" action={<Link to="/student/od" className="btn-secondary">Cancel</Link>} />

      <ol className="flex items-center gap-2 flex-wrap mb-5" aria-label="Application steps">
        {STEPS.map((label, i) => (
          <li key={label} className="flex items-center gap-2" aria-current={i === step ? "step" : undefined}>
            <span className={`h-6 w-6 rounded-full flex items-center justify-center text-[11px] font-medium ${i < step ? "bg-leaf text-white" : i === step ? "bg-navy text-paper" : "bg-black/10 text-slate"}`}>
              {i < step ? <Check size={13} aria-hidden="true" /> : i + 1}
            </span>
            <span className={`text-xs ${i === step ? "text-ink font-medium" : "text-slate"}`}>{label}</span>
            {i < STEPS.length - 1 && <span className="w-6 h-px bg-black/15" aria-hidden="true" />}
          </li>
        ))}
      </ol>

      {error && <Banner text={error} tone="bad" onClose={() => setError("")} />}

      <div className="card p-6">
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <label htmlFor="od-event" className="block text-xs text-slate mb-1">Club event (optional)</label>
              <select id="od-event" className="input" value={form.event_id} onChange={(e) => pickEvent(e.target.value)}>
                <option value="">Another event — I will type the details</option>
                {(events || []).map((e) => (
                  <option key={e.event_id} value={e.event_id}>{e.date} · {e.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="od-name" className="block text-xs text-slate mb-1">Event name</label>
              <input id="od-name" className="input" value={form.event_name} onChange={(e) => set({ event_name: e.target.value, event_id: "" })} required />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="od-org" className="block text-xs text-slate mb-1">Organiser</label>
                <input id="od-org" className="input" value={form.organizer} onChange={(e) => set({ organizer: e.target.value })} />
              </div>
              <div>
                <label htmlFor="od-venue" className="block text-xs text-slate mb-1">Venue</label>
                <input id="od-venue" className="input" value={form.venue} onChange={(e) => set({ venue: e.target.value })} />
              </div>
              <div>
                <label htmlFor="od-start" className="block text-xs text-slate mb-1">Starts</label>
                <input id="od-start" type="datetime-local" className="input" value={form.start_at}
                  onChange={(e) => set({ start_at: e.target.value, requested_hours: hoursBetween(e.target.value, form.end_at) || form.requested_hours })} required />
              </div>
              <div>
                <label htmlFor="od-end" className="block text-xs text-slate mb-1">Ends</label>
                <input id="od-end" type="datetime-local" className="input" value={form.end_at}
                  onChange={(e) => set({ end_at: e.target.value, requested_hours: hoursBetween(form.start_at, e.target.value) || form.requested_hours })} required />
              </div>
              <div>
                <label htmlFor="od-hours" className="block text-xs text-slate mb-1">OD hours needed</label>
                <input id="od-hours" type="number" min="0.5" step="0.5" className="input" value={form.requested_hours} onChange={(e) => set({ requested_hours: e.target.value })} required />
              </div>
            </div>
            <div>
              <label htmlFor="od-reason" className="block text-xs text-slate mb-1">Purpose</label>
              <textarea id="od-reason" className="input" rows={3} value={form.reason} onChange={(e) => set({ reason: e.target.value })} placeholder="What you will be doing at the event" required />
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <p className="font-display text-lg text-ink">Supporting document</p>
            <p className="text-sm text-slate mt-1">
              Optional but recommended: an invitation, registration confirmation or circular. PDF, PNG, JPEG, WEBP or text, up to 5 MB.
              The event name, date and venue in the document are compared with what you entered, and differences are shown to your approver.
            </p>
            <label htmlFor="od-file" className="block text-xs text-slate mt-4 mb-1">Choose a file</label>
            <input id="od-file" type="file" className="input" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            {file && (
              <p className="text-sm text-ink mt-3">
                Selected: <span className="font-medium">{file.name}</span> ({Math.max(1, Math.round(file.size / 1024))} KB){" "}
                <button className="text-xs text-clay underline ml-2" onClick={() => setFile(null)}>Remove</button>
              </p>
            )}
          </div>
        )}

        {step === 2 && (
          <div>
            <p className="font-display text-lg text-ink">Eligibility and balance</p>
            {checking || !eligibility ? (
              <Loading />
            ) : (
              <>
                <div className={`rounded-lg p-3 mt-3 text-sm ${eligibility.eligible ? "bg-leaf/10" : "bg-clay/10"}`} role="status">
                  <p className="font-medium text-ink">{eligibility.eligible ? "You can submit this request." : "This request cannot be submitted yet."}</p>
                  <p className="text-ink mt-1">{eligibility.explanation}</p>
                </div>
                <ul className="mt-4 space-y-2">
                  {eligibility.checks.map((c) => (
                    <li key={c.code} className="flex gap-3 text-sm">
                      <span className={`mt-0.5 h-5 w-5 rounded-full flex items-center justify-center shrink-0 ${c.ok ? "bg-leaf text-white" : "bg-clay text-white"}`}>
                        {c.ok ? <Check size={12} aria-label="Passed" /> : <X size={12} aria-label="Failed" />}
                      </span>
                      <span>
                        <span className="font-medium text-ink">{CHECK_TITLES[c.code] || c.code}: </span>
                        <span className={c.ok ? "text-slate" : "text-clay"}>{c.message}</span>
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="grid sm:grid-cols-3 gap-3 mt-5 text-sm">
                  <div className="rounded-lg bg-black/[0.03] p-3">
                    <p className="text-xs text-slate">Balance after this request</p>
                    <p className="text-ink mt-0.5">{Math.max(0, eligibility.balance.available_hours - Number(form.requested_hours))}h of {eligibility.balance.allowance_hours}h</p>
                  </div>
                  <div className="rounded-lg bg-black/[0.03] p-3">
                    <p className="text-xs text-slate">Approval route</p>
                    <p className="text-ink mt-0.5">{eligibility.approval_route.join(" → ")}</p>
                  </div>
                  <div className="rounded-lg bg-black/[0.03] p-3">
                    <p className="text-xs text-slate">Classes covered by this OD</p>
                    <p className="text-ink mt-0.5">{eligibility.classes_affected}</p>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="flex items-center justify-between gap-3">
              <p className="font-display text-lg text-ink">Review</p>
              {eligibility && <Pill text={eligibility.eligible ? "Eligible" : "Not eligible"} tone={eligibility.eligible ? "good" : "bad"} />}
            </div>
            <dl className="grid sm:grid-cols-2 gap-4 mt-4 text-sm">
              <div><dt className="text-xs text-slate">Event</dt><dd className="text-ink">{form.event_name}</dd></div>
              <div><dt className="text-xs text-slate">When</dt><dd className="text-ink">{fmtWhen(form.start_at, form.end_at)}</dd></div>
              <div><dt className="text-xs text-slate">Organiser</dt><dd className="text-ink">{form.organizer || "—"}</dd></div>
              <div><dt className="text-xs text-slate">Venue</dt><dd className="text-ink">{form.venue || "—"}</dd></div>
              <div><dt className="text-xs text-slate">OD hours</dt><dd className="text-ink">{form.requested_hours}</dd></div>
              <div><dt className="text-xs text-slate">Document</dt><dd className="text-ink">{file ? file.name : "None attached"}</dd></div>
              <div className="sm:col-span-2"><dt className="text-xs text-slate">Purpose</dt><dd className="text-ink">{form.reason}</dd></div>
              <div className="sm:col-span-2"><dt className="text-xs text-slate">Goes to</dt><dd className="text-ink">{eligibility ? eligibility.approval_route.join(" → ") : "Class advisor"}</dd></div>
            </dl>
            {eligibility && !eligibility.eligible && (
              <p className="text-sm text-clay mt-4">This request does not meet the rules yet, so it cannot be submitted. You can save it as a draft or go back and change it.</p>
            )}
          </div>
        )}

        <div className="mt-6 pt-5 border-t border-black/5 flex items-center justify-between gap-3 flex-wrap">
          <button className="btn-secondary" disabled={step === 0 || busy} onClick={() => { setError(""); setStep((s) => s - 1); }}>Back</button>
          {step < 3 ? (
            <button className="btn-primary" onClick={next} disabled={step === 2 && checking}>Continue</button>
          ) : (
            <div className="flex gap-2">
              <button className="btn-secondary" disabled={busy} onClick={() => send(false)}>Save as draft</button>
              <button className="btn-primary" disabled={busy || !eligibility?.eligible} onClick={() => send(true)}>
                {busy ? "Submitting…" : "Submit request"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
