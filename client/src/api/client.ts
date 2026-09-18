import { ApiError } from "@/types/api";

// Base URL — VITE_API_URL env var, default localhost:8001.
// Exported for raw fetch callers (e.g. binary PDF streams) that can't go
// through the JSON-shaped `request()` helper.
export const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

// Extract error message — handle string or array detail.
function extractDetail(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // FastAPI validation array — flatten first msg.
      const first = detail[0];
      if (first && typeof first === "object" && "msg" in first) {
        return String((first as { msg: unknown }).msg);
      }
      return JSON.stringify(detail);
    }
    return JSON.stringify(detail);
  }
  return "unknown error";
}

// Core fetch wrapper — JSON parse, error extract, 204 handling.
async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const init: RequestInit = {
    method,
    headers: {},
  };

  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Cannot reach server");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      // non-JSON error body (502 HTML, middleware) — throw with status text.
      throw new ApiError(res.statusText || "non-JSON error response", res.status);
    }
  }

  if (!res.ok) {
    const detail = extractDetail(parsed);
    throw new ApiError(detail, res.status);
  }

  return parsed as T;
}

// Typed helpers.
export function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, body);
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PUT", path, body);
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>("DELETE", path);
}