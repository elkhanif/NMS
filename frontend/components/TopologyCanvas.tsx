"use client";

import dagre from "dagre";
import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Position,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import type { TopologyEdge, TopologyNode } from "@/lib/types";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;

const STATUS_COLORS: Record<string, string> = {
  UP: "#22c55e",
  WARNING: "#eab308",
  CRITICAL: "#ef4444",
  DOWN: "#ef4444",
  UNKNOWN: "#6b7280",
};

type LayoutNode = Node & { _hostname: string; _ip: string };

function layout(nodes: TopologyNode[], edges: TopologyEdge[]): { nodes: LayoutNode[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 90 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.parent_device_id, e.child_device_id));

  dagre.layout(g);

  const downstreamOf = new Set<string>();
  const criticalIds = new Set(nodes.filter((n) => n.status === "DOWN" || n.status === "CRITICAL").map((n) => n.id));

  function markDownstream(id: string) {
    edges
      .filter((e) => e.parent_device_id === id)
      .forEach((e) => {
        if (!downstreamOf.has(e.child_device_id)) {
          downstreamOf.add(e.child_device_id);
          markDownstream(e.child_device_id);
        }
      });
  }
  criticalIds.forEach(markDownstream);

  const rfNodes: LayoutNode[] = nodes.map((n) => {
    const pos = g.node(n.id);
    const color = STATUS_COLORS[n.status] || STATUS_COLORS.UNKNOWN;
    const affected = downstreamOf.has(n.id);
    return {
      id: n.id,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {},
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      style: {
        width: NODE_WIDTH,
        border: `2px solid ${color}`,
        borderRadius: 8,
        background: "#111827",
        color: "#e5e7eb",
        opacity: affected ? 0.55 : 1,
        padding: 8,
      },
      _hostname: n.hostname,
      _ip: n.ip_address,
    };
  });

  const rfEdges: Edge[] = edges.map((e) => {
    const affected = downstreamOf.has(e.child_device_id) || criticalIds.has(e.parent_device_id);
    return {
      id: e.id,
      source: e.parent_device_id,
      target: e.child_device_id,
      animated: false,
      style: { stroke: affected ? "#ef4444" : "#4b5563", strokeDasharray: affected ? "6 3" : undefined },
    };
  });

  return { nodes: rfNodes, edges: rfEdges };
}

export function TopologyCanvas({
  nodes,
  edges,
  highlightId,
  highlightIds,
  onNodeClick,
}: {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  highlightId?: string | null;
  /** A set of node ids to highlight distinctly from `highlightId` -- used to mark an
   * incident's affected devices (red glow) rather than a single search match (blue ring). */
  highlightIds?: string[];
  onNodeClick?: (deviceId: string) => void;
}) {
  const { nodes: rfNodes, edges: rfEdges } = useMemo(() => layout(nodes, edges), [nodes, edges]);
  const highlightSet = useMemo(() => new Set(highlightIds || []), [highlightIds]);

  const nodesWithLabel: Node[] = rfNodes.map((n) => {
    const isHighlighted = n.id === highlightId;
    const isIncidentAffected = highlightSet.has(n.id);
    return {
      ...n,
      style: {
        ...n.style,
        boxShadow: isHighlighted ? "0 0 0 3px #3b82f6" : isIncidentAffected ? "0 0 0 3px #f97316" : undefined,
        cursor: onNodeClick ? "pointer" : undefined,
      },
      data: {
        label: (
          <div className="text-xs">
            <div className="font-semibold">{n._hostname}</div>
            <div className="text-gray-400">{n._ip}</div>
          </div>
        ),
      },
    };
  });

  return (
    <div style={{ height: "70vh" }} className="rounded-lg border border-panelborder overflow-hidden">
      <ReactFlow
        nodes={nodesWithLabel}
        edges={rfEdges}
        fitView
        minZoom={0.2}
        maxZoom={2}
        onNodeClick={onNodeClick ? (_, node) => onNodeClick(node.id) : undefined}
      >
        <Background color="#1f2937" gap={20} />
        <Controls />
        <MiniMap pannable zoomable style={{ background: "#111827" }} nodeColor={() => "#374151"} />
      </ReactFlow>
    </div>
  );
}
