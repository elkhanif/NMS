"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useAcknowledgeAlert, useAlerts, useResolveAlert, type AlertFilters } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AlertSeverity, AlertStatus } from "@/lib/types";

const STATUSES: AlertStatus[] = ["OPEN", "ACKNOWLEDGED", "RESOLVED"];
const SEVERITIES: AlertSeverity[] = ["WARNING", "CRITICAL"];

export default function AlertsPage() {
  const [filters, setFilters] = useState<AlertFilters>({ status: "OPEN" });
  const { data: alerts, isLoading } = useAlerts(filters);
  const { isOperator } = useAuth();
  const acknowledge = useAcknowledgeAlert();
  const resolve = useResolveAlert();

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Alerts</h1>

      <div className="card flex flex-wrap gap-3">
        <select
          className="input"
          value={filters.status || ""}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined }))}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={filters.severity || ""}
          onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value || undefined }))}
        >
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
              <th>Device</th>
              <th>Message</th>
              <th>Status</th>
              <th>Opened</th>
              {isOperator && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {alerts?.map((a) => (
              <tr key={a.id}>
                <td>
                  <StatusBadge status={a.severity} />
                </td>
                <td>
                  <Link href={`/devices/${a.device_id}`} className="text-blue-400 hover:underline">
                    view device
                  </Link>
                </td>
                <td>{a.message}</td>
                <td>
                  <StatusBadge status={a.status} />
                </td>
                <td className="text-xs text-gray-400">{new Date(a.opened_at).toLocaleString()}</td>
                {isOperator && (
                  <td className="flex gap-2">
                    {a.status === "OPEN" && (
                      <button className="btn-secondary" onClick={() => acknowledge.mutate(a.id)}>
                        Acknowledge
                      </button>
                    )}
                    {a.status !== "RESOLVED" && (
                      <button className="btn-primary" onClick={() => resolve.mutate(a.id)}>
                        Resolve
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {!isLoading && !alerts?.length && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  No alerts match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
