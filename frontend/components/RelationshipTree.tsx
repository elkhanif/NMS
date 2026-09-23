import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import type { RelationshipNode } from "@/lib/types";

export function RelationshipTree({
  ancestors,
  deviceHostname,
  deviceStatus,
  childDevices,
}: {
  ancestors: RelationshipNode[];
  deviceHostname: string;
  deviceStatus: string;
  childDevices: RelationshipNode[];
}) {
  const chain = [...ancestors].reverse(); // topmost ancestor first, down to the direct parent

  if (!chain.length && !childDevices.length) {
    return <p className="text-sm text-gray-500">No topology relationships recorded for this device.</p>;
  }

  return (
    <div className="flex flex-col items-start gap-0 font-mono text-sm">
      {chain.map((node) => (
        <div key={node.device_id} className="flex flex-col items-start">
          <Link href={`/detective/${node.device_id}`} className="flex items-center gap-2 hover:underline">
            <StatusBadge status={node.status} />
            <span>{node.hostname}</span>
            {node.interface_name && <span className="text-xs text-gray-500">({node.interface_name})</span>}
          </Link>
          <span className="pl-3 text-gray-600">│</span>
        </div>
      ))}
      <div className="flex items-center gap-2 font-semibold text-blue-300">
        <StatusBadge status={deviceStatus} />
        <span>{deviceHostname}</span>
        <span className="text-xs text-gray-500">(this device)</span>
      </div>
      {childDevices.length > 0 && (
        <>
          <span className="pl-3 text-gray-600">│</span>
          <div className="flex flex-col gap-1 pl-3">
            {childDevices.map((c) => (
              <Link
                key={c.device_id}
                href={`/detective/${c.device_id}`}
                className="flex items-center gap-2 hover:underline"
              >
                <StatusBadge status={c.status} />
                <span>{c.hostname}</span>
                {c.interface_name && <span className="text-xs text-gray-500">({c.interface_name})</span>}
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
