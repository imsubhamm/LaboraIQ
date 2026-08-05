import { createHash, randomBytes } from "node:crypto";

export type OidcDiscovery = {
  authorization_endpoint: string;
  token_endpoint: string;
  jwks_uri?: string;
};

export function oidcConfigured(): boolean {
  return Boolean(process.env.OIDC_ISSUER?.trim() && process.env.OIDC_CLIENT_ID?.trim());
}

export function base64Url(buffer: Buffer): string {
  return buffer.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function createPkcePair(): { verifier: string; challenge: string } {
  const verifier = base64Url(randomBytes(32));
  const challenge = base64Url(createHash("sha256").update(verifier).digest());
  return { verifier, challenge };
}

export function createOidcState(): string {
  return base64Url(randomBytes(24));
}

export async function discoverOidc(issuer: string): Promise<OidcDiscovery> {
  const metadataUrl = `${issuer.replace(/\/$/, "")}/.well-known/openid-configuration`;
  const response = await fetch(metadataUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Unable to discover OIDC provider metadata");
  }
  const body = (await response.json()) as Partial<OidcDiscovery>;
  if (!body.authorization_endpoint || !body.token_endpoint) {
    throw new Error("OIDC discovery document is incomplete");
  }
  return {
    authorization_endpoint: body.authorization_endpoint,
    token_endpoint: body.token_endpoint,
    jwks_uri: body.jwks_uri
  };
}

export function oidcRedirectUri(origin: string): string {
  return process.env.OIDC_REDIRECT_URI?.trim() || `${origin}/auth/oidc/callback`;
}
