import clsx from "clsx";

const STATUS_STYLES: Record<string, string> = {
  UP: "bg-status-up/20 text-status-up border-status-up/40",
  WARNING: "bg-status-warning/20 text-status-warning border-status-warning/40",
  CRITICAL: "bg-status-critical/20 text-status-critical border-status-critical/40",
  DOWN: "bg-status-down/20 text-status-down border-status-down/40",
  UNKNOWN: "bg-status-unknown/20 text-status-unknown border-status-unknown/40",
  OPEN: "bg-status-critical/20 text-status-critical border-status-critical/40",
  ACKNOWLEDGED: "bg-status-warning/20 text-status-warning border-status-warning/40",
  RESOLVED: "bg-status-up/20 text-status-up border-status-up/40",
  PENDING: "bg-status-unknown/20 text-status-unknown border-status-unknown/40",
  RUNNING: "bg-status-warning/20 text-status-warning border-status-warning/40",
  COMPLETED: "bg-status-up/20 text-status-up border-status-up/40",
  FAILED: "bg-status-critical/20 text-status-critical border-status-critical/40",
  INFO: "bg-blue-500/20 text-blue-400 border-blue-500/40",
  POSSIBLE: "bg-status-warning/20 text-status-warning border-status-warning/40",
  SUSPECTED: "bg-orange-500/20 text-orange-400 border-orange-500/40",
  CONFIRMED: "bg-status-critical/20 text-status-critical border-status-critical/40",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-block rounded-full border px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[status] || STATUS_STYLES.UNKNOWN
      )}
    >
      {status}
    </span>
  );
}
