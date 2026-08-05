import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const encoder = new TextEncoder();

export function isLegacySessionValid(value: string | undefined, now = Date.now()): boolean {
  if (!value) return false;
  const expiresAt = Number(value);
  return Number.isFinite(expiresAt) && expiresAt > now;
}

export async function isSessionValid(value: string | undefined, now = Date.now()): Promise<boolean> {
  if (!value) return false;
  if (/^\d+$/.test(value)) {
    return isLegacySessionValid(value, now);
  }
  const secret = process.env.SESSION_SECRET?.trim();
  if (!secret) {
    // Without a shared secret, accept non-empty JWT-shaped cookies (API still enforces auth).
    return value.split(".").length === 3;
  }
  try {
    await jwtVerify(value, encoder.encode(secret), {
      issuer: "laboraiq",
      audience: "laboraiq-api"
    });
    return true;
  } catch {
    return false;
  }
}

export async function proxy(request: NextRequest) {
  if (process.env.DEV_AUTH_BYPASS === "true") return NextResponse.next();
  const session = request.cookies.get("labora_session")?.value;
  if (!(await isSessionValid(session))) {
    const login = new URL("/login", request.url);
    login.searchParams.set("returnTo", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/organizations/:path*",
    "/branches/:path*",
    "/departments/:path*",
    "/users/:path*",
    "/roles/:path*",
    "/audit/:path*",
    "/settings/:path*",
    "/clients/:path*",
    "/patients/:path*",
    "/payments/:path*",
    "/specimens/:path*",
    "/test-master/:path*",
    "/analyzers/:path*",
    "/results/:path*"
  ]
};
