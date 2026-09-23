"use client";

import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { useBulkSetCheck, useBulkSetCredential, useCreateDevice, useDevices, type DeviceFilters } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { CheckType, DeviceStatus, DeviceType } from "@/lib/types";

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
const CHECK_TYPES: CheckType[] = ["ICMP", "TCP", "HTTP", "HTTPS", "SNMP"];
const AUTH_PROTOCOLS = ["SHA", "MD5", "SHA224", "SHA256", "SHA384", "SHA512"];
const PRIV_PROTOCOLS = ["AES", "AES192", "AES256", "DES", "3DES"];

export default function DevicesPage() {
  const [filters, setFilters] = useState<DeviceFilters>({});
  const [showAdd, setShowAdd] = useState(false);
  const { data: devices, isLoading } = useDevices(filters);
  const { isConfigWriter } = useAuth();
  const createDevice = useCreateDevice();
  const bulkSetCredential = useBulkSetCredential();
  const bulkSetCheck = useBulkSetCheck();
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set());
  const [showBulkCredential, setShowBulkCredential] = useState(false);
  const [bulkCredentialType, setBulkCredentialType] = useState<"SNMPV2C" | "SNMPV3">("SNMPV2C");
  const [showBulkCheck, setShowBulkCheck] = useState(false);
  const [bulkCheckType, setBulkCheckType] = useState<CheckType>("ICMP");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">Devices</h1>
        <div className="flex gap-2">
          {isConfigWriter && selectedDevices.size > 0 && (
            <button className="btn-secondary" onClick={() => setShowBulkCheck((v) => !v)}>
              {showBulkCheck ? "Cancel" : `Set monitoring config (${selectedDevices.size})`}
            </button>
          )}
          {isConfigWriter && selectedDevices.size > 0 && (
            <button className="btn-secondary" onClick={() => setShowBulkCredential((v) => !v)}>
              {showBulkCredential ? "Cancel" : `Set SNMP credential (${selectedDevices.size})`}
            </button>
          )}
          {isConfigWriter && (
            <button className="btn-primary" onClick={() => setShowAdd((v) => !v)}>
              {showAdd ? "Cancel" : "+ Add device"}
            </button>
          )}
        </div>
      </div>

      {showBulkCheck && (
        <form
          className="card flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const device_ids = Array.from(selectedDevices);
            const config: Record<string, unknown> = {};
            if (bulkCheckType === "TCP" || bulkCheckType === "HTTP" || bulkCheckType === "HTTPS") {
              const port = form.get("port");
              if (port) config.port = Number(port);
            }
            bulkSetCheck.mutate(
              {
                device_ids,
                check_type: bulkCheckType,
                enabled: true,
                config,
                interval_seconds: Number(form.get("interval_seconds") || 60),
                timeout_seconds: Number(form.get("timeout_seconds") || 5),
                retries: Number(form.get("retries") || 1),
              },
              {
                onSuccess: () => {
                  setShowBulkCheck(false);
                  setSelectedDevices(new Set());
                },
              }
            );
          }}
        >
          <p className="text-xs text-gray-400">
            Applies the same monitoring check to all {selectedDevices.size} selected device(s) at once.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Check type
              <select
                className="input"
                value={bulkCheckType}
                onChange={(e) => setBulkCheckType(e.target.value as CheckType)}
              >
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
          </div>
          <div className="flex items-center gap-3">
            <button type="submit" className="btn-primary w-fit" disabled={bulkSetCheck.isPending}>
              {bulkSetCheck.isPending ? "Applying..." : `Apply to ${selectedDevices.size} device(s)`}
            </button>
            {bulkSetCheck.isError && (
              <span className="text-xs text-red-400">{(bulkSetCheck.error as Error).message}</span>
            )}
          </div>
        </form>
      )}

      {showBulkCredential && (
        <form
          className="card flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const device_ids = Array.from(selectedDevices);
            const credPayload: Record<string, string> =
              bulkCredentialType === "SNMPV3"
                ? {
                    username: String(form.get("username") || ""),
                    auth_protocol: String(form.get("auth_protocol") || ""),
                    auth_password: String(form.get("auth_password") || ""),
                    priv_protocol: String(form.get("priv_protocol") || ""),
                    priv_password: String(form.get("priv_password") || ""),
                  }
                : { community: String(form.get("community") || "public") };
            bulkSetCredential.mutate(
              { device_ids, credential_type: bulkCredentialType, payload: credPayload },
              {
                onSuccess: () => {
                  setShowBulkCredential(false);
                  setSelectedDevices(new Set());
                },
              }
            );
          }}
        >
          <p className="text-xs text-gray-400">
            Applies the same SNMP credential to all {selectedDevices.size} selected device(s) at once.
          </p>
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            SNMP credential type
            <select
              className="input w-40"
              value={bulkCredentialType}
              onChange={(e) => setBulkCredentialType(e.target.value as "SNMPV2C" | "SNMPV3")}
            >
              <option value="SNMPV2C">SNMPv2c</option>
              <option value="SNMPV3">SNMPv3</option>
            </select>
          </label>

          {bulkCredentialType === "SNMPV2C" ? (
            <label className="flex flex-col gap-1 text-xs text-gray-400">
              Community string
              <input name="community" className="input" placeholder="public" type="password" />
            </label>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-gray-400">
                Username
                <input name="username" className="input" placeholder="admin" />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-400">
                Auth protocol
                <select name="auth_protocol" className="input" defaultValue="SHA">
                  <option value="">None (noAuthNoPriv)</option>
                  {AUTH_PROTOCOLS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-400">
                Auth password
                <input name="auth_password" className="input" type="password" />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-400">
                Priv protocol
                <select name="priv_protocol" className="input" defaultValue="AES">
                  <option value="">None (authNoPriv)</option>
                  {PRIV_PROTOCOLS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-400">
                Priv password
                <input name="priv_password" className="input" type="password" />
              </label>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button type="submit" className="btn-primary w-fit" disabled={bulkSetCredential.isPending}>
              {bulkSetCredential.isPending ? "Applying..." : `Apply to ${selectedDevices.size} device(s)`}
            </button>
            {bulkSetCredential.isError && (
              <span className="text-xs text-red-400">{(bulkSetCredential.error as Error).message}</span>
            )}
          </div>
        </form>
      )}

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
              {isConfigWriter && (
                <th>
                  <input
                    type="checkbox"
                    checked={!!devices?.length && devices.every((d) => selectedDevices.has(d.id))}
                    onChange={(e) => {
                      setSelectedDevices(e.target.checked ? new Set(devices?.map((d) => d.id)) : new Set());
                    }}
                  />
                </th>
              )}
              <th>Hostname</th>
              <th>IP Address</th>
              <th>Type</th>
              <th>Vendor</th>
              <th>Status</th>
              <th>SNMP</th>
              <th>Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {!isLoading && devices?.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-gray-500">
                  No devices found.
                </td>
              </tr>
            )}
            {devices?.map((d) => (
              <tr key={d.id}>
                {isConfigWriter && (
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedDevices.has(d.id)}
                      onChange={(e) => {
                        setSelectedDevices((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(d.id);
                          else next.delete(d.id);
                          return next;
                        });
                      }}
                    />
                  </td>
                )}
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
                <td>
                  {d.has_snmp_credential ? (
                    <span className="text-xs text-green-400">configured</span>
                  ) : (
                    <span className="text-xs text-gray-500">none</span>
                  )}
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
