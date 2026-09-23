"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { StatusBadge } from "@/components/StatusBadge";
import {
  useDevice,
  useDeviceAlerts,
  useDeviceCredentials,
  useDeviceEvents,
  useDeviceInterfaces,
  useDeviceMetrics,
  useSetDeviceCredential,
  useUpsertDeviceCheck,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { CheckType, MetricType } from "@/lib/types";

const METRIC_OPTIONS: MetricType[] = [
  "AVAILABILITY",
  "RESPONSE_TIME",
  "PACKET_LOSS",
  "CPU_USAGE",
  "MEMORY_USAGE",
  "DISK_USAGE",
  "UPTIME",
];

const CHECK_TYPES: CheckType[] = ["ICMP", "TCP", "HTTP", "HTTPS", "SNMP"];

function metricValue(latest: { metric_type: string; value: number; unit: string | null }[] | undefined, type: string) {
  const m = latest?.find((x) => x.metric_type === type);
  if (!m) return "-";
  return `${m.value.toFixed(1)}${m.unit || ""}`;
}

function formatTime(t: string) {
  return new Date(t).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function DeviceDetailPage() {
  const params = useParams<{ id: string }>();
  const deviceId = params.id;
  const { isConfigWriter } = useAuth();

  const { data: device, isLoading } = useDevice(deviceId);
  const { data: interfaces } = useDeviceInterfaces(deviceId);
  const { data: alerts } = useDeviceAlerts(deviceId);
  const { data: events } = useDeviceEvents(deviceId);
  const { data: credentials } = useDeviceCredentials(deviceId);

  const [metricType, setMetricType] = useState<MetricType>("RESPONSE_TIME");
  const [hours, setHours] = useState(24);
  const { data: series } = useDeviceMetrics(deviceId, metricType, hours);

  const upsertCheck = useUpsertDeviceCheck(deviceId);
  const setCredential = useSetDeviceCredential(deviceId);

  const chartData = useMemo(() => series?.points.map((p) => ({ time: p.time, value: p.value })) || [], [series]);

  if (isLoading || !device) return <div className="text-gray-400">Loading device...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">{device.hostname}</h1>
          <p className="text-sm text-gray-500 font-mono">{device.ip_address}</p>
        </div>
        <StatusBadge status={device.status} />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="card">
          <div className="text-xs text-gray-400">Type</div>
          <div className="text-gray-100">{device.device_type}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Vendor / Model</div>
          <div className="text-gray-100">{device.vendor || "-"} {device.model || ""}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Availability</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "AVAILABILITY")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Latency</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "RESPONSE_TIME")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Packet Loss</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "PACKET_LOSS")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Uptime</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "UPTIME")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">CPU</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "CPU_USAGE")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Memory</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "MEMORY_USAGE")}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-400">Disk</div>
          <div className="text-gray-100">{metricValue(device.latest_metrics, "DISK_USAGE")}</div>
        </div>
      </div>

      <div className="card">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <h3 className="text-sm font-medium text-gray-300">Historical metrics</h3>
          <select className="input" value={metricType} onChange={(e) => setMetricType(e.target.value as MetricType)}>
            {METRIC_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select className="input" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={6}>6h</option>
            <option value={24}>24h</option>
            <option value={168}>7d</option>
            <option value={720}>30d</option>
          </select>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tickFormatter={formatTime} stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} />
              <Tooltip labelFormatter={formatTime} contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <h3 className="mb-2 text-sm font-medium text-gray-300">Interfaces</h3>
        <table className="table-base">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Speed</th>
              <th>Alias</th>
            </tr>
          </thead>
          <tbody>
            {interfaces?.length ? (
              interfaces.map((iface) => (
                <tr key={iface.id}>
                  <td>{iface.name}</td>
                  <td>
                    <StatusBadge status={iface.oper_status} />
                  </td>
                  <td>{iface.speed_bps ? `${(iface.speed_bps / 1e9).toFixed(2)} Gbps` : "-"}</td>
                  <td>{iface.alias || "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="py-4 text-center text-gray-500">
                  No interface data (SNMP not configured or device has none).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card overflow-x-auto">
          <h3 className="mb-2 text-sm font-medium text-gray-300">Alerts</h3>
          <table className="table-base">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Message</th>
                <th>Status</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {alerts?.map((a) => (
                <tr key={a.id}>
                  <td>
                    <StatusBadge status={a.severity} />
                  </td>
                  <td>{a.message}</td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="text-xs text-gray-400">{new Date(a.opened_at).toLocaleString()}</td>
                </tr>
              ))}
              {!alerts?.length && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-gray-500">
                    No alerts.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card overflow-x-auto">
          <h3 className="mb-2 text-sm font-medium text-gray-300">Events</h3>
          <table className="table-base">
            <thead>
              <tr>
                <th>Type</th>
                <th>Message</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {events?.map((e) => (
                <tr key={e.id}>
                  <td className="text-xs">{e.event_type}</td>
                  <td>{e.message}</td>
                  <td className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {!events?.length && (
                <tr>
                  <td colSpan={3} className="py-4 text-center text-gray-500">
                    No events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isConfigWriter && (
        <div className="card flex flex-col gap-4">
          <h3 className="text-sm font-medium text-gray-300">Monitoring configuration</h3>

          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const checkType = form.get("check_type") as CheckType;
              const config: Record<string, unknown> = {};
              if (checkType === "TCP" || checkType === "HTTP" || checkType === "HTTPS") {
                const port = form.get("port");
                if (port) config.port = Number(port);
              }
              upsertCheck.mutate({
                check_type: checkType,
                enabled: true,
                config,
                interval_seconds: Number(form.get("interval_seconds") || 60),
                timeout_seconds: Number(form.get("timeout_seconds") || 5),
                retries: Number(form.get("retries") || 1),
              });
            }}
          >
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Check type
              <select name="check_type" className="input">
                {CHECK_TYPES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Port (TCP/HTTP)
              <input name="port" className="input w-24" placeholder="optional" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Interval (s)
              <input name="interval_seconds" className="input w-24" defaultValue={60} />
            </label>
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Timeout (s)
              <input name="timeout_seconds" className="input w-20" defaultValue={5} />
            </label>
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Retries
              <input name="retries" className="input w-16" defaultValue={1} />
            </label>
            <button type="submit" className="btn-primary" disabled={upsertCheck.isPending}>
              Save check
            </button>
          </form>

          <div>
            <h4 className="mb-1 text-xs uppercase tracking-wide text-gray-500">Configured checks</h4>
            <ul className="flex flex-wrap gap-2">
              {device.checks.map((c) => (
                <li key={c.id} className="rounded-md border border-panelborder px-2 py-1 text-xs text-gray-300">
                  {c.check_type} every {c.interval_seconds}s {c.enabled ? "" : "(disabled)"}
                </li>
              ))}
              {!device.checks.length && <li className="text-xs text-gray-500">No checks configured yet.</li>}
            </ul>
          </div>

          <form
            className="flex flex-wrap items-end gap-3 border-t border-panelborder pt-3"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              setCredential.mutate({
                credential_type: "SNMPV2C",
                payload: { community: String(form.get("community") || "public") },
              });
              e.currentTarget.reset();
            }}
          >
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              SNMPv2c community string
              <input name="community" className="input" placeholder="public" type="password" />
            </label>
            <button type="submit" className="btn-secondary" disabled={setCredential.isPending}>
              Save credential
            </button>
            <span className="text-xs text-gray-500">
              {credentials?.some((c) => c.credential_type === "SNMPV2C")
                ? "SNMPv2c credential is configured (value hidden)."
                : "No SNMP credential configured yet."}
            </span>
          </form>
        </div>
      )}
    </div>
  );
}
