import { NextRequest, NextResponse } from "next/server";
import { apiBaseUrl, applySessionCookies } from "@/lib/auth-cookies";
import { discoverOidc, oidcConfigured, oidcRedirectUri } from "@/lib/oidc";
import { cookieSecure } from "@/lib/session";

type TokenResponse = {
  id_token?: string;
  access_token?: string;
  error?: string;
  error_description?: string;
};

type SessionResponse = {
  access_token: string;
  expires_at: string;
  email: string;
  permissions: string[];
  detail?: string;
};

export async function GET(request: NextRequest) {
  if (!oidcConfigured()) {
    return NextResponse.redirect(new URL("/login?reason=oidc_unconfigured", request.url));
  }

  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");
  if (error) {
    return NextResponse.redirect(new URL(`/login?reason=oidc_${error}`, request.url));
  }
  if (!code || !state) {
    return NextResponse.redirect(new URL("/login?reason=oidc_missing_code", request.url));
  }

  const expectedState = request.cookies.get("labora_oidc_state")?.value;
  const verifier = request.cookies.get("labora_oidc_verifier")?.value;
  const returnTo = request.cookies.get("labora_oidc_return")?.value ?? "/dashboard";
  if (!expectedState || expectedState !== state || !verifier) {
    return NextResponse.redirect(new URL("/login?reason=oidc_state", request.url));
  }

  const issuer = process.env.OIDC_ISSUER!.trim();
  const clientId = process.env.OIDC_CLIENT_ID!.trim();
  const clientSecret = process.env.OIDC_CLIENT_SECRET?.trim();
  const discovery = await discoverOidc(issuer);
  const redirectUri = oidcRedirectUri(request.nextUrl.origin);

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: verifier
  });
  if (clientSecret) {
    body.set("client_secret", clientSecret);
  }

  const tokenResponse = await fetch(discovery.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });
  const tokenPayload = (await tokenResponse.json().catch(() => ({}))) as TokenResponse;
  if (!tokenResponse.ok || !tokenPayload.id_token) {
    return NextResponse.redirect(new URL("/login?reason=oidc_token", request.url));
  }

  const sessionResponse = await fetch(`${apiBaseUrl()}/auth/oidc/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: tokenPayload.id_token })
  });
  const session = (await sessionResponse.json().catch(() => ({}))) as SessionResponse;
  if (!sessionResponse.ok || !session.access_token) {
    return NextResponse.redirect(new URL("/login?reason=oidc_provision", request.url));
  }

  const destination = returnTo.startsWith("/") ? returnTo : "/dashboard";
  const response = NextResponse.redirect(new URL(destination, request.url));
  applySessionCookies(response, session);
  for (const name of ["labora_oidc_verifier", "labora_oidc_state", "labora_oidc_return"]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      secure: cookieSecure(),
      sameSite: "lax",
      path: "/",
      maxAge: 0
    });
  }
  return response;
}
