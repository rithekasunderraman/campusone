import { useEffect, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import type { Page } from "../../components/OD";
import { Pagination, PageHeader, Loading, EmptyState, ProgressBar } from "../../components/Common";
import client from "../../api/client";

interface Subject { id: number; code: string; name: string }
interface AttendanceRow {
  attendance_id: number; student_id: number; register_number: string; full_name: string;
  total_classes: number; attended_classes: number; percentage: number;
}

export default function FacultyAttendance() {
  const { data: subjects, loading: loadingSubjects } = useFetch<Subject[]>("/faculty/subjects");
  const [subjectId, setSubjectId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const query = new URLSearchParams({ subject_id: subjectId, page: String(page), page_size: "25" });
  if (search.trim()) query.set("q", search.trim());
  const { data, loading, refresh } = useFetch<Page<AttendanceRow>>(subjectId ? `/faculty/attendance?${query}` : null);
  const reload = refresh; // after a save, update the rows without flashing the loading state
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [saving, setSaving] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (subjects && subjects.length > 0 && !subjectId) setSubjectId(String(subjects[0].id));
  }, [subjects]);

  useEffect(() => {
    setRows(data?.items || []);
  }, [data]);

  const updateRow = (id: number, field: "total_classes" | "attended_classes", value: number) => {
    setRows((rs) => rs.map((r) => (r.attendance_id === id ? { ...r, [field]: value } : r)));
  };

  const save = async (row: AttendanceRow) => {
    setSaving(row.attendance_id);
    setMessage("");
    try {
      await client.post("/faculty/attendance", {
        attendance_id: row.attendance_id,
        total_classes: row.total_classes,
        attended_classes: row.attended_classes,
      });
      setMessage(`Updated attendance for ${row.full_name}.`);
      reload();
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || "Could not update attendance.");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Attendance Management"
        subtitle="Update attended and total classes per student, per subject"
        action={
          <div className="flex gap-2 flex-wrap">
            <label htmlFor="f-subject" className="sr-only">Subject</label>
            <select id="f-subject" className="input w-64" value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setPage(1); }}>
              {(subjects || []).map((s) => (
                <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
              ))}
            </select>
            <label htmlFor="f-search" className="sr-only">Search students</label>
            <input id="f-search" className="input w-56" placeholder="Search by name or reg. no." value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        }
      />

      {message && <div className="card p-3.5 mb-4 text-sm text-ink bg-brass/10 border-brass/20">{message}</div>}

      {loadingSubjects || (loading && !data) ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState text="No students found for this subject." />
      ) : (
        <div className="card p-5">
          <table className="w-full table-clean">
            <thead>
              <tr>
                <th>Register No.</th>
                <th>Name</th>
                <th>Attended</th>
                <th>Total</th>
                <th>Percentage</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const pct = r.total_classes ? Math.round((r.attended_classes / r.total_classes) * 100) : 0;
                return (
                  <tr key={r.attendance_id}>
                    <td>{r.register_number}</td>
                    <td className="font-medium">{r.full_name}</td>
                    <td>
                      <input
                        type="number"
                        className="input w-20 py-1.5"
                        value={r.attended_classes}
                        onChange={(e) => updateRow(r.attendance_id, "attended_classes", Number(e.target.value))}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        className="input w-20 py-1.5"
                        value={r.total_classes}
                        onChange={(e) => updateRow(r.attendance_id, "total_classes", Number(e.target.value))}
                      />
                    </td>
                    <td className="w-40">
                      <div className="flex items-center gap-2.5">
                        <div className="flex-1"><ProgressBar pct={pct} /></div>
                        <span className="text-xs text-slate w-10">{pct}%</span>
                      </div>
                    </td>
                    <td>
                      <button className="btn-secondary py-1.5 px-3 text-xs" disabled={saving === r.attendance_id} onClick={() => save(r)}>
                        {saving === r.attendance_id ? "Saving…" : "Save"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {data && <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />}
        </div>
      )}
    </div>
  );
}
