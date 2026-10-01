import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, ErrorState, Pagination } from "../../components/Common";
import type { Page } from "../../components/OD";

interface Subject { id: number; code: string; name: string }
interface StudentRow {
  id: number; register_number: string; full_name: string; department_code: string;
  year: number; semester: number; cgpa: number; email: string;
}

export default function FacultyStudents() {
  const { data: subjects } = useFetch<Subject[]>("/faculty/subjects");
  const [subjectId, setSubjectId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (subjectId) params.set("subject_id", subjectId);
  if (search.trim()) params.set("q", search.trim());
  const { data, loading, error, reload } = useFetch<Page<StudentRow>>(`/faculty/students?${params}`);

  return (
    <div>
      <PageHeader
        title="Student Directory"
        subtitle={data ? `${data.total.toLocaleString()} student${data.total === 1 ? "" : "s"} across your subjects` : "Students enrolled across your subjects"}
        action={
          <div className="flex gap-2 flex-wrap">
            <label htmlFor="fs-subject" className="sr-only">Subject</label>
            <select id="fs-subject" className="input w-56" value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setPage(1); }}>
              <option value="">All my subjects</option>
              {(subjects || []).map((s) => (
                <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
              ))}
            </select>
            <label htmlFor="fs-search" className="sr-only">Search students</label>
            <input id="fs-search" className="input w-56" placeholder="Search by name or reg. no." value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        }
      />
      {loading && !data ? (
        <Loading />
      ) : error || !data ? (
        <ErrorState text={error || "Could not load students."} onRetry={reload} />
      ) : data.total === 0 ? (
        <EmptyState text="No students found." />
      ) : (
        <div className="card p-5 overflow-x-auto">
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
              {data.items.map((s) => (
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
          <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
