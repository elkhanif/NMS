"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { RelationshipTree } from "@/components/RelationshipTree";
import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { useDeviceInvestigation } from "@/lib/api";

function fmt(value: string | null): string {
  return value ?? "Unknown";
}

function fmtNum(value: number | null, unit: string, digits = 1): string {
  return value === null || value === undefined ? "Unknown" : `${value.toFixed(digits)}${unit}`;
}

function fmtTime(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Unknown";
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className={value === "Unknown" ? "text-gray-600" : "text-gray-100"}>{value}</div>
    </div>
  );
}

export default function DetectiveInvestigationPage() {
  const params = useParams<{ deviceId: string }>();
  const deviceId = params.deviceId;
  const { data, isLoading, error } = useDeviceInvestigation(deviceId);

  if (isLoading) return <div className="text-gray-400">Investigating...</div>;
  if (error || !data) return <div className="text-red-400">Device not found.</div>;

  const { identity, network_identity: net, health, timeline, ancestors, children, summary } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">{identity.hostname}</h1>
          <p className="font-mono text-sm text-gray-500">{identity.ip_address}</p>
        </div>
        <StatusBadge status={identity.status} />
      </div>

      {/* Investigation Summary */}
      <div className="card">
        <h3 className="mb-3 text-sm font-medium text-gray-300">Investigation Summary</h3>
        <div className="flex flex-col gap-1 font-mono text-sm text-gray-200">
          <p>
            Device is currently <span className="font-semibold">{summary.current_status}</span>.
          </p>
          <p>
            Last outage:{" "}
            {summary.last_outage_start ? (
              <>
                {fmtTime(summary.last_outage_start)}
                {summary.last_outage_end ? ` - ${fmtTime(summary.last_outage_end)}` : " (ongoing)"}
              </>
            ) : (
              "none recorded"
            )}
          </p>
          <p>Average latency (24h): {fmtNum(summary.avg_latency_ms, " ms", 1)}</p>
          <p>Packet loss (24h): {fmtNum(summary.packet_loss_pct, "%", 1)}</p>
          <p>IP changes (24h): {summary.ip_changes_24h}</p>
          <p>MAC changes (24h): {summary.mac_changes_24h}</p>
          <p>Connected through: {summary.connected_through || "Unknown"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Device Identity */}
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Device Identity</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Hostname" value={identity.hostname} />
            <Field label="IP Address" value={identity.ip_address} />
            <Field label="MAC Address" value={fmt(identity.mac_address)} />
            <Field label="Vendor" value={fmt(identity.vendor)} />
            <Field label="Model" value={fmt(identity.model)} />
            <Field label="Device Type" value={identity.device_type} />
            <Field label="OS" value={fmt(identity.os)} />
            <Field label="Serial Number" value={fmt(identity.serial_number)} />
            <Field label="First Seen" value={fmtTime(identity.first_seen)} />
            <Field label="Last Seen" value={fmtTime(identity.last_seen)} />
          </div>
        </div>

        {/* Network Identity */}
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-300">Network Identity</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Gateway" value={fmt(net.gateway)} />
            <Field label="VLAN" value={fmt(net.vlan)} />
            <Field label="Subnet" value={fmt(net.subnet)} />
            <Field label="Switch" value={fmt(net.switch_hostname)} />
            <Field label="Switch Port" value={fmt(net.switch_port)} />
            <Field label="Access Point" value={fmt(net.access_point)} />
            <Field label="Connected Devices" value={String(net.connected_device_ids.length)} />
          </div>
        </div>
      </div>

      {/* Current Health */}
      <div className="card">
        <h3 className="mb-3 text-sm font-medium text-gray-300">Current Health</h3>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Field label="Availability" value={fmtNum(health.availability_pct, "%")} />
          <Field label="Latency" value={fmtNum(health.latency_ms, " ms")} />
          <Field label="Packet Loss" value={fmtNum(health.packet_loss_pct, "%")} />
          <Field label="CPU" value={fmtNum(health.cpu_percent, "%")} />
          <Field label="Memory" value={fmtNum(health.memory_percent, "%")} />
          <Field label="Interfaces" value={String(health.interfaces.length)} />
        </div>
        {health.interfaces.length > 0 && (
          <table className="table-base mt-4">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>MAC</th>
                <th>Speed</th>
              </tr>
            </thead>
            <tbody>
              {health.interfaces.map((iface) => (
                <tr key={iface.id}>
                  <td>{iface.name}</td>
                  <td>
                    <StatusBadge status={iface.oper_status} />
                  </td>
                  <td className="font-mono text-xs">{iface.mac_address || "Unknown"}</td>
                  <td>{iface.speed_bps != null ? `${(iface.speed_bps / 1e9).toFixed(2)} Gbps` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Network Relationship */}
      <div className="card">
        <h3 className="mb-3 text-sm font-medium text-gray-300">Network Relationship</h3>
        <RelationshipTree
          ancestors={ancestors}
          deviceHostname={identity.hostname}
          deviceStatus={identity.status}
          childDevices={children}
        />
      </div>

      {/* Device Timeline */}
      <div className="card">
        <h3 className="mb-3 text-sm font-medium text-gray-300">Device Timeline</h3>
        <Timeline entries={timeline} />
      </div>

      <div>
        <Link href="/detective" className="text-sm text-blue-400 hover:underline">
          ← New search
        </Link>
      </div>
    </div>
  );
}
