import { expect, type APIRequestContext, type Page, type Request } from "@playwright/test";
import { provenSupersededHistoryReads, type HistoryRequestObservation } from "./historyRequestEvidence";

type Observation = HistoryRequestObservation & { url: string; timestamp?: number | null };
type ProbeWindow = Window & { __civoraTestHistoryEvidence?: Observation[] };
function historyTimestamp(value: unknown): number | null {
  if (!value || typeof value !== "object") throw new Error("Missing history response");
  const data = value as { last_successful_calculation_at?: unknown; calculations?: unknown };
  if (!Array.isArray(data.calculations)) throw new Error("Invalid history response");
  const timestamp = data.last_successful_calculation_at ?? data.calculations
    .filter(entry => entry?.successful === true).map(entry => entry.created_at)
    .filter((entry): entry is number => typeof entry === "number" && Number.isFinite(entry))
    .sort((a, b) => b - a)[0];
  if (timestamp === undefined || timestamp === null) return null;
  if (typeof timestamp !== "number" || !Number.isFinite(timestamp)) throw new Error("Invalid history timestamp");
  return timestamp;
}

/** Test-only observer. No new fetches in the application, no change to cancellation.
 * Accept only explicitly recovered same-actor reads and authoritative header proof.
 */
export async function auditProjectHistoryRequests(page: Page, apiBase: string, token: string) {
  const origin = new URL(apiBase).origin;
  await page.addInitScript(({ origin, authorization }) => {
    const observations: Observation[] = [];
    (window as ProbeWindow).__civoraTestHistoryEvidence = observations;
    let order = 0;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, options) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, location.href);
      if (url.origin !== origin || !/^\/api\/projects\/[^/]+\/calculations$/.test(url.pathname))
        return originalFetch(input, options);
      const headers = new Headers(options?.headers ?? (input instanceof Request ? input.headers : undefined));
      const signal = options?.signal ?? (input instanceof Request ? input.signal : undefined);
      const observation: Observation = { id: observations.length + 1, url: url.href, path: url.pathname,
        method: options?.method ?? (input instanceof Request ? input.method : "GET"),
        actorMatches: headers.get("authorization") === authorization,
        startedAt: performance.now(), startedOrder: ++order };
      observations.push(observation);
      const aborted = () => { observation.abortOrder = ++order; };
      signal?.addEventListener("abort", aborted, { once: true });
      const failure = (error: unknown) => {
        if (observation.failedOrder !== undefined) return;
        observation.failedAt = performance.now(); observation.failedOrder = ++order;
        observation.error = error instanceof Error && error.name === "AbortError" ? "net::ERR_ABORTED" : "other-fetch-or-body-error";
      };
      try {
        const response = await originalFetch(input, options);
        observation.status = response.status;
        // Read a clone; do not consume/change the application's response. A
        // headers-only 200 never proves that the history body completed.
        void response.clone().json().then(data => {
          if (!Array.isArray(data?.calculations)) throw new Error("Invalid history body");
          const timestamp = data.last_successful_calculation_at ?? data.calculations
            .filter((entry: { successful?: boolean } | null) => entry?.successful === true)
            .map((entry: { created_at?: unknown }) => entry.created_at)
            .filter((value: unknown) => typeof value === "number" && Number.isFinite(value))
            .sort((a: number, b: number) => b - a)[0];
          if (timestamp != null && (typeof timestamp !== "number" || !Number.isFinite(timestamp)))
            throw new Error("Invalid history timestamp");
          observation.timestamp = timestamp ?? null;
          observation.completedAt = performance.now(); ++order;
        }).catch(failure).finally(() => signal?.removeEventListener("abort", aborted));
        return response;
      } catch (error) { failure(error); signal?.removeEventListener("abort", aborted); throw error; }
    };
  }, { origin, authorization: `Bearer ${token}` });
  const requests = new Map<Request, Observation>();
  const parsing: Promise<void>[] = [];
  let sequence = 0;
  let project: { id: string; sequence: number } | undefined;
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.origin !== origin || !url.pathname.startsWith("/api/projects")) return;
    requests.set(request, { id: ++sequence, url: request.url(), method: request.method(), path: url.pathname,
      actorMatches: request.headers().authorization === `Bearer ${token}`, startedAt: Date.now() });
  });
  page.on("response", response => {
    const observation = requests.get(response.request());
    if (!observation) return;
    observation.status = response.status();
    if (response.status() !== 200 || !observation.actorMatches) return;
    if (observation.path === "/api/projects" && observation.method === "POST") {
      parsing.push(response.json().then(data => {
        if (typeof data?.project?.project_id === "string" && (!project || observation.id > project.sequence))
          project = { id: data.project.project_id, sequence: observation.id };
      }).catch(() => { /* No usable project evidence: final proof must fail. */ }));
    } else if (/^\/api\/projects\/[^/]+\/calculations$/.test(observation.path) && observation.method === "GET") {
      parsing.push(response.json().then(data => { observation.timestamp = historyTimestamp(data); })
        .catch(() => { /* Undefined timestamp cannot establish matching history. */ }));
    }
  });
  page.on("requestfinished", request => {
    const observation = requests.get(request);
    if (observation) observation.completedAt = Date.now();
  });
  page.on("requestfailed", request => {
    const observation = requests.get(request);
    if (observation) { observation.failedAt = Date.now(); observation.error = request.failure()?.errorText ?? "unknown"; }
  });

  return { async unexpectedFailures(failures: string[], api: APIRequestContext): Promise<string[]> {
    await Promise.all(parsing);
    if (!project) throw new Error("No authenticated saved-project evidence was observed");
    const projectId = project.id;
    await page.getByRole("button", { name: "Project details", exact: true }).click();
    const details = page.getByTestId("project-header-details");
    const field = (name: string) => details.getByText(name, { exact: true }).locator("..").locator("dd");
    let accepted = new Set<number>();
    let lastFailure: unknown;
    await expect(async () => {
      try {
      const headers = { Authorization: `Bearer ${token}` };
      const recordResponse = await api.get(`${apiBase}/api/projects/${encodeURIComponent(projectId)}`, { headers });
      const historyResponse = await api.get(`${apiBase}/api/projects/${encodeURIComponent(projectId)}/calculations`, { headers });
      expect(recordResponse.status()).toBe(200); expect(historyResponse.status()).toBe(200);
      const record = (await recordResponse.json()).project;
      expect(record.project_id).toBe(projectId);
      expect(typeof record.revision_token).toBe("string"); expect(record.revision_token.length).toBeGreaterThan(0);
      const timestamp = historyTimestamp(await historyResponse.json());
      const displayedTimestamp = await page.evaluate(value => value === null ? "Not recorded" : new Date(value * 1000).toLocaleString(), timestamp);
      await expect(details.getByLabel("Project name", { exact: true })).toHaveValue(record.name);
      await expect(field("Active revision")).toHaveText(record.revision_token);
      await expect(field("Last calculation")).toHaveText(displayedTimestamp);
      await Promise.all(parsing);
      const observations = await page.evaluate(() => (window as ProbeWindow).__civoraTestHistoryEvidence ?? []);
      const path = `/api/projects/${encodeURIComponent(projectId)}/calculations`;
      const latest = observations.filter(item => item.path === path && item.actorMatches && item.method === "GET").at(-1);
      expect(latest?.status).toBe(200); expect(latest?.error).toBeUndefined();
      expect(latest?.completedAt).toBeDefined(); expect(latest?.timestamp).toBe(timestamp);
      accepted = provenSupersededHistoryReads(observations, { projectId, revision: record.revision_token,
        headerRevision: await field("Active revision").innerText(), headerNameMatches: true,
        headerHistoryMatches: true, historyResponseMatches: latest?.timestamp === timestamp });
      } catch (error) { lastFailure = error; throw error; }
    }).toPass({ timeout: 10000 }).catch(error => {
      throw new Error(`Current history proof did not settle: ${String(lastFailure)}`, { cause: error });
    });
    await page.getByRole("button", { name: "Close project details", exact: true }).click();
    // Multiset accounting: identical URL strings must not hide an unrelated failure.
    const allowances = new Map<string, number>();
    const clientObservations = await page.evaluate(() => (window as ProbeWindow).__civoraTestHistoryEvidence ?? []);
    for (const observation of clientObservations) if (accepted.has(observation.id)) {
      const key = `${observation.method} ${observation.url} ${observation.error}`;
      allowances.set(key, (allowances.get(key) ?? 0) + 1);
    }
    return failures.filter(failure => {
      const remaining = allowances.get(failure) ?? 0;
      if (!remaining) return true;
      allowances.set(failure, remaining - 1); return false;
    });
  } };
}
