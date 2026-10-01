import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, ErrorState, Pagination } from "../../components/Common";
import type { Page } from "../../components/OD";

interface StudentRow {
  id: number; register_number: string; full_name: string; department: string; department_code: string;
  year: number; semester: number; cgpa: number; email: string;
}

export default function AdminStudents() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (search.trim()) params.set("q", search.trim());
  const { data, loading, error, reload } = useFetch<Page<StudentRow>>(`/admin/students?${params}`);

  return (
    <div>
      <PageHeader
        title="Students"
        subtitle={data ? `${data.total.toLocaleString()} student${data.total === 1 ? "" : "s"}${search.trim() ? " match your search" : " enrolled"}` : undefined}
        action={
          <>
            <label htmlFor="student-search" className="sr-only">Search students</label>
            <input id="student-search" className="input w-64" placeholder="Search by name, reg. no., or dept." value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </>
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
                <th>Register No.</th><th>Name</th><th>Department</th><th>Year / Sem</th><th>CGPA</th><th>Email</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
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
          <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
