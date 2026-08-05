import { NextRequest, NextResponse } from "next/server";

export function isSessionValid(value: string | undefined, now = Date.now()): boolean {
  if (!value) return false;
  const expiresAt = Number(value);
  return Number.isFinite(expiresAt) && expiresAt > now;
}

export function proxy(request: NextRequest) {
  if (process.env.DEV_AUTH_BYPASS === "true") return NextResponse.next();
  const session = request.cookies.get("labora_session")?.value;
  if (!isSessionValid(session)) {
    const login = new URL("/login", request.url);
    login.searchParams.set("returnTo", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/organizations/:path*", "/branches/:path*",
    "/departments/:path*", "/users/:path*", "/roles/:path*", "/audit/:path*",
    "/settings/:path*", "/clients/:path*", "/patients/:path*", "/payments/:path*",
    "/specimens/:path*", "/test-master/:path*", "/analyzers/:path*"]
};
