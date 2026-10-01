import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, Pill } from "../../components/Common";

interface MarkRow {
  subject_code: string;
  subject_name: string;
  internal_1: number;
  internal_2: number;
  assignment: number;
  external: number;
  total: number;
  grade: string;
}

const gradeTone = (g: string): "good" | "warn" | "bad" =>
  ["S", "A", "B"].includes(g) ? "good" : ["C", "D"].includes(g) ? "warn" : "bad";

export default function StudentMarks() {
  const { data, loading } = useFetch<MarkRow[]>("/student/marks");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No marks have been recorded yet." />;

  const chartData = data.map((m) => ({ name: m.subject_code, Total: m.total }));

  return (
    <div>
      <PageHeader title="Marks & Grades" subtitle="Internal assessments, assignments, and external marks by subject" />

      <div className="card p-5 mb-6">
        <p className="font-display text-lg text-ink mb-4">Subject-wise total (out of 100)</p>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#12233D0D" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#5B6B7C" }} />
            <YAxis tick={{ fontSize: 12, fill: "#5B6B7C" }} domain={[0, 100]} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar dataKey="Total" fill="#B98B3E" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card p-5">
        <table className="w-full table-clean">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Internal 1</th>
              <th>Internal 2</th>
              <th>Assignment</th>
              <th>External</th>
              <th>Total</th>
              <th>Grade</th>
            </tr>
          </thead>
          <tbody>
            {data.map((m) => (
              <tr key={m.subject_code}>
                <td>
                  <p className="font-medium">{m.subject_name}</p>
                  <p className="text-xs text-slate">{m.subject_code}</p>
                </td>
                <td>{m.internal_1}</td>
                <td>{m.internal_2}</td>
                <td>{m.assignment}</td>
                <td>{m.external}</td>
                <td className="font-medium">{m.total}</td>
                <td><Pill text={m.grade} tone={gradeTone(m.grade)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
