"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import {
  useDiscoveryJobs,
  useDiscoveryResults,
  useImportDiscoveryResults,
  useStartDiscovery,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { DeviceType } from "@/lib/types";

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

export default function DiscoveryPage() {
  const { isConfigWriter } = useAuth();
  const { data: jobs } = useDiscoveryJobs();
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [selectedResults, setSelectedResults] = useState<Set<string>>(new Set());
  const startDiscovery = useStartDiscovery();
  const { data: results } = useDiscoveryResults(selectedJob || "");
  const importResults = useImportDiscoveryResults(selectedJob || "");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Device Discovery</h1>

      {isConfigWriter && (
        <form
          className="card flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            startDiscovery.mutate({
              cidr: String(form.get("cidr")),
              rate_limit_pps: Number(form.get("rate_limit_pps") || 20),
            });
          }}
        >
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            CIDR range
            <input name="cidr" required className="input" placeholder="10.10.0.0/28" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-400">
            Rate limit (pps)
            <input name="rate_limit_pps" className="input w-28" defaultValue={20} />
          </label>
          <button type="submit" className="btn-primary" disabled={startDiscovery.isPending}>
            Start discovery
          </button>
          {startDiscovery.isError && (
            <span className="text-xs text-red-400">{(startDiscovery.error as Error).message}</span>
          )}
        </form>
      )}

      <div className="card overflow-x-auto">
        <h3 className="mb-2 text-sm font-medium text-gray-300">Discovery jobs</h3>
        <table className="table-base">
          <thead>
            <tr>
              <th>CIDR</th>
              <th>Status</th>
              <th>Hosts</th>
              <th>Found</th>
              <th>Started</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs?.map((job) => (
              <tr key={job.id}>
                <td className="font-mono text-xs">{job.cidr}</td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td>{job.total_hosts ?? "-"}</td>
                <td>{job.found_count ?? "-"}</td>
                <td className="text-xs text-gray-400">{job.started_at ? new Date(job.started_at).toLocaleString() : "-"}</td>
                <td>
                  <button className="btn-secondary" onClick={() => setSelectedJob(job.id)}>
                    View results
                  </button>
                </td>
              </tr>
            ))}
            {!jobs?.length && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  No discovery jobs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedJob && (
        <form
          className="card overflow-x-auto"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const resultIds = Array.from(selectedResults);
            const overrides = resultIds.map((id) => ({
              result_id: id,
              hostname: String(form.get(`hostname_${id}`) || "") || undefined,
              device_type: String(form.get(`device_type_${id}`) || "") || undefined,
              department: String(form.get(`department_${id}`) || "") || undefined,
            }));
            importResults.mutate(
              { result_ids: resultIds, overrides },
              { onSuccess: () => setSelectedResults(new Set()) }
            );
          }}
        >
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-300">Results</h3>
            {isConfigWriter && (
              <button type="submit" className="btn-primary" disabled={!selectedResults.size || importResults.isPending}>
                Import selected ({selectedResults.size})
              </button>
            )}
          </div>
          <table className="table-base">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={
                      !!results?.length &&
                      results.filter((r) => !r.imported).every((r) => selectedResults.has(r.id))
                    }
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedResults(new Set(results?.filter((r) => !r.imported).map((r) => r.id)));
                      } else {
                        setSelectedResults(new Set());
                      }
                    }}
                  />
                </th>
                <th>IP</th>
                <th>Hostname</th>
                <th>Open ports</th>
                <th>SNMP</th>
                <th>Device type</th>
                <th>Department</th>
                <th>Imported</th>
              </tr>
            </thead>
            <tbody>
              {results?.map((r) => {
                const selected = selectedResults.has(r.id);
                return (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="checkbox"
                        disabled={r.imported}
                        checked={selected}
                        onChange={(e) => {
                          setSelectedResults((prev) => {
                            const next = new Set(prev);
                            if (e.target.checked) next.add(r.id);
                            else next.delete(r.id);
                            return next;
                          });
                        }}
                      />
                    </td>
                    <td className="font-mono text-xs">{r.ip_address}</td>
                    <td>
                      {r.imported ? (
                        r.hostname_guess || "-"
                      ) : (
                        <input
                          name={`hostname_${r.id}`}
                          className="input"
                          defaultValue={r.hostname_guess || ""}
                          placeholder={r.ip_address}
                          disabled={!selected}
                        />
                      )}
                    </td>
                    <td className="text-xs">{r.open_ports.join(", ") || "-"}</td>
                    <td>{r.snmp_reachable ? "yes" : "no"}</td>
                    <td>
                      {r.imported ? (
                        r.suggested_device_type || "-"
                      ) : (
                        <select
                          name={`device_type_${r.id}`}
                          className="input"
                          defaultValue={r.suggested_device_type || "GENERIC"}
                          disabled={!selected}
                        >
                          {DEVICE_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>
                      {r.imported ? (
                        "-"
                      ) : (
                        <input name={`department_${r.id}`} className="input" disabled={!selected} />
                      )}
                    </td>
                    <td>{r.imported ? "yes" : "no"}</td>
                  </tr>
                );
              })}
              {!results?.length && (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-gray-500">
                    No results yet -- job may still be running.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </form>
      )}
    </div>
  );
}
