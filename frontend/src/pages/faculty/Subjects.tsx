import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface Subject {
  id: number;
  code: string;
  name: string;
  semester: number;
  credits: number;
  faculty_name: string | null;
}

export default function FacultySubjects() {
  const { data, loading } = useFetch<Subject[]>("/faculty/subjects");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No subjects assigned to you yet." />;

  return (
    <div>
      <PageHeader title="My Subjects" subtitle="Subjects you are currently teaching" />
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.map((s) => (
          <div key={s.id} className="card p-5">
            <p className="text-xs text-brass font-medium">{s.code}</p>
            <p className="font-display text-lg text-ink mt-1">{s.name}</p>
            <p className="text-xs text-slate mt-2">Semester {s.semester} · {s.credits} credits</p>
          </div>
        ))}
      </div>
    </div>
  );
}
