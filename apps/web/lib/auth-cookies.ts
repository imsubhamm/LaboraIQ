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

export function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
}
