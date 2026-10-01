import { ReactNode } from "react";

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 className="font-display text-2xl text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-slate mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  accent = "navy",
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "navy" | "brass" | "leaf" | "clay";
}) {
  const accentColor = {
    navy: "bg-navy",
    brass: "bg-brass",
    leaf: "bg-leaf",
    clay: "bg-clay",
  }[accent];
  return (
    <div className="card p-5 relative overflow-hidden">
      <div className={`absolute left-0 top-0 h-full w-1 ${accentColor}`} />
      <p className="text-xs text-slate font-medium">{label}</p>
      <p className="font-display text-3xl text-ink mt-1.5">{value}</p>
      {hint && <p className="text-xs text-slate mt-1.5">{hint}</p>}
    </div>
  );
}

export function ProgressBar({ pct, tone = "navy" }: { pct: number; tone?: "navy" | "clay" | "leaf" }) {
  const color = pct >= 75 ? "bg-leaf" : pct >= 65 ? "bg-brass" : "bg-clay";
  const c = tone === "navy" ? color : tone === "clay" ? "bg-clay" : "bg-leaf";
  return (
    <div className="progress-track">
      <div className={`h-full rounded-full ${c}`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="card p-10 text-center text-sm text-slate">
      {text}
    </div>
  );
}

export function Pill({ text, tone = "neutral" }: { text: string; tone?: "neutral" | "good" | "warn" | "bad" }) {
  const styles = {
    neutral: "bg-black/5 text-ink",
    good: "bg-leaf/10 text-leaf",
    warn: "bg-brass/15 text-brass",
    bad: "bg-clay/10 text-clay",
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}>{text}</span>;
}

export function Loading() {
  return <div className="text-sm text-slate py-10 text-center">Loading…</div>;
}
