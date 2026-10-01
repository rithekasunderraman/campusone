import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface StudentRow {
  id: number; register_number: string; full_name: string; department: string; department_code: string;
  year: number; semester: number; cgpa: number; email: string;
}

export default function AdminStudents() {
  const { data, loading } = useFetch<StudentRow[]>("/admin/students");
  const [search, setSearch] = useState("");

  const filtered = (data || []).filter(
    (s) =>
      s.full_name.toLowerCase().includes(search.toLowerCase()) ||
      s.register_number.toLowerCase().includes(search.toLowerCase()) ||
      s.department_code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Students"
        subtitle={data ? `${data.length} students enrolled` : undefined}
        action={<input className="input w-64" placeholder="Search by name, reg. no., or dept." value={search} onChange={(e) => setSearch(e.target.value)} />}
      />
      {loading ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <EmptyState text="No students found." />
      ) : (
        <div className="card p-5 overflow-x-auto">
          <table className="w-full table-clean">
            <thead>
              <tr>
                <th>Register No.</th><th>Name</th><th>Department</th><th>Year / Sem</th><th>CGPA</th><th>Email</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td>{s.register_number}</td>
                  <td className="font-medium">{s.full_name}</td>
                  <td>{s.department}</td>
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
