import { useFetch } from "../../hooks/useFetch";
import { PageHeader, Loading, EmptyState, Pill } from "../../components/Common";

interface FeeRow {
  semester: number;
  total_amount: number;
  paid_amount: number;
  balance: number;
  due_date: string;
  status: string;
}

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export default function StudentFees() {
  const { data, loading } = useFetch<FeeRow[]>("/student/fees");

  if (loading) return <Loading />;
  if (!data || data.length === 0) return <EmptyState text="No fee records found." />;

  return (
    <div>
      <PageHeader title="Fees & Payments" subtitle="Semester-wise fee status" />
      <div className="grid md:grid-cols-2 gap-4">
        {data.map((f, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-start justify-between mb-4">
              <p className="font-display text-lg text-ink">Semester {f.semester}</p>
              <Pill text={f.status} tone={f.status === "Paid" ? "good" : f.status === "Partially Paid" ? "warn" : "bad"} />
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate">Total fee</span><span className="font-medium">{inr(f.total_amount)}</span></div>
              <div className="flex justify-between"><span className="text-slate">Paid</span><span className="font-medium text-leaf">{inr(f.paid_amount)}</span></div>
              <div className="flex justify-between"><span className="text-slate">Balance due</span><span className="font-medium text-clay">{inr(f.balance)}</span></div>
              <div className="flex justify-between pt-2 border-t border-black/5"><span className="text-slate">Due date</span><span className="font-medium">{f.due_date}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
