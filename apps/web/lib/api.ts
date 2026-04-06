const ENV_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";

function normalizeApiBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

function resolveApiBaseUrl(): string {
  if (ENV_API_BASE_URL) {
    return normalizeApiBaseUrl(ENV_API_BASE_URL);
  }

  if (typeof window === "undefined") {
    return "http://127.0.0.1:8002";
  }

  const { hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://127.0.0.1:8002";
  }

  return "";
}

export const API_BASE_URL = resolveApiBaseUrl();

type RequestOptions = {
  token?: string | null;
  signal?: AbortSignal;
};

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

function contentDispositionFilename(value: string | null): string | null {
  if (!value) return null;
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const simpleMatch = value.match(/filename="?([^"]+)"?/i);
  return simpleMatch?.[1] ?? null;
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
      return new Error(
        "Civora AI could not reach the backend. Check the live backend URL, CORS settings, and deployment health.",
      );
    }
    return error;
  }

  return new Error("Civora AI could not reach the backend.");
}

export async function readJsonResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.message === "string"
          ? payload.message
          : `Request failed with status ${response.status}`;
    throw new Error(detail);
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

export async function postBinary(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<{ blob: Blob; filename: string | null }> {
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

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.message === "string"
          ? payload.message
          : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return {
    blob: await response.blob(),
    filename: contentDispositionFilename(response.headers.get("content-disposition")),
  };
}
