import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, apiBase, clearAuthCookies, setTokenCookies } from "@/lib/cookies";

async function forward(request: NextRequest, path: string[], accessToken: string | undefined): Promise<Response> {
  const url = new URL(request.url);
  const target = `${apiBase()}/${path.join("/")}${url.search}`;
  const method = request.method;
  const headers: Record<string, string> = {};
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.text() : undefined;

  return fetch(target, { method, headers, body, cache: "no-store" });
}

function passthrough(upstreamBody: string, upstream: Response): NextResponse {
  return new NextResponse(upstreamBody, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") || "application/json" },
  });
}

async function handle(request: NextRequest, context: { params: { path: string[] } }) {
  const cookieStore = cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;

  let upstream = await forward(request, context.params.path, accessToken);

  if (upstream.status === 401 && refreshToken) {
    const refreshResp = await fetch(`${apiBase()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (refreshResp.ok) {
      const tokens = await refreshResp.json();
      upstream = await forward(request, context.params.path, tokens.access_token);
      const res = passthrough(await upstream.text(), upstream);
      setTokenCookies(res, tokens.access_token, tokens.refresh_token);
      return res;
    }

    const res = NextResponse.json({ detail: "Session expired" }, { status: 401 });
    clearAuthCookies(res);
    return res;
  }

  return passthrough(await upstream.text(), upstream);
}

export { handle as GET, handle as POST, handle as PATCH, handle as PUT, handle as DELETE };
