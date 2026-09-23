"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RelationshipTree } from "@/components/RelationshipTree";
import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { TopologyCanvas } from "@/components/TopologyCanvas";
import { useAuth } from "@/lib/auth-context";
import { useDeviceMetrics, useIncident, useUpdateIncident } from "@/lib/api";

function formatTime(t: string) {
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function displayId(seq: number) {
  return `INC-${String(seq).padStart(5, "0")}`;
}

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const { isConfigWriter } = useAuth();
  const { data: incident, isLoading } = useIncident(incidentId);
  const updateIncident = useUpdateIncident(incidentId);

  const hoursBack = useMemo(() => {
    if (!incident) return 24;
    const start = new Date(incident.started_at).getTime();
    return Math.max(1, (Date.now() - start) / 3_600_000 + 0.5);
  }, [incident]);

  const { data: latencySeries } = useDeviceMetrics(incident?.suspected_device_id || "", "RESPONSE_TIME", hoursBack);

  if (isLoading || !incident) return <div className="text-gray-400">Loading incident...</div>;

  const chartData = latencySeries?.points.map((p) => ({ time: p.time, value: p.value })) || [];
  const affectedIds = incident.affected_devices.map((d) => d.id);
  const relationshipNodes = incident.affected_devices
    .filter((d) => d.id !== incident.suspected_device_id)
    .map((d) => ({ device_id: d.id, hostname: d.hostname, status: d.status, relationship_type: null, interface_name: null }));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">
            {displayId(incident.sequence_number)} -- {incident.title}
          </h1>
          <p className="text-sm text-gray-500">
            {incident.confidence === "POSSIBLE" && "System has weak evidence this is one shared-cause incident."}
            {incident.confidence === "SUSPECTED" && "System has moderate evidence this is one shared-cause incident."}
            {incident.confidence === "CONFIRMED" && "A human has confirmed this incident and its root cause."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={incident.confidence} />
          <StatusBadge status={incident.status} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="card">
          <div className="text-xs text-gray-400">Suspected Device</div>
          <div className="text-gray-100">
            {incident.suspected_device ? (
              <Link href={`/detective/${incident.suspected_device_id}`} className="text-blue-400 hover:underline">
                {incident.suspected_device.hostname}
              </Link>
            ) : (
              "Unknown"
            )}
          </div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Started</div>
          <div className="text-gray-100">{new Date(incident.started_at).toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Duration</div>
          <div className="text-gray-100">
            {incident.duration_seconds !== null ? `${Math.round(incident.duration_seconds)}s` : "-"}
          </div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Affected Devices</div>
          <div className="text-gray-100">{incident.affected_device_count}</div>
        </div>
      </div>

      {isConfigWriter && incident.confidence !== "CONFIRMED" && (
        <div className="card flex items-center gap-3">
          <span className="text-sm text-gray-400">Investigated this and confirmed the root cause?</span>
          <button
            className="btn-primary"
            disabled={updateIncident.isPending}
            onClick={() => updateIncident.mutate({ confidence: "CONFIRMED" })}
          >
            Confirm root cause
          </button>
          {incident.status === "OPEN" && (
            <button
              className="btn-secondary"
              disabled={updateIncident.isPending}
              onClick={() => updateIncident.mutate({ status: "RESOLVED" })}
            >
              Mark resolved
            </button>
          )}
        </div>
      )}

      <div className="card">
        <h3 className="mb-3 text-sm font-medium text-gray-300">Affected Topology</h3>
        <TopologyCanvas nodes={incident.topology.nodes} edges={incident.topology.edges} highlightIds={affectedIds} />
      </div>

      {incident.suspected_device_id && (
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-300">
            Latency around the incident ({incident.suspected_device?.hostname})
          </h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} />
                <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
                <ReferenceArea
                  x1={incident.started_at}
                  x2={incident.resolved_at || new Date().toISOString()}
                  fill="#ef4444"
                  fillOpacity={0.12}
                />
                <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-xs text-gray-500">Shaded region marks the incident window (started → resolved/now).</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Affected Devices</h3>
          {incident.suspected_device && (
            <RelationshipTree
              ancestors={[]}
              deviceHostname={incident.suspected_device.hostname}
              deviceStatus={incident.suspected_device.status}
              childDevices={relationshipNodes}
            />
          )}
        </div>

        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Related Events</h3>
          <Timeline
            entries={incident.related_events.map((e) => ({
              time: e.created_at,
              event_type: e.event_type,
              message: e.message,
              severity: e.severity,
            }))}
          />
        </div>
      </div>

      <div>
        <Link href="/incidents" className="text-sm text-blue-400 hover:underline">
          ← All incidents
        </Link>
      </div>
    </div>
  );
}
