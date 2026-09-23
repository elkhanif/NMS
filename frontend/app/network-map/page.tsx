"use client";

import { useMemo, useState } from "react";

import { useTopology } from "@/lib/api";
import type { DeviceStatus, DeviceType } from "@/lib/types";

import { TopologyCanvas } from "@/components/TopologyCanvas";

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

export default function NetworkMapPage() {
  const { data: graph, isLoading } = useTopology();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<DeviceType | "">("");
  const [statusFilter, setStatusFilter] = useState<DeviceStatus | "">("");

  const filteredNodes = useMemo(() => {
    if (!graph) return [];
    return graph.nodes.filter((n) => {
      if (typeFilter && n.device_type !== typeFilter) return false;
      if (statusFilter && n.status !== statusFilter) return false;
      return true;
    });
  }, [graph, typeFilter, statusFilter]);

  const filteredIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);
  const filteredEdges = useMemo(
    () => (graph ? graph.edges.filter((e) => filteredIds.has(e.parent_device_id) && filteredIds.has(e.child_device_id)) : []),
    [graph, filteredIds]
  );

  const searchMatch = useMemo(() => {
    if (!search) return null;
    return filteredNodes.find(
      (n) => n.hostname.toLowerCase().includes(search.toLowerCase()) || n.ip_address.includes(search)
    );
  }, [search, filteredNodes]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Network Map</h1>

      <div className="card flex flex-wrap gap-3">
        <input
          className="input flex-1 min-w-[180px]"
          placeholder="Search device..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as DeviceType | "")}>
          <option value="">All types</option>
          {DEVICE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as DeviceStatus | "")}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <div className="text-gray-400">Loading topology...</div>}
      {!isLoading && graph && (
        <TopologyCanvas nodes={filteredNodes} edges={filteredEdges} highlightId={searchMatch?.id} />
      )}
      {!isLoading && graph && graph.nodes.length === 0 && (
        <div className="card text-gray-400">
          No devices yet. Add devices and topology relationships to see them here.
        </div>
      )}
    </div>
  );
}
