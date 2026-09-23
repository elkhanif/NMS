"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useDetectiveSearch } from "@/lib/api";

export default function DetectivePage() {
  return (
    <Suspense fallback={<div className="text-gray-400">Loading...</div>}>
      <DetectiveSearchInner />
    </Suspense>
  );
}

function DetectiveSearchInner() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQ);
  const [submitted, setSubmitted] = useState(initialQ);
  const router = useRouter();
  const { data, isLoading } = useDetectiveSearch(submitted);

  useEffect(() => {
    if (data?.matches.length === 1) {
      router.push(`/detective/${data.matches[0].device_id}`);
    }
  }, [data, router]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Network Detective</h1>
      <p className="text-sm text-gray-400">Search by IP address, MAC address, hostname, device ID, or serial number.</p>

      <form
        className="card flex gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(query.trim());
        }}
      >
        <input
          className="input flex-1 font-mono"
          placeholder="192.168.10.45"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <button type="submit" className="btn-primary">
          Investigate
        </button>
      </form>

      {isLoading && <p className="text-sm text-gray-500">Searching...</p>}

      {submitted && !isLoading && data && data.matches.length !== 1 && (
        <div className="card">
          {data.matches.length ? (
            <ul className="flex flex-col gap-1">
              {data.matches.map((m) => (
                <li key={`${m.device_id}-${m.match_type}`}>
                  <Link
                    href={`/detective/${m.device_id}`}
                    className="flex items-center justify-between rounded px-2 py-2 hover:bg-white/5"
                  >
                    <span className="flex items-center gap-3">
                      <span className="font-medium text-gray-100">{m.hostname}</span>
                      <span className="font-mono text-xs text-gray-500">{m.ip_address}</span>
                    </span>
                    <span className="text-xs text-gray-500">
                      matched {m.match_type.replace("_", " ")}: {m.matched_value}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-4 text-center text-sm text-gray-500">No matches found for &quot;{submitted}&quot;.</p>
          )}
        </div>
      )}
    </div>
  );
}
