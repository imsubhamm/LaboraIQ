export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type RecordValue = string | number | boolean | null | undefined;
export type ApiRecord = Record<string, RecordValue>;

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Dev-User-Email": "admin@dev.labora.local",
      ...init?.headers
    },
    cache: "no-store"
  });
  if (response.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login?reason=expired");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

