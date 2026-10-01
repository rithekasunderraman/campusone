import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, ErrorState, Pagination } from "../../components/Common";
import type { Page } from "../../components/OD";

interface FacultyRow {
  id: number; employee_code: string; full_name: string; designation: string;
  department: string; office: string; subjects_count: number; email: string;
}

export default function AdminFaculty() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "24" });
  if (search.trim()) params.set("q", search.trim());
  const { data, loading, error, reload } = useFetch<Page<FacultyRow>>(`/admin/faculty?${params}`);

  return (
    <div>
      <PageHeader
        title="Faculty"
        subtitle={data ? `${data.total.toLocaleString()} faculty member${data.total === 1 ? "" : "s"}${search.trim() ? " match your search" : ""}` : undefined}
        action={
          <>
            <label htmlFor="faculty-search" className="sr-only">Search faculty</label>
            <input id="faculty-search" className="input w-64" placeholder="Search by name, department or code" value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </>
        }
      />
      {loading && !data ? (
        <Loading />
      ) : error || !data ? (
        <ErrorState text={error || "Could not load faculty."} onRetry={reload} />
      ) : data.total === 0 ? (
        <EmptyState text="No faculty found." />
      ) : (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((f) => (
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
          <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
        </>
      )}
    </div>
  );
}
