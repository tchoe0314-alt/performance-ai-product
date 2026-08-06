const ENV_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";

function normalizeApiBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

function resolveApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8002";
  }

  const { hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    if (ENV_API_BASE_URL) {
      return normalizeApiBaseUrl(ENV_API_BASE_URL);
    }
    return "http://127.0.0.1:8002";
  }

  if (ENV_API_BASE_URL) {
    const normalized = normalizeApiBaseUrl(ENV_API_BASE_URL);
    if (!/localhost|127\\.0\\.0\\.1/.test(normalized)) {
      return normalized;
    }
  }

  return "https://api.civoraai.com";
}

const API_BASE_URL = resolveApiBaseUrl();

type RequestOptions = {
  token?: string | null;
  signal?: AbortSignal;
};

export type ApiErrorKind =
  | "auth_expired"
  | "backend_unreachable"
  | "api_blocked"
  | "rate_limited"
  | "upload_too_large"
  | "unsupported_file"
  | "request_failed";

class CivoraApiError extends Error {
  kind: ApiErrorKind;
  status?: number;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = "CivoraApiError";
    this.kind = kind;
    this.status = status;
  }
}

export function classifyApiError(error: unknown): ApiErrorKind {
  if (error instanceof CivoraApiError) return error.kind;
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (message.includes("session expired") || message.includes("sign in again")) return "auth_expired";
    if (message.includes("could not reach the backend") || message.includes("backend url")) return "backend_unreachable";
    if (message.includes("cors") || message.includes("api blocked")) return "api_blocked";
    if (message.includes("too many requests") || message.includes("rate")) return "rate_limited";
    if (message.includes("too large")) return "upload_too_large";
    if (message.includes("not supported") || message.includes("unsupported")) return "unsupported_file";
  }
  return "request_failed";
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function buildHeaders(token?: string | null, json = true): HeadersInit {
  const headers: Record<string, string> = {};

  if (json) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

export function toApiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  if (!API_BASE_URL) {
    throw new Error(
      "Civora AI cannot reach the backend right now. Set NEXT_PUBLIC_API_BASE_URL to your live backend URL.",
    );
  }
  return `${API_BASE_URL}${path}`;
}

function formatNetworkError(error: unknown): Error {
  if (error instanceof Error) {
    if (error.name === "AbortError") {
      return error;
    }
    if (error.message.includes("NEXT_PUBLIC_API_BASE_URL")) {
      return error;
    }
    if (error.name === "TypeError" || /fetch/i.test(error.message)) {
      return new CivoraApiError(
        "Backend unreachable or CORS/API blocked. Check the backend URL, CORS settings, and deployment health, then retry.",
        "backend_unreachable",
      );
    }
    return error;
  }

  return new CivoraApiError("Backend unreachable. Check the backend URL and retry.", "backend_unreachable");
}

type ReadJsonResponseOptions = {
  preserveUnauthorizedDetail?: boolean;
};

async function readJsonResponse<T>(
  response: Response,
  options: ReadJsonResponseOptions = {},
): Promise<T> {
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const rawDetail =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.message === "string"
          ? payload.message
          : `Request failed with status ${response.status}`;
    const detail =
      response.status === 401 && !options.preserveUnauthorizedDetail
        ? "Session expired. Sign in again."
        : response.status === 403
          ? rawDetail || "This account does not have access to that action."
          : response.status === 413
            ? rawDetail || "Upload too large. Choose a smaller file or compress it, then retry."
            : response.status === 415
              ? rawDetail || "Unsupported file. Use an accepted file type for this upload."
              : response.status === 429
                ? rawDetail || "Rate limited. Wait about a minute, then try again."
                : rawDetail;
    const kind: ApiErrorKind =
      response.status === 401 && !options.preserveUnauthorizedDetail
        ? "auth_expired"
        : response.status === 403
          ? "api_blocked"
          : response.status === 413
            ? "upload_too_large"
            : response.status === 415
              ? "unsupported_file"
              : response.status === 429
                ? "rate_limited"
                : "request_failed";
    throw new CivoraApiError(detail, kind, response.status);
  }

  return payload as T;
}

export async function getJson<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(toApiUrl(path), {
      method: "GET",
      cache: "no-store",
      headers: buildHeaders(options.token, false),
      signal: options.signal,
    });
  } catch (error) {
    throw formatNetworkError(error);
  }
  return readJsonResponse<T>(response);
}

export async function postJson<T>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(toApiUrl(path), {
      method: "POST",
      headers: buildHeaders(options.token, true),
      body: JSON.stringify(body),
      signal: options.signal,
    });
  } catch (error) {
    throw formatNetworkError(error);
  }
  return readJsonResponse<T>(response, {
    preserveUnauthorizedDetail: path === "/api/auth/login",
  });
}

export async function postJsonWithTimeout<T>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
  timeoutMs = 60000,
): Promise<T> {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort();
  options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await postJson<T>(path, body, { ...options, signal: controller.signal });
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw new CivoraApiError(
        "Source lookup took too long. The site stayed editable; retry source discovery or continue with manual/survey evidence.",
        "request_failed",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function patchJson<T>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(toApiUrl(path), {
      method: "PATCH",
      headers: buildHeaders(options.token, true),
      body: JSON.stringify(body),
      signal: options.signal,
    });
  } catch (error) {
    throw formatNetworkError(error);
  }
  return readJsonResponse<T>(response);
}

export async function postForm<T>(
  path: string,
  formData: FormData,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(toApiUrl(path), {
      method: "POST",
      headers: options.token ? buildHeaders(options.token, false) : undefined,
      body: formData,
      signal: options.signal,
    });
  } catch (error) {
    throw formatNetworkError(error);
  }
  return readJsonResponse<T>(response);
}

export async function deleteJson<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(toApiUrl(path), {
      method: "DELETE",
      headers: buildHeaders(options.token, false),
      signal: options.signal,
    });
  } catch (error) {
    throw formatNetworkError(error);
  }
  return readJsonResponse<T>(response);
}
