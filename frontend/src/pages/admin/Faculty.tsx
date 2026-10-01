import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface FacultyRow {
  id: number; employee_code: string; full_name: string; designation: string;
  department: string; office: string; subjects_count: number; email: string;
}

export default function AdminFaculty() {
  const { data, loading } = useFetch<FacultyRow[]>("/admin/faculty");
  const [search, setSearch] = useState("");

  const filtered = (data || []).filter(
    (f) => f.full_name.toLowerCase().includes(search.toLowerCase()) || f.department.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Faculty"
        subtitle={data ? `${data.length} faculty members` : undefined}
        action={<input className="input w-64" placeholder="Search by name or department" value={search} onChange={(e) => setSearch(e.target.value)} />}
      />
      {loading ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <EmptyState text="No faculty found." />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((f) => (
            <div key={f.id} className="card p-5">
              <p className="font-display text-lg text-ink">{f.full_name}</p>
              <p className="text-xs text-slate mt-1">{f.designation} · {f.department}</p>
              <div className="mt-3 pt-3 border-t border-black/5 text-xs text-slate space-y-1">
                <p>Employee code: <span className="text-ink font-medium">{f.employee_code}</span></p>
                <p>Office: <span className="text-ink font-medium">{f.office}</span></p>
                <p>Subjects taught: <span className="text-ink font-medium">{f.subjects_count}</span></p>
                <p>Email: <span className="text-ink font-medium">{f.email}</span></p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
