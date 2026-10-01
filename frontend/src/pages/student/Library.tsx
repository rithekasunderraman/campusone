import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, Pill } from "../../components/Common";

interface LibRow {
  book_title: string;
  issue_date: string;
  due_date: string;
  return_date: string | null;
  status: string;
}

export default function StudentLibrary() {
  const { data, loading } = useFetch<LibRow[]>("/student/library");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="You have no library records." />;

  return (
    <div>
      <PageHeader title="Library" subtitle="Books issued to you and their return status" />
      <div className="card p-5">
        <table className="w-full table-clean">
          <thead>
            <tr>
              <th>Book</th>
              <th>Issued</th>
              <th>Due</th>
              <th>Returned</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r, i) => (
              <tr key={i}>
                <td className="font-medium">{r.book_title}</td>
                <td>{r.issue_date}</td>
                <td>{r.due_date}</td>
                <td>{r.return_date || "—"}</td>
                <td><Pill text={r.status} tone={r.status === "Returned" ? "good" : r.status === "Overdue" ? "bad" : "warn"} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
