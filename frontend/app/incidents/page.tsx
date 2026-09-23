"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useIncidents } from "@/lib/api";

export default function IncidentsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: incidents, isLoading } = useIncidents(statusFilter ? { status: statusFilter } : {});

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Incidents</h1>

      <div className="card flex gap-3">
        <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="OPEN">Open</option>
          <option value="RESOLVED">Resolved</option>
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Affected</th>
              <th>Started</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {!isLoading && !incidents?.length && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-gray-500">
                  No incidents.
                </td>
              </tr>
            )}
            {incidents?.map((inc) => (
              <tr key={inc.id}>
                <td className="font-mono text-xs">
                  <Link href={`/incidents/${inc.id}`} className="text-blue-400 hover:underline">
                    INC-{String(inc.sequence_number).padStart(5, "0")}
                  </Link>
                </td>
                <td>{inc.title}</td>
                <td>
                  <StatusBadge status={inc.confidence} />
                </td>
                <td>
                  <StatusBadge status={inc.status} />
                </td>
                <td>{inc.affected_device_count}</td>
                <td className="text-xs text-gray-400">{new Date(inc.started_at).toLocaleString()}</td>
                <td className="text-xs text-gray-400">
                  {inc.resolved_at
                    ? `${Math.round(
                        (new Date(inc.resolved_at).getTime() - new Date(inc.started_at).getTime()) / 1000
                      )}s`
                    : "ongoing"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
