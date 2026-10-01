import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface DeptRow { id: number; name: string; code: string; students: number; faculty: number; courses: number }

export default function AdminDepartments() {
  const { data, loading } = useFetch<DeptRow[]>("/admin/departments");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No departments found." />;

  return (
    <div>
      <PageHeader title="Departments" subtitle="Academic departments across the institution" />
      <div className="grid md:grid-cols-3 gap-4">
        {data.map((d) => (
          <div key={d.id} className="card p-5">
            <p className="text-xs text-brass font-medium">{d.code}</p>
            <p className="font-display text-lg text-ink mt-1">{d.name}</p>
            <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-black/5">
              <div>
                <p className="text-lg font-display text-ink">{d.students}</p>
                <p className="text-xs text-slate">Students</p>
              </div>
              <div>
                <p className="text-lg font-display text-ink">{d.faculty}</p>
                <p className="text-xs text-slate">Faculty</p>
              </div>
              <div>
                <p className="text-lg font-display text-ink">{d.courses}</p>
                <p className="text-xs text-slate">Courses</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
