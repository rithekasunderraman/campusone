import { useEffect, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, Pill } from "../../components/Common";
import client from "../../api/client";

interface Subject { id: number; code: string; name: string }
interface MarkRow {
  mark_id: number; student_id: number; register_number: string; full_name: string;
  internal_1: number; internal_2: number; assignment: number; external: number; total: number; grade: string;
}

const gradeTone = (g: string): "good" | "warn" | "bad" =>
  ["S", "A", "B"].includes(g) ? "good" : ["C", "D"].includes(g) ? "warn" : "bad";

export default function FacultyMarks() {
  const { data: subjects, loading: loadingSubjects } = useFetch<Subject[]>("/faculty/subjects");
  const [subjectId, setSubjectId] = useState<string>("");
  const { data, loading, reload } = useFetch<MarkRow[]>(
    subjectId ? `/faculty/marks?subject_id=${subjectId}` : null,
    [subjectId]
  );
  const [rows, setRows] = useState<MarkRow[]>([]);
  const [saving, setSaving] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (subjects && subjects.length > 0 && !subjectId) setSubjectId(String(subjects[0].id));
  }, [subjects]);

  useEffect(() => {
    setRows(data || []);
  }, [data]);

  const updateRow = (id: number, field: "internal_1" | "internal_2" | "assignment" | "external", value: number) => {
    setRows((rs) => rs.map((r) => (r.mark_id === id ? { ...r, [field]: value } : r)));
  };

  const save = async (row: MarkRow) => {
    setSaving(row.mark_id);
    setMessage("");
    try {
      const res = await client.post("/faculty/marks", {
        mark_id: row.mark_id,
        internal_1: row.internal_1,
        internal_2: row.internal_2,
        assignment: row.assignment,
        external: row.external,
      });
      setMessage(`Updated marks for ${row.full_name}: total ${res.data.total}, grade ${res.data.grade}.`);
      reload();
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || "Could not update marks.");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Marks Entry"
        subtitle="Enter internal, assignment, and external marks per student"
        action={
          <select className="input w-64" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            {(subjects || []).map((s) => (
              <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
            ))}
          </select>
        }
      />

      {message && <div className="card p-3.5 mb-4 text-sm text-ink bg-brass/10 border-brass/20">{message}</div>}

      {loadingSubjects || loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState text="No students found for this subject." />
      ) : (
        <div className="card p-5 overflow-x-auto">
          <table className="w-full table-clean">
            <thead>
              <tr>
                <th>Register No.</th>
                <th>Name</th>
                <th>Internal 1</th>
                <th>Internal 2</th>
                <th>Assignment</th>
                <th>External</th>
                <th>Total</th>
                <th>Grade</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const total = Math.round((r.internal_1 + r.internal_2 + r.assignment + r.external) * 10) / 10;
                return (
                  <tr key={r.mark_id}>
                    <td>{r.register_number}</td>
                    <td className="font-medium">{r.full_name}</td>
                    {(["internal_1", "internal_2", "assignment", "external"] as const).map((field) => (
                      <td key={field}>
                        <input
                          type="number"
                          className="input w-16 py-1.5"
                          value={r[field]}
                          onChange={(e) => updateRow(r.mark_id, field, Number(e.target.value))}
                        />
                      </td>
                    ))}
                    <td className="font-medium">{total}</td>
                    <td><Pill text={r.grade} tone={gradeTone(r.grade)} /></td>
                    <td>
                      <button className="btn-secondary py-1.5 px-3 text-xs" disabled={saving === r.mark_id} onClick={() => save(r)}>
                        {saving === r.mark_id ? "Saving…" : "Save"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
