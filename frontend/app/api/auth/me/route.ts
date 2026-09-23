import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/cookies";

export async function GET() {
  const sessionCookie = cookies().get(SESSION_COOKIE);
  if (!sessionCookie) {
    return NextResponse.json({ email: null, role: null }, { status: 200 });
  }
  try {
    const session = JSON.parse(sessionCookie.value);
    return NextResponse.json(session);
  } catch {
    return NextResponse.json({ email: null, role: null });
  }
}
