import { toApiUrl } from "../lib/api";

const TOKEN_KEY = "civora-ai-token";
const LEGACY_TOKEN_KEY = "performance-ai-token";

export function getStoredToken() {
  if (typeof window === "undefined") {
    return "";
  }
  return (
    window.localStorage.getItem(TOKEN_KEY) ??
    window.localStorage.getItem(LEGACY_TOKEN_KEY) ??
    ""
  );
}

export function setStoredToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
}

export function uploadedImageSrc(pathOrUrl: string, token: string): string {
  const safeToken = encodeURIComponent(token);
  if (!pathOrUrl || !token) {
    return "";
  }

  if (pathOrUrl.startsWith("/api/uploads/")) {
    return `${toApiUrl(pathOrUrl)}?access_token=${safeToken}`;
  }

  const filename = pathOrUrl.split("/").pop();
  if (!filename) {
    return "";
  }

  return `${toApiUrl(`/api/uploads/${filename}`)}?access_token=${safeToken}`;
}
