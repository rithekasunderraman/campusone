import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Subject { id: number; code: string; name: string }
interface StudentRow {
  id: number; register_number: string; full_name: string; department_code: string;
  year: number; semester: number; cgpa: number; email: string;
}

export default function FacultyStudents() {
  const { data: subjects } = useFetch<Subject[]>("/faculty/subjects");
  const [subjectId, setSubjectId] = useState<string>("");
  const [search, setSearch] = useState("");
  const { data, loading } = useFetch<StudentRow[]>(
    `/faculty/students${subjectId ? `?subject_id=${subjectId}` : ""}`,
    [subjectId]
  );

  const filtered = (data || []).filter(
    (s) => s.full_name.toLowerCase().includes(search.toLowerCase()) || s.register_number.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Student Directory"
        subtitle="Students enrolled across your subjects"
        action={
          <div className="flex gap-2">
            <select className="input w-56" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              <option value="">All my subjects</option>
              {(subjects || []).map((s) => (
                <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
              ))}
            </select>
            <input className="input w-56" placeholder="Search by name or reg. no." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        }
      />
      {loading ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <EmptyState text="No students found." />
      ) : (
        <div className="card p-5">
          <table className="w-full table-clean">
            <thead>
              <tr>
                <th>Register No.</th>
                <th>Name</th>
                <th>Department</th>
                <th>Year / Sem</th>
                <th>CGPA</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td>{s.register_number}</td>
                  <td className="font-medium">{s.full_name}</td>
                  <td>{s.department_code}</td>
                  <td>Y{s.year} / S{s.semester}</td>
                  <td>{s.cgpa}</td>
                  <td className="text-slate">{s.email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
