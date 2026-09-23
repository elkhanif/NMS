"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useCreateDevice, useDevices, type DeviceFilters } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { DeviceStatus, DeviceType } from "@/lib/types";

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
const STATUSES: DeviceStatus[] = ["UP", "WARNING", "CRITICAL", "DOWN", "UNKNOWN"];

export default function DevicesPage() {
  const [filters, setFilters] = useState<DeviceFilters>({});
  const [showAdd, setShowAdd] = useState(false);
  const { data: devices, isLoading } = useDevices(filters);
  const { isConfigWriter } = useAuth();
  const createDevice = useCreateDevice();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">Devices</h1>
        {isConfigWriter && (
          <button className="btn-primary" onClick={() => setShowAdd((v) => !v)}>
            {showAdd ? "Cancel" : "+ Add device"}
          </button>
        )}
      </div>

      {showAdd && (
        <form
          className="card flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createDevice.mutate(
              {
                hostname: String(form.get("hostname")),
                ip_address: String(form.get("ip_address")),
                device_type: form.get("device_type") as DeviceType,
                vendor: String(form.get("vendor") || "") || undefined,
              },
              { onSuccess: () => setShowAdd(false) }
            );
          }}
        >
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            Hostname
            <input name="hostname" required className="input" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            IP Address
            <input name="ip_address" required className="input" placeholder="10.10.0.1" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            Type
            <select name="device_type" className="input" defaultValue="GENERIC">
              {DEVICE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            Vendor
            <input name="vendor" className="input" />
          </label>
          <button type="submit" className="btn-primary" disabled={createDevice.isPending}>
            {createDevice.isPending ? "Saving..." : "Save"}
          </button>
          {createDevice.isError && (
            <span className="text-xs text-red-400">{(createDevice.error as Error).message}</span>
          )}
        </form>
      )}

      <div className="card flex flex-wrap gap-3">
        <input
          className="input flex-1 min-w-[180px]"
          placeholder="Search hostname or IP..."
          value={filters.search || ""}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value || undefined }))}
        />
        <select
          className="input"
          value={filters.device_type || ""}
          onChange={(e) => setFilters((f) => ({ ...f, device_type: e.target.value || undefined }))}
        >
          <option value="">All types</option>
          {DEVICE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
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
      </div>

      <div className="card overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>Hostname</th>
              <th>IP Address</th>
              <th>Type</th>
              <th>Vendor</th>
              <th>Status</th>
              <th>Last Seen</th>
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
            {!isLoading && devices?.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  No devices found.
                </td>
              </tr>
            )}
            {devices?.map((d) => (
              <tr key={d.id}>
                <td>
                  <Link href={`/devices/${d.id}`} className="text-blue-400 hover:underline">
                    {d.hostname}
                  </Link>
                </td>
                <td className="font-mono text-xs">{d.ip_address}</td>
                <td>{d.device_type}</td>
                <td>{d.vendor || "-"}</td>
                <td>
                  <StatusBadge status={d.status} />
                </td>
                <td className="text-xs text-gray-400">{d.last_seen ? new Date(d.last_seen).toLocaleString() : "never"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
