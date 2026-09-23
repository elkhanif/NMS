import { NextResponse } from "next/server";

import { clearAuthCookies } from "@/lib/cookies";

export async function POST() {
  const res = NextResponse.json({ detail: "Logged out" });
  clearAuthCookies(res);
  return res;
}
