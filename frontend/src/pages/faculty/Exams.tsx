import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState } from "../../components/Common";

interface ExamRow {
  subject_code: string; subject_name: string; exam_type: string;
  date: string; start_time: string; end_time: string; venue: string;
}

export default function FacultyExams() {
  const { data, loading } = useFetch<ExamRow[]>("/faculty/exams");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No exams scheduled for your subjects." />;

  return (
    <div>
      <PageHeader title="Exam Schedule" subtitle="Upcoming internal and semester-end exams for your subjects" />
      <div className="grid md:grid-cols-2 gap-4">
        {data.map((e, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-ink">{e.subject_name}</p>
                <p className="text-xs text-slate">{e.subject_code} · {e.exam_type}</p>
              </div>
              <span className="font-display text-lg text-brass">{e.date}</span>
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs text-slate">
              <span>{e.start_time} – {e.end_time}</span>
              <span>{e.venue}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
