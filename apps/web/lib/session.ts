/** Cookie and client storage helpers for LaboraIQ session JWTs. */

export const SESSION_COOKIE = "labora_session";
export const TOKEN_COOKIE = "labora_token";
export const TOKEN_STORAGE_KEY = "labora_access_token";

export type SessionPayload = {
  access_token: string;
  expires_at: string;
  email?: string;
  permissions?: string[];
};

export function cookieSecure(): boolean {
  return process.env.NODE_ENV === "production";
}

export function sessionMaxAgeSeconds(expiresAt: string | Date): number {
  const expires = typeof expiresAt === "string" ? Date.parse(expiresAt) : expiresAt.getTime();
  const seconds = Math.floor((expires - Date.now()) / 1000);
  return Math.max(60, Math.min(seconds, 60 * 60 * 24));
}

export function readBrowserAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  if (stored) return stored;
  const match = document.cookie.match(/(?:^|; )labora_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function storeBrowserAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearBrowserAccessToken(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
}
