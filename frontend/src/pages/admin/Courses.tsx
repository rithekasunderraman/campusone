import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Subject { id: number; code: string; name: string; semester: number; credits: number; faculty_name: string | null }
interface Course { id: number; name: string; department: string; subjects: Subject[] }

export default function AdminCourses() {
  const { data, loading } = useFetch<Course[]>("/admin/courses");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No courses found." />;

  return (
    <div>
      <PageHeader title="Courses & Subjects" subtitle="Programs and their subject curriculum" />
      <div className="space-y-6">
        {data.map((c) => (
          <div key={c.id} className="card p-5">
            <p className="font-display text-lg text-ink">{c.name}</p>
            <p className="text-xs text-slate mt-0.5">{c.department}</p>
            <table className="w-full table-clean mt-4">
              <thead>
                <tr><th>Code</th><th>Subject</th><th>Semester</th><th>Credits</th><th>Faculty</th></tr>
              </thead>
              <tbody>
                {c.subjects.map((s) => (
                  <tr key={s.id}>
                    <td>{s.code}</td>
                    <td className="font-medium">{s.name}</td>
                    <td>{s.semester}</td>
                    <td>{s.credits}</td>
                    <td>{s.faculty_name || "Unassigned"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
