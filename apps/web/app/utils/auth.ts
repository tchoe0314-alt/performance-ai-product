import { toApiUrl } from "../../lib/api";

const TOKEN_KEY = "civora-ai-token";
const LEGACY_TOKEN_KEY = "performance-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

export function getStoredToken() {
  if (typeof window === "undefined") {
    return "";
  }
  const token = window.sessionStorage.getItem(TOKEN_KEY) ??
    window.localStorage.getItem(TOKEN_KEY) ??
    window.localStorage.getItem(LEGACY_TOKEN_KEY) ?? "";
  // One-time migration for existing tabs; persistent copies are never retained.
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
  return token;
}

export function setStoredToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.sessionStorage.setItem(TOKEN_KEY, token);
  window.sessionStorage.setItem(SESSION_RESTORE_KEY, "1");
}

export function clearStoredToken() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(LEGACY_TOKEN_KEY);
  window.sessionStorage.removeItem(SESSION_RESTORE_KEY);
}

export function shouldRestoreStoredToken() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.sessionStorage.getItem(SESSION_RESTORE_KEY) === "1";
}

export function uploadedImageSrc(pathOrUrl: string, token: string): string {
  if (!pathOrUrl || !token) {
    return "";
  }

  if (pathOrUrl.startsWith("/api/uploads/")) {
    return toApiUrl(pathOrUrl.split("?")[0]);
  }

  const filename = pathOrUrl.split("?")[0].split("/").pop();
  if (!filename) {
    return "";
  }

  return toApiUrl(`/api/uploads/${filename}`);
}
