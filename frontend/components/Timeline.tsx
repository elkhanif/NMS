import { StatusBadge } from "@/components/StatusBadge";
import type { TimelineEntry } from "@/lib/types";

function formatTime(t: string) {
  return new Date(t).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  if (!entries.length) {
    return <p className="text-sm text-gray-500">No timeline activity recorded yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-3">
      {entries.map((e, i) => (
        <li key={i} className="flex items-start gap-3 border-l-2 border-panelborder pl-3">
          <span className="w-40 shrink-0 font-mono text-xs text-gray-500">{formatTime(e.time)}</span>
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <StatusBadge status={e.severity} />
              <span className="text-xs text-gray-400">{e.event_type}</span>
            </div>
            <span className="text-sm text-gray-200">{e.message}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
