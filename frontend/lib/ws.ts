"use client";

import { useEffect, useRef } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

type LiveMessage = {
  type: "event" | "alert" | "incident";
  action: string;
  id?: string;
  device_id?: string;
};

const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000, 10_000];

function invalidate(qc: QueryClient, msg: LiveMessage) {
  if (msg.type === "event") {
    qc.invalidateQueries({ queryKey: ["events"] });
    qc.invalidateQueries({ queryKey: ["devices"] });
    qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qc.invalidateQueries({ queryKey: ["status-distribution"] });
    if (msg.device_id) {
      qc.invalidateQueries({ queryKey: ["device", msg.device_id] });
      qc.invalidateQueries({ queryKey: ["device-events", msg.device_id] });
    }
  } else if (msg.type === "alert") {
    qc.invalidateQueries({ queryKey: ["alerts"] });
    qc.invalidateQueries({ queryKey: ["devices"] });
    qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qc.invalidateQueries({ queryKey: ["status-distribution"] });
    if (msg.device_id) {
      qc.invalidateQueries({ queryKey: ["device-alerts", msg.device_id] });
      qc.invalidateQueries({ queryKey: ["device", msg.device_id] });
    }
  } else if (msg.type === "incident") {
    qc.invalidateQueries({ queryKey: ["incidents"] });
    if (msg.id) {
      qc.invalidateQueries({ queryKey: ["incident", msg.id] });
    }
  }
}

async function mintTicket(): Promise<string | null> {
  try {
    const resp = await fetch("/api/backend/ws/ticket", { method: "POST" });
    if (!resp.ok) return null;
    const body = (await resp.json()) as { ticket: string };
    return body.ticket;
  } catch {
    return null;
  }
}

export function useLiveUpdates(enabled: boolean) {
  const qc = useQueryClient();
  const attemptRef = useRef(0);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    stoppedRef.current = false;
    let socket: WebSocket | null = null;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    async function connect() {
      const ticket = await mintTicket();
      if (stoppedRef.current) return;
      if (!ticket) {
        scheduleReconnect();
        return;
      }
      const base = process.env.NEXT_PUBLIC_API_WS_URL || "ws://localhost:8000";
      socket = new WebSocket(`${base}/api/v1/ws?ticket=${encodeURIComponent(ticket)}`);

      socket.onopen = () => {
        attemptRef.current = 0;
      };
      socket.onmessage = (evt) => {
        try {
          invalidate(qc, JSON.parse(evt.data) as LiveMessage);
        } catch {
          /* ignore malformed messages */
        }
      };
      socket.onclose = () => {
        if (!stoppedRef.current) scheduleReconnect();
      };
      socket.onerror = () => {
        socket?.close();
      };
    }

    function scheduleReconnect() {
      const delay = RECONNECT_DELAYS_MS[Math.min(attemptRef.current, RECONNECT_DELAYS_MS.length - 1)];
      attemptRef.current += 1;
      retryTimeout = setTimeout(connect, delay);
    }

    connect();

    return () => {
      stoppedRef.current = true;
      if (retryTimeout) clearTimeout(retryTimeout);
      socket?.close();
    };
  }, [enabled, qc]);
}
