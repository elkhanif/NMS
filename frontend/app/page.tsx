"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { SummaryCard } from "@/components/SummaryCard";
import {
  useDashboardChart,
  useDashboardSummary,
  useDevices,
  useEvents,
  useIncidents,
  useLocations,
  useStatusDistribution,
} from "@/lib/api";
import type { DashboardFilters, DeviceType } from "@/lib/types";

const DEVICE_TYPES: DeviceType[] = [
  "ROUTER",
  "FIREWALL",
  "SWITCH",
  "ACCESS_POINT",
  "SERVER",
  "VM",
  "PRINTER",
  "CCTV_NVR",
  "IOT_DEVICE",
  "GENERIC",
];

const STATUS_COLORS: Record<string, string> = {
  UP: "#22c55e",
  WARNING: "#eab308",
  CRITICAL: "#ef4444",
  DOWN: "#ef4444",
  UNKNOWN: "#6b7280",
};

function formatTime(t: string) {
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="card">
      <h3 className="mb-2 text-sm font-medium text-gray-300">{title}</h3>
      <div className="h-56">{children}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [filters, setFilters] = useState<DashboardFilters>({});
  const { data: locations } = useLocations();
  const { data: summary, isLoading } = useDashboardSummary(filters);
  const { data: statusDist } = useStatusDistribution(filters);
  const { data: bandwidth } = useDashboardChart("bandwidth");
  const { data: latency } = useDashboardChart("latency");
  const { data: availability } = useDashboardChart("availability");
  const { data: alertTrend } = useDashboardChart("alert-trend");

  const { data: openIncidents } = useIncidents({ status: "OPEN" });
  const { data: changes } = useEvents({ category: "change" });
  const { data: allDevices } = useDevices();

  const brokenDevices = useMemo(
    () => (allDevices || []).filter((d) => d.status === "DOWN" || d.status === "CRITICAL").slice(0, 5),
    [allDevices]
  );
  const isHealthy = Boolean(summary) && summary!.critical === 0 && summary!.offline === 0 && !openIncidents?.length;
  const topIncident = openIncidents?.[0];
  const affectedCount = openIncidents?.length
    ? openIncidents.reduce((sum, inc) => sum + inc.affected_device_count, 0)
    : brokenDevices.length;

  const heartbeatAge = summary?.worker_last_heartbeat_at
    ? (Date.now() - new Date(summary.worker_last_heartbeat_at).getTime()) / 1000
    : null;
  const workerStale = heartbeatAge === null || heartbeatAge > 60;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-gray-100">NOC Dashboard</h1>
        <div
          className={`rounded-md border px-3 py-1 text-xs ${
            workerStale ? "border-red-700 bg-red-900/30 text-red-300" : "border-green-700 bg-green-900/30 text-green-300"
          }`}
        >
          Worker:{" "}
          {heartbeatAge === null
            ? "no heartbeat yet"
            : workerStale
              ? `stale (${Math.round(heartbeatAge)}s ago)`
              : `healthy (${Math.round(heartbeatAge)}s ago)`}
        </div>
      </div>

      {/* NOC-style "answer the question" strip */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-gray-500">Is the network healthy?</div>
          <div className={`mt-1 text-lg font-semibold ${isHealthy ? "text-status-up" : "text-status-critical"}`}>
            {isHealthy ? "Yes" : "No"}
          </div>
        </div>

        <div className="card">
          <div className="text-xs uppercase tracking-wide text-gray-500">What is broken?</div>
          {brokenDevices.length ? (
            <ul className="mt-1 flex flex-col gap-0.5 text-sm">
              {brokenDevices.map((d) => (
                <li key={d.id}>
                  <Link href={`/detective/${d.id}`} className="text-gray-100 hover:underline">
                    {d.hostname}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-1 text-sm text-gray-500">Nothing broken.</div>
          )}
        </div>

        <div className="card">
          <div className="text-xs uppercase tracking-wide text-gray-500">What changed?</div>
          {changes?.length ? (
            <ul className="mt-1 flex flex-col gap-0.5 text-xs text-gray-300">
              {changes.slice(0, 3).map((e) => (
                <li key={e.id} className="truncate">
                  {e.message}
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-1 text-sm text-gray-500">No recent changes.</div>
          )}
        </div>

        <div className="card">
          <div className="text-xs uppercase tracking-wide text-gray-500">Devices affected</div>
          <div className="mt-1 text-lg font-semibold text-gray-100">{affectedCount}</div>
        </div>

        <div className="card">
          <div className="text-xs uppercase tracking-wide text-gray-500">Where to investigate?</div>
          {topIncident ? (
            <Link href={`/incidents/${topIncident.id}`} className="mt-1 block text-sm text-blue-400 hover:underline">
              {topIncident.title}
            </Link>
          ) : brokenDevices[0] ? (
            <Link href={`/detective/${brokenDevices[0].id}`} className="mt-1 block text-sm text-blue-400 hover:underline">
              {brokenDevices[0].hostname}
            </Link>
          ) : (
            <div className="mt-1 text-sm text-gray-500">Nothing to investigate.</div>
          )}
        </div>
      </div>

      <div className="card flex flex-wrap gap-3">
        <select
          className="input"
          value={filters.location_id || ""}
          onChange={(e) => setFilters((f) => ({ ...f, location_id: e.target.value || undefined }))}
        >
          <option value="">All locations</option>
          {locations?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={filters.device_type || ""}
          onChange={(e) => setFilters((f) => ({ ...f, device_type: (e.target.value || undefined) as DeviceType }))}
        >
          <option value="">All device types</option>
          {DEVICE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          className="input"
          placeholder="Vendor"
          value={filters.vendor || ""}
          onChange={(e) => setFilters((f) => ({ ...f, vendor: e.target.value || undefined }))}
        />
        <button className="btn-secondary" onClick={() => setFilters({})}>
          Clear filters
        </button>
      </div>

      {!isLoading && summary && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <SummaryCard label="Total Devices" value={summary.total_devices} />
          <SummaryCard label="Online" value={summary.online} accent="up" />
          <SummaryCard label="Warning" value={summary.warning} accent="warning" />
          <SummaryCard label="Critical" value={summary.critical} accent="critical" />
          <SummaryCard label="Offline" value={summary.offline} accent="down" />
          <SummaryCard label="Availability" value={`${summary.overall_availability_pct.toFixed(1)}%`} accent="up" />
          <SummaryCard
            label="Active Alerts"
            value={summary.active_alerts}
            sub={`${summary.active_critical_alerts} critical`}
            accent={summary.active_critical_alerts > 0 ? "critical" : "warning"}
          />
          <SummaryCard
            label="Avg Latency"
            value={summary.avg_latency_ms !== null ? `${summary.avg_latency_ms.toFixed(1)} ms` : "-"}
          />
          <SummaryCard
            label="Avg Packet Loss"
            value={summary.avg_packet_loss_pct !== null ? `${summary.avg_packet_loss_pct.toFixed(1)}%` : "-"}
          />
          <SummaryCard
            label="Bandwidth (in/out)"
            value={`${((summary.total_inbound_bps || 0) / 1e6).toFixed(1)} / ${((summary.total_outbound_bps || 0) / 1e6).toFixed(1)} Mbps`}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Bandwidth (avg bps, hourly)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={bandwidth?.points || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} />
              <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Latency (ms, hourly avg)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={latency?.points || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} />
              <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Line type="monotone" dataKey="value" stroke="#eab308" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Availability (%, hourly avg)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={availability?.points || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
              <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={11} />
              <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Line type="monotone" dataKey="value" stroke="#22c55e" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Device Status Distribution">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={statusDist || []}
                dataKey="count"
                nameKey="status"
                innerRadius={45}
                outerRadius={75}
                paddingAngle={2}
              >
                {(statusDist || []).map((entry) => (
                  <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || "#6b7280"} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Alert Trend (opened per hour)">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={alertTrend?.points || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
              <YAxis allowDecimals={false} stroke="#6b7280" fontSize={11} />
              <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Bar dataKey="value" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
