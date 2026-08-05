export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type RecordValue = string | number | boolean | null | undefined;
export type ApiRecord = Record<string, RecordValue>;

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (!item || typeof item !== "object") return String(item);
      const issue = item as { msg?: unknown; loc?: unknown[] };
      const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : undefined;
      return `${field ? `${String(field)}: ` : ""}${String(issue.msg ?? "Invalid value")}`;
    });
    return messages.join("; ");
  }
  if (detail && typeof detail === "object" && "msg" in detail) {
    return String((detail as { msg: unknown }).msg);
  }
  return "Request failed";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
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
    throw new ApiError(response.status, errorMessage(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
