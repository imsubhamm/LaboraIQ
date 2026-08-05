import { NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  TOKEN_COOKIE,
  cookieSecure,
  sessionMaxAgeSeconds,
  type SessionPayload
} from "@/lib/session";

export function applySessionCookies(response: NextResponse, session: SessionPayload): NextResponse {
  const maxAge = sessionMaxAgeSeconds(session.expires_at);
  const common = {
    secure: cookieSecure(),
    sameSite: "lax" as const,
    path: "/",
    maxAge
  };
  // HttpOnly gate cookie for route protection.
  response.cookies.set(SESSION_COOKIE, session.access_token, {
    ...common,
    httpOnly: true
  });
  // Readable cookie so browser API calls can send Authorization: Bearer.
  response.cookies.set(TOKEN_COOKIE, session.access_token, {
    ...common,
    httpOnly: false
  });
  return response;
}

export function clearSessionCookies(response: NextResponse): NextResponse {
  for (const name of [SESSION_COOKIE, TOKEN_COOKIE]) {
    response.cookies.set(name, "", {
      httpOnly: name === SESSION_COOKIE,
      secure: cookieSecure(),
      sameSite: "lax",
      path: "/",
      maxAge: 0
    });
  }
  return response;
}

/**
 * Absolute API base for Next.js route handlers (Node fetch rejects relative URLs).
 * Prefer INTERNAL_API_URL on EC2/UAT where the browser uses a relative NEXT_PUBLIC_API_URL.
 */
export function apiBaseUrl(): string {
  const configured =
    process.env.INTERNAL_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://127.0.0.1:8000/api/v1";
  if (configured.startsWith("/")) {
    const origin = (process.env.INTERNAL_API_ORIGIN?.trim() || "http://127.0.0.1:8000").replace(
      /\/$/,
      ""
    );
    return `${origin}${configured}`;
  }
  return configured.replace(/\/$/, "");
}
