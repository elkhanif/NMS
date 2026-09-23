"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useEvents } from "@/lib/api";
import type { EventSeverity } from "@/lib/types";

const SEVERITIES: EventSeverity[] = ["INFO", "WARNING", "CRITICAL"];

export default function EventsPage() {
  const [severity, setSeverity] = useState<string | undefined>();
  const { data: events, isLoading } = useEvents({ severity });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Events</h1>

      <div className="card flex flex-wrap gap-3">
        <select className="input" value={severity || ""} onChange={(e) => setSeverity(e.target.value || undefined)}>
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Type</th>
              <th>Message</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {events?.map((e) => (
              <tr key={e.id}>
                <td>
                  <StatusBadge status={e.severity} />
                </td>
                <td className="text-xs">{e.event_type}</td>
                <td>{e.message}</td>
                <td className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {!isLoading && !events?.length && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-gray-500">
                  No events yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
