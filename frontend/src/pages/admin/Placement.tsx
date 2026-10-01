import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, StatCard, Pill } from "../../components/Common";
import client from "../../api/client";

interface Company { id: number; name: string; role: string; ctc_lpa: number; min_cgpa: number; eligible_departments: string[]; description: string }
interface Drive { id: number; company: Company; drive_date: string; application_deadline: string; status: string; applicants: number }
interface ApplicationRow {
  id: number; student_name: string; register_number: string; department: string; cgpa: number;
  company: string; status: string; applied_on: string;
}
interface Analytics {
  total_applications: number; total_offers: number; average_ctc_lpa: number; highest_ctc_lpa: number;
  department_summary: { department: string; offers: number; avg_ctc_lpa: number; highest_ctc_lpa: number }[];
  status_breakdown: Record<string, number>;
}

const STATUSES = ["Applied", "Shortlisted", "Interview", "Offered", "Rejected"];
const statusTone = (s: string) => (s === "Offered" ? "good" : s === "Rejected" ? "bad" : s === "Applied" ? "neutral" : "warn");

export default function AdminPlacement() {
  const { data: companies, loading: loadingCompanies, reload: reloadCompanies } = useFetch<Company[]>("/placement/companies");
  const { data: drives, loading: loadingDrives, reload: reloadDrives } = useFetch<Drive[]>("/placement/drives");
  const { data: applications, loading: loadingApps, reload: reloadApps } = useFetch<ApplicationRow[]>("/placement/admin/applications");
  const { data: analytics, loading: loadingAnalytics } = useFetch<Analytics>("/placement/admin/analytics");

  const [showCompanyForm, setShowCompanyForm] = useState(false);
  const [showDriveForm, setShowDriveForm] = useState(false);
  const [message, setMessage] = useState("");

  const [companyForm, setCompanyForm] = useState({
    name: "", role: "", ctc_lpa: "", min_cgpa: "", eligible_departments: "CSE", description: "",
  });
  const [driveForm, setDriveForm] = useState({ company_id: "", drive_date: "", application_deadline: "" });

  const submitCompany = async () => {
    try {
      await client.post("/placement/admin/companies", {
        ...companyForm,
        ctc_lpa: Number(companyForm.ctc_lpa),
        min_cgpa: Number(companyForm.min_cgpa),
      });
      setMessage(`Company "${companyForm.name}" added.`);
      setShowCompanyForm(false);
      setCompanyForm({ name: "", role: "", ctc_lpa: "", min_cgpa: "", eligible_departments: "CSE", description: "" });
      reloadCompanies();
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || "Could not add company.");
    }
  };

  const submitDrive = async () => {
    try {
      await client.post("/placement/admin/drives", {
        company_id: Number(driveForm.company_id),
        drive_date: driveForm.drive_date,
        application_deadline: driveForm.application_deadline,
      });
      setMessage("Placement drive created.");
      setShowDriveForm(false);
      setDriveForm({ company_id: "", drive_date: "", application_deadline: "" });
      reloadDrives();
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || "Could not create drive.");
    }
  };

  const updateStatus = async (id: number, status: string) => {
    try {
      await client.patch(`/placement/admin/applications/${id}`, { status });
      reloadApps();
    } catch {
      setMessage("Could not update application status.");
    }
  };

  return (
    <div>
      <PageHeader title="Placement Portal" subtitle="Manage companies, drives, applications, and view placement analytics" />

      {message && <div className="card p-3.5 mb-4 text-sm text-ink bg-brass/10 border-brass/20">{message}</div>}

      {!loadingAnalytics && analytics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Applications" value={analytics.total_applications} accent="navy" />
          <StatCard label="Total Offers" value={analytics.total_offers} accent="leaf" />
          <StatCard label="Average CTC" value={`${analytics.average_ctc_lpa} LPA`} accent="brass" />
          <StatCard label="Highest CTC" value={`${analytics.highest_ctc_lpa} LPA`} accent="brass" />
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="font-display text-lg text-ink">Companies</p>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setShowCompanyForm((s) => !s)}>
              {showCompanyForm ? "Cancel" : "+ Add company"}
            </button>
          </div>
          {showCompanyForm && (
            <div className="space-y-2 mb-4 p-3 rounded-lg bg-black/[0.02]">
              <input className="input" placeholder="Company name" value={companyForm.name} onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })} />
              <input className="input" placeholder="Role" value={companyForm.role} onChange={(e) => setCompanyForm({ ...companyForm, role: e.target.value })} />
              <div className="grid grid-cols-2 gap-2">
                <input className="input" type="number" placeholder="CTC (LPA)" value={companyForm.ctc_lpa} onChange={(e) => setCompanyForm({ ...companyForm, ctc_lpa: e.target.value })} />
                <input className="input" type="number" placeholder="Min. CGPA" value={companyForm.min_cgpa} onChange={(e) => setCompanyForm({ ...companyForm, min_cgpa: e.target.value })} />
              </div>
              <input className="input" placeholder="Eligible depts, e.g. CSE,ECE" value={companyForm.eligible_departments} onChange={(e) => setCompanyForm({ ...companyForm, eligible_departments: e.target.value })} />
              <textarea className="input" placeholder="Description" value={companyForm.description} onChange={(e) => setCompanyForm({ ...companyForm, description: e.target.value })} />
              <button className="btn-primary text-xs py-2 px-3" onClick={submitCompany}>Save company</button>
            </div>
          )}
          {loadingCompanies ? <Loading /> : (
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {(companies || []).map((c) => (
                <div key={c.id} className="text-sm border-b border-black/5 pb-2 last:border-0">
                  <p className="font-medium text-ink">{c.name} — {c.role}</p>
                  <p className="text-xs text-slate">{c.ctc_lpa} LPA · Min CGPA {c.min_cgpa} · {c.eligible_departments.join(", ")}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="font-display text-lg text-ink">Placement Drives</p>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setShowDriveForm((s) => !s)}>
              {showDriveForm ? "Cancel" : "+ New drive"}
            </button>
          </div>
          {showDriveForm && (
            <div className="space-y-2 mb-4 p-3 rounded-lg bg-black/[0.02]">
              <select className="input" value={driveForm.company_id} onChange={(e) => setDriveForm({ ...driveForm, company_id: e.target.value })}>
                <option value="">Select company</option>
                {(companies || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <input className="input" type="date" value={driveForm.drive_date} onChange={(e) => setDriveForm({ ...driveForm, drive_date: e.target.value })} />
                <input className="input" type="date" value={driveForm.application_deadline} onChange={(e) => setDriveForm({ ...driveForm, application_deadline: e.target.value })} />
              </div>
              <button className="btn-primary text-xs py-2 px-3" onClick={submitDrive}>Create drive</button>
            </div>
          )}
          {loadingDrives ? <Loading /> : (
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {(drives || []).map((d) => (
                <div key={d.id} className="flex items-center justify-between text-sm border-b border-black/5 pb-2 last:border-0">
                  <div>
                    <p className="font-medium text-ink">{d.company.name}</p>
                    <p className="text-xs text-slate">{d.drive_date} · {d.applicants} applicants</p>
                  </div>
                  <Pill text={d.status} tone={d.status === "Open" ? "good" : "neutral"} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="font-display text-lg text-ink mb-3">Applications</p>
      {loadingApps ? <Loading /> : !applications || applications.length === 0 ? (
        <EmptyState text="No applications yet." />
      ) : (
        <div className="card p-5 overflow-x-auto">
          <table className="w-full table-clean">
            <thead>
              <tr><th>Student</th><th>Dept</th><th>CGPA</th><th>Company</th><th>Applied</th><th>Status</th></tr>
            </thead>
            <tbody>
              {applications.map((a) => (
                <tr key={a.id}>
                  <td className="font-medium">{a.student_name}<span className="block text-xs text-slate font-normal">{a.register_number}</span></td>
                  <td>{a.department}</td>
                  <td>{a.cgpa}</td>
                  <td>{a.company}</td>
                  <td>{new Date(a.applied_on).toLocaleDateString()}</td>
                  <td>
                    <select className="input py-1 px-2 text-xs w-32" value={a.status} onChange={(e) => updateStatus(a.id, e.target.value)}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
