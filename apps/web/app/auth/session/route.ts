import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

function equal(value: string, expected: string): boolean {
  const actualBuffer = Buffer.from(value);
  const expectedBuffer = Buffer.from(expected);
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

export async function POST(request: NextRequest) {
  const expectedEmail = process.env.ADMIN_LOGIN_EMAIL?.trim().toLowerCase();
  const expectedPasswordHash = process.env.ADMIN_PASSWORD_SHA256?.trim().toLowerCase();
  if (!expectedEmail || !expectedPasswordHash) {
    return NextResponse.json({ detail: "Administrator login is not configured" }, { status: 503 });
  }

  const body = await request.json().catch(() => null) as { email?: string; password?: string } | null;
  const email = body?.email?.trim().toLowerCase() ?? "";
  const passwordHash = createHash("sha256").update(body?.password ?? "").digest("hex");
  if (!equal(email, expectedEmail) || !equal(passwordHash, expectedPasswordHash)) {
    return NextResponse.json({ detail: "Incorrect email or password" }, { status: 401 });
  }

  const expires = Date.now() + 8 * 60 * 60 * 1000;
  const response = NextResponse.json({ ok: true });
  response.cookies.set("labora_session", String(expires), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 8 * 60 * 60
  });
  return response;
}
