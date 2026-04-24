import { clearTokens, getAccessToken, getRefreshToken, setAccessToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:6200";

type FetchOptions = RequestInit & {
  auth?: boolean;
  json?: unknown;
};

class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, payload: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

export { ApiError };

async function refreshAccess(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const data = (await res.json()) as { access_token: string };
  setAccessToken(data.access_token);
  return true;
}

export async function apiFetch<T = unknown>(
  path: string,
  { auth = true, json, headers, ...init }: FetchOptions = {},
): Promise<T> {
  const doRequest = async (): Promise<Response> => {
    const hdrs = new Headers(headers);
    if (json !== undefined) hdrs.set("Content-Type", "application/json");
    if (auth) {
      const token = getAccessToken();
      if (token) hdrs.set("Authorization", `Bearer ${token}`);
    }
    return fetch(`${API_URL}${path}`, {
      ...init,
      headers: hdrs,
      body: json !== undefined ? JSON.stringify(json) : init.body,
    });
  };

  let res = await doRequest();

  if (res.status === 401 && auth) {
    const refreshed = await refreshAccess();
    if (refreshed) res = await doRequest();
  }

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = await res.text();
    }
    throw new ApiError(res.status, payload);
  }

  if (res.status === 204) return undefined as T;

  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

export async function apiUpload<T = unknown>(
  path: string,
  file: File,
  fieldName = "file",
): Promise<T> {
  const form = new FormData();
  form.append(fieldName, file);

  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: form,
  });

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = await res.text();
    }
    throw new ApiError(res.status, payload);
  }
  return (await res.json()) as T;
}
