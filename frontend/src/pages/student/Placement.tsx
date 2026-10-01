import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, Pill } from "../../components/Common";
import client from "../../api/client";

interface Drive {
  id: number;
  company: { name: string; role: string; ctc_lpa: number; min_cgpa: number; description: string };
  drive_date: string;
  application_deadline: string;
  status: string;
  already_applied: boolean;
}

interface Application {
  id: number;
  company: string;
  role: string;
  ctc_lpa: number;
  status: string;
  applied_on: string;
  drive_date: string;
}

const statusTone = (s: string) => (s === "Offered" ? "good" : s === "Rejected" ? "bad" : s === "Applied" ? "neutral" : "warn");

export default function StudentPlacement() {
  const { data: drives, loading: loadingDrives, reload: reloadDrives } = useFetch<Drive[]>("/placement/eligible");
  const { data: apps, loading: loadingApps, reload: reloadApps } = useFetch<Application[]>("/placement/my-applications");
  const [applying, setApplying] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const apply = async (driveId: number) => {
    setApplying(driveId);
    setMessage("");
    try {
      const res = await client.post(`/placement/apply/${driveId}`);
      setMessage(res.data.message);
      reloadDrives();
      reloadApps();
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || "Could not apply to this drive.");
    } finally {
      setApplying(null);
    }
  };

  return (
    <div>
      <PageHeader title="Placement Portal" subtitle="Companies you're eligible for, and your application status" />

      {message && <div className="card p-3.5 mb-4 text-sm text-ink bg-brass/10 border-brass/20">{message}</div>}

      <p className="font-display text-lg text-ink mb-3">Eligible drives</p>
      {loadingDrives ? (
        <Loading />
      ) : !drives || drives.length === 0 ? (
        <EmptyState text="No open drives match your department and CGPA right now." />
      ) : (
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          {drives.map((d) => (
            <div key={d.id} className="card p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-ink">{d.company.name}</p>
                  <p className="text-xs text-slate mt-0.5">{d.company.role}</p>
                </div>
                <span className="font-display text-lg text-brass">{d.company.ctc_lpa} LPA</span>
              </div>
              <p className="text-xs text-slate mt-3">{d.company.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <p className="text-xs text-slate">Apply by <span className="font-medium text-ink">{d.application_deadline}</span></p>
                <button
                  className="btn-primary py-1.5 px-3.5 text-xs"
                  disabled={d.already_applied || applying === d.id}
                  onClick={() => apply(d.id)}
                >
                  {d.already_applied ? "Applied" : applying === d.id ? "Applying…" : "Apply now"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="font-display text-lg text-ink mb-3">My applications</p>
      {loadingApps ? (
        <Loading />
      ) : !apps || apps.length === 0 ? (
        <EmptyState text="You haven't applied to any placement drives yet." />
      ) : (
        <div className="card p-5">
          <table className="w-full table-clean">
            <thead>
              <tr>
                <th>Company</th>
                <th>Role</th>
                <th>CTC</th>
                <th>Applied on</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id}>
                  <td className="font-medium">{a.company}</td>
                  <td>{a.role}</td>
                  <td>{a.ctc_lpa} LPA</td>
                  <td>{new Date(a.applied_on).toLocaleDateString()}</td>
                  <td><Pill text={a.status} tone={statusTone(a.status) as any} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
