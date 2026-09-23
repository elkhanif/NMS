import { NextRequest, NextResponse } from "next/server";

import { apiBase, setAuthCookies } from "@/lib/cookies";

export async function POST(request: NextRequest) {
  const body = await request.json();

  const resp = await fetch(`${apiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json(detail, { status: resp.status });
  }

  const tokens = await resp.json();
  const meResp = await fetch(`${apiBase()}/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  const me = meResp.ok ? await meResp.json() : null;

  const res = NextResponse.json({ email: me?.email ?? null, role: me?.role ?? null });
  setAuthCookies(res, tokens.access_token, tokens.refresh_token, me);
  return res;
}
