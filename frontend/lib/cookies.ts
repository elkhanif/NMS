import { NextResponse } from "next/server";

export const ACCESS_COOKIE = "access_token";
export const REFRESH_COOKIE = "refresh_token";
export const SESSION_COOKIE = "session_info";

const isProd = process.env.NODE_ENV === "production";

export function apiBase(): string {
  return process.env.API_INTERNAL_BASE_URL || "http://localhost:8000/api/v1";
}

interface MeLike {
  email?: string | null;
  role?: string | null;
}

export function setTokenCookies(res: NextResponse, accessToken: string, refreshToken: string) {
  const commonOpts = { httpOnly: true, secure: isProd, sameSite: "lax" as const, path: "/" };
  res.cookies.set(ACCESS_COOKIE, accessToken, { ...commonOpts, maxAge: 60 * 15 });
  res.cookies.set(REFRESH_COOKIE, refreshToken, { ...commonOpts, maxAge: 60 * 60 * 24 * 7 });
}

export function setSessionCookie(res: NextResponse, me: MeLike | null) {
  res.cookies.set(SESSION_COOKIE, JSON.stringify({ email: me?.email ?? null, role: me?.role ?? null }), {
    httpOnly: false,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export function setAuthCookies(res: NextResponse, accessToken: string, refreshToken: string, me: MeLike | null) {
  setTokenCookies(res, accessToken, refreshToken);
  setSessionCookie(res, me);
}

export function clearAuthCookies(res: NextResponse) {
  res.cookies.set(ACCESS_COOKIE, "", { path: "/", maxAge: 0 });
  res.cookies.set(REFRESH_COOKIE, "", { path: "/", maxAge: 0 });
  res.cookies.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
}
