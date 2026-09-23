import clsx from "clsx";
import type { ReactNode } from "react";

export function SummaryCard({
  label,
  value,
  accent,
  sub,
}: {
  label: string;
  value: ReactNode;
  accent?: "up" | "warning" | "critical" | "down" | "unknown";
  sub?: string;
}) {
  const accentClass = accent
    ? {
        up: "text-status-up",
        warning: "text-status-warning",
        critical: "text-status-critical",
        down: "text-status-down",
        unknown: "text-status-unknown",
      }[accent]
    : "text-gray-100";

  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-gray-400">{label}</span>
      <span className={clsx("text-2xl font-semibold", accentClass)}>{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  );
}
