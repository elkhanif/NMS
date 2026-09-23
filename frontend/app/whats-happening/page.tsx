"use client";

import Link from "next/link";
import { useMemo } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useDevices, useEvents, useIncidents } from "@/lib/api";
import type { EventRow } from "@/lib/types";

const SEVERITY_DOT: Record<string, string> = {
  INFO: "🔵",
  WARNING: "🟡",
  CRITICAL: "🔴",
};

function isRecoveryish(e: EventRow): boolean {
  return e.event_type === "DEVICE_RECOVERED" || e.event_type === "INTERFACE_RECOVERED" || e.event_type === "ALERT_RESOLVED";
}

function formatTime(t: string) {
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function WhatsHappeningPage() {
  const { data: devices } = useDevices();
  const { data: openIncidents } = useIncidents({ status: "OPEN" });
  const { data: events } = useEvents({});
  const { data: changes } = useEvents({ category: "change" });

  const deviceMap = useMemo(() => {
    const m = new Map<string, { hostname: string; ip_address: string }>();
    devices?.forEach((d) => m.set(d.id, { hostname: d.hostname, ip_address: d.ip_address }));
    return m;
  }, [devices]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">What&apos;s Happening</h1>
        <p className="text-sm text-gray-400">What&apos;s happening on the network right now.</p>
      </div>

      {/* Incidents */}
      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">Incidents</h3>
          <Link href="/incidents" className="text-xs text-blue-400 hover:underline">
            View all
          </Link>
        </div>
        {openIncidents?.length ? (
          <div className="flex flex-col gap-2">
            {openIncidents.map((inc) => (
              <Link
                key={inc.id}
                href={`/incidents/${inc.id}`}
                className="flex items-center justify-between rounded-md border border-panelborder px-3 py-2 hover:bg-white/5"
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={inc.confidence} />
                  <StatusBadge status={inc.status} />
                  <span className="text-sm text-gray-100">{inc.title}</span>
                </div>
                <span className="text-xs text-gray-500">{inc.affected_device_count} device(s) affected</span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No open incidents. Network is not showing correlated failures.</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Live Event Feed */}
        <div className="card overflow-x-auto">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Live Event Feed</h3>
          <ul className="flex max-h-[600px] flex-col gap-1 overflow-y-auto font-mono text-sm">
            {events?.slice(0, 40).map((e) => {
              const device = e.device_id ? deviceMap.get(e.device_id) : null;
              return (
                <li key={e.id} className="flex items-baseline gap-2">
                  <span className="text-xs text-gray-500">{formatTime(e.created_at)}</span>
                  <span>{isRecoveryish(e) ? "🟢" : SEVERITY_DOT[e.severity] || "⚪"}</span>
                  <span className="text-gray-100">{device?.hostname || "System"}</span>
                  <span className="text-xs text-gray-500">{e.event_type}</span>
                  <span className="truncate text-xs text-gray-400">{e.message}</span>
                </li>
              );
            })}
            {!events?.length && <li className="py-4 text-center text-gray-500">No events yet.</li>}
          </ul>
        </div>

        {/* Network Changes */}
        <div className="card overflow-x-auto">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Network Changes</h3>
          <ul className="flex max-h-[600px] flex-col gap-1 overflow-y-auto font-mono text-sm">
            {changes?.slice(0, 40).map((e) => {
              const device = e.device_id ? deviceMap.get(e.device_id) : null;
              const dot = e.event_type === "DEVICE_NEW" ? "🟢" : "🟡";
              return (
                <li key={e.id} className="flex items-baseline gap-2">
                  <span className="text-xs text-gray-500">{formatTime(e.created_at)}</span>
                  <span>{dot}</span>
                  <span className="text-gray-100">
                    {device ? (
                      <Link href={`/detective/${e.device_id}`} className="hover:underline">
                        {device.hostname}
                      </Link>
                    ) : (
                      "Unknown device"
                    )}
                  </span>
                  <span className="truncate text-xs text-gray-400">{e.message}</span>
                </li>
              );
            })}
            {!changes?.length && <li className="py-4 text-center text-gray-500">No network changes recorded yet.</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
