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

export function ErrorState({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div className="card p-8 text-center text-sm" role="alert">
      <p className="text-clay">{text}</p>
      {onRetry && (
        <button className="btn-secondary text-xs py-1.5 px-3 mt-3" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Pagination({
  page,
  pages,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav className="flex items-center justify-between gap-3 flex-wrap mt-4 text-xs text-slate" aria-label="Pagination">
      <span>
        Showing {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span aria-live="polite">
          Page {page} of {pages}
        </span>
        <button className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </nav>
  );
}

export function Banner({ text, tone = "info", onClose }: { text: string; tone?: "info" | "good" | "bad"; onClose?: () => void }) {
  const styles = {
    info: "bg-brass/10 border-brass/20 text-ink",
    good: "bg-leaf/10 border-leaf/20 text-ink",
    bad: "bg-clay/10 border-clay/20 text-clay",
  }[tone];
  return (
    <div className={`card p-3.5 mb-4 text-sm flex items-start justify-between gap-3 ${styles}`} role={tone === "bad" ? "alert" : "status"}>
      <span className="whitespace-pre-line">{text}</span>
      {onClose && (
        <button className="text-xs text-slate hover:text-ink shrink-0" onClick={onClose} aria-label="Dismiss message">
          Dismiss
        </button>
      )}
    </div>
  );
}
