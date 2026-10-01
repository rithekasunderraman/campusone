import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import client from "../../api/client";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, ErrorState, Banner } from "../../components/Common";
import { ODRequest, RequestDetail, errorMessage } from "../../components/OD";

export default function StudentODDetail() {
  const { id } = useParams();
  const { data: req, loading, error, reload, refresh } = useFetch<ODRequest>(`/student/od/requests/${id}`, [], { pollMs: 6000 });
  const [message, setMessage] = useState<{ text: string; tone: "good" | "bad" } | null>(null);
  const [response, setResponse] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  if (loading && !req) return <Loading />;
  if (error || !req) return <ErrorState text={error || "This request could not be loaded."} onRetry={reload} />;

  const act = async (path: string, body: object, done: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await client.post(`/student/od/requests/${req.id}/${path}`, { version: req.version, ...body });
      setMessage({ text: done, tone: "good" });
      setResponse("");
    } catch (err) {
      setMessage({ text: errorMessage(err), tone: "bad" });
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const upload = async (file: File) => {
    setBusy(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    try {
      await client.post(`/student/od/requests/${req.id}/documents`, form);
      setMessage({ text: "Document added.", tone: "good" });
    } catch (err) {
      setMessage({ text: errorMessage(err, "The document could not be uploaded."), tone: "bad" });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    }
  };

  const can = (action: string) => req.allowed_actions.includes(action);
  const open = !["Approved", "Rejected", "Cancelled"].includes(req.state);

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="OD request"
        subtitle="Status updates appear here automatically"
        action={<Link to="/student/od" className="btn-secondary">Back to my requests</Link>}
      />
      {message && <Banner text={message.text} tone={message.tone} onClose={() => setMessage(null)} />}

      {can("respond_clarification") && (
        <div className="card p-5 mb-4 border-brass/40">
          <p className="font-display text-lg text-ink">Your class advisor needs more information</p>
          <p className="text-sm text-ink mt-1 bg-black/[0.03] rounded-lg px-3 py-2">“{req.clarification_text}”</p>
          <label htmlFor="clarify" className="block text-xs text-slate mt-3 mb-1">Your response</label>
          <textarea id="clarify" className="input" rows={3} value={response} onChange={(e) => setResponse(e.target.value)} />
          <p className="text-xs text-slate mt-1">You can also attach a document below before responding.</p>
          <button
            className="btn-primary mt-3"
            disabled={busy || !response.trim()}
            onClick={() => act("clarification-response", { response }, "Response sent to your class advisor.")}
          >
            Send response
          </button>
        </div>
      )}

      <div className="card p-6">
        <RequestDetail req={req} role="student" />

        {open && (
          <div className="mt-6 pt-5 border-t border-black/5 flex items-center gap-3 flex-wrap">
            {can("submit") && (
              <button className="btn-primary" disabled={busy} onClick={() => act("submit", {}, "Request submitted to your class advisor.")}>
                Submit request
              </button>
            )}
            <div>
              <label htmlFor="add-doc" className="btn-secondary cursor-pointer">Add a document</label>
              <input
                id="add-doc"
                ref={fileRef}
                type="file"
                className="sr-only"
                accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
                disabled={busy}
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
              />
            </div>
            {can("cancel") && (
              <button
                className="btn-secondary text-clay"
                disabled={busy}
                onClick={() => {
                  if (window.confirm("Cancel this OD request? This cannot be undone.")) act("cancel", {}, "Request cancelled.");
                }}
              >
                Cancel request
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
