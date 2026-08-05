import { NextRequest, NextResponse } from "next/server";
import { createPkcePair, createOidcState, discoverOidc, oidcConfigured, oidcRedirectUri } from "@/lib/oidc";
import { cookieSecure } from "@/lib/session";

export async function GET(request: NextRequest) {
  if (!oidcConfigured()) {
    return NextResponse.redirect(new URL("/login?reason=oidc_unconfigured", request.url));
  }
  const issuer = process.env.OIDC_ISSUER!.trim();
  const clientId = process.env.OIDC_CLIENT_ID!.trim();
  const discovery = await discoverOidc(issuer);
  const { verifier, challenge } = createPkcePair();
  const state = createOidcState();
  const returnTo = request.nextUrl.searchParams.get("returnTo");
  const redirectUri = oidcRedirectUri(request.nextUrl.origin);

  const authorize = new URL(discovery.authorization_endpoint);
  authorize.searchParams.set("response_type", "code");
  authorize.searchParams.set("client_id", clientId);
  authorize.searchParams.set("redirect_uri", redirectUri);
  authorize.searchParams.set("scope", process.env.OIDC_SCOPES?.trim() || "openid profile email");
  authorize.searchParams.set("state", state);
  authorize.searchParams.set("code_challenge", challenge);
  authorize.searchParams.set("code_challenge_method", "S256");
  if (process.env.OIDC_AUDIENCE?.trim()) {
    authorize.searchParams.set("audience", process.env.OIDC_AUDIENCE.trim());
  }

  const response = NextResponse.redirect(authorize);
  response.cookies.set("labora_oidc_verifier", verifier, {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    path: "/",
    maxAge: 600
  });
  response.cookies.set("labora_oidc_state", state, {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    path: "/",
    maxAge: 600
  });
  if (returnTo?.startsWith("/")) {
    response.cookies.set("labora_oidc_return", returnTo, {
      httpOnly: true,
      secure: cookieSecure(),
      sameSite: "lax",
      path: "/",
      maxAge: 600
    });
  }
  return response;
}
