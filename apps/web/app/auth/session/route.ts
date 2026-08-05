import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { apiBaseUrl, applySessionCookies } from "@/lib/auth-cookies";

function equal(value: string, expected: string): boolean {
  const actualBuffer = Buffer.from(value);
  const expectedBuffer = Buffer.from(expected);
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

type SessionResponse = {
  access_token: string;
  expires_at: string;
  email: string;
  permissions: string[];
  detail?: string;
};

export async function POST(request: NextRequest) {
  const expectedEmail = process.env.ADMIN_LOGIN_EMAIL?.trim().toLowerCase();
  const expectedPasswordHash = process.env.ADMIN_PASSWORD_SHA256?.trim().toLowerCase();
  if (!expectedEmail || !expectedPasswordHash) {
    return NextResponse.json({ detail: "Administrator login is not configured" }, { status: 503 });
  }

  const body = (await request.json().catch(() => null)) as { email?: string; password?: string } | null;
  const email = body?.email?.trim().toLowerCase() ?? "";
  const passwordHash = createHash("sha256").update(body?.password ?? "").digest("hex");
  if (!equal(email, expectedEmail) || !equal(passwordHash, expectedPasswordHash)) {
    return NextResponse.json({ detail: "Incorrect email or password" }, { status: 401 });
  }

  // Exchange the validated admin identity for a signed LaboraIQ API session JWT.
  // Requires API DEV_AUTH_ENABLED (local/UAT). Production should use OIDC instead.
  const apiResponse = await fetch(`${apiBaseUrl()}/auth/session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Dev-User-Email": email
    }
  });
  const session = (await apiResponse.json().catch(() => ({}))) as SessionResponse;
  if (!apiResponse.ok || !session.access_token) {
    const detail =
      typeof session.detail === "string"
        ? session.detail
        : "Unable to establish an API session for this administrator";
    return NextResponse.json({ detail }, { status: apiResponse.status === 401 ? 401 : 503 });
  }

  const response = NextResponse.json({
    ok: true,
    access_token: session.access_token,
    expires_at: session.expires_at,
    email: session.email,
    permissions: session.permissions
  });
  applySessionCookies(response, session);
  return response;
}
