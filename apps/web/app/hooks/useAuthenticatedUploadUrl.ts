import { useEffect, useState } from "react";
import { toApiUrl } from "../../lib/api";

// Private file credentials travel only in headers. Blob URLs are revoked when
// the source or account changes, including requests that finish after cleanup.
export function useAuthenticatedUploadUrl(source: string, token: string): string {
  const [loaded, setLoaded] = useState<{ source: string; token: string; url: string } | null>(null);
  useEffect(() => {
    if (!source || !token) return;
    const url = new URL(source, toApiUrl("/"));
    const apiOrigin = new URL(toApiUrl("/")).origin;
    if (url.origin !== apiOrigin || !url.pathname.startsWith("/api/uploads/")) return;
    url.search = "";
    url.hash = "";
    const controller = new AbortController();
    let objectUrl = "";
    void fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
      cache: "no-store",
      redirect: "error",
    }).then(async (response) => {
      if (!response.ok) throw new Error("Private file unavailable");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setLoaded({ source, token, url: objectUrl });
    }).catch(() => {
      // Existing empty-preview handling remains available after a failed fetch.
    });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [source, token]);
  return loaded?.source === source && loaded.token === token ? loaded.url : "";
}
