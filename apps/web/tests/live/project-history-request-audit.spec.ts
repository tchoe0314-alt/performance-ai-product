import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { auditProjectHistoryRequests } from "./helpers/projectHistoryRequestAudit";

// Tests the test adapter, not Civora engineering or backend behavior. Every URL
// is intercepted; the API proof stand-in is explicit and never reaches a server.
const origin = "http://127.0.0.1:49741";
const token = "synthetic-adapter-only";
const project = { project_id: "synthetic", revision_token: "revision-b", name: "Synthetic project" };
const history = { project_id: "synthetic", calculations: [], last_successful_calculation_at: null };
const proofApi = { get: async (url: string) => ({ status: () => 200,
  json: async () => url.endsWith("/calculations") ? history : { project } }) } as unknown as APIRequestContext;
type FixtureWindow = Window & { controller?: AbortController; pending?: Promise<unknown> };

async function fixture(page: Page, mode = "normal") {
  const audit = await auditProjectHistoryRequests(page, origin, token);
  const failures: string[] = [];
  page.on("requestfailed", request => failures.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`));
  let held: Route | undefined;
  let holdHistory = false;
  await page.route(`${origin}/**`, async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path === "/audit-fixture") return route.fulfill({ contentType: "text/html", body: `
      <button aria-label="Project details" onclick="document.querySelector('section').hidden=false">Details</button>
      <section hidden data-testid="project-header-details">
        <label>Project name<input value="Synthetic project"></label>
        <dl><div><dt>Active revision</dt><dd>${mode === "stale header" ? "revision-a" : "revision-b"}</dd></div>
        <div><dt>Last calculation</dt><dd>Not recorded</dd></div></dl>
        <button aria-label="Close project details" onclick="document.querySelector('section').hidden=true">Close</button>
      </section>` });
    if (path === "/api/projects" && request.method() === "POST") {
      if (request.postDataJSON()?.cancelWrite) { held = route; return; }
      return route.fulfill({ json: { project } });
    }
    if (path.endsWith("/calculations")) {
      if (holdHistory) { holdHistory = false; held = route; return; }
      return route.fulfill({ status: mode === "server failure" ? 503 : 200,
        json: mode === "malformed body" ? { invalid: true } : history });
    }
    return route.fulfill({ status: 404, json: { detail: "Unsupported adapter fixture request" } });
  });
  await page.goto(`${origin}/audit-fixture`);
  await page.evaluate(async () => { await fetch("/api/projects", { method: "POST",
    headers: { Authorization: "Bearer synthetic-adapter-only", "Content-Type": "application/json" }, body: "{}" }); });
  return { audit, failures,
    async startHeld(write = false) {
      held = undefined; holdHistory = !write;
      await page.evaluate(write => {
        const fixture = window as FixtureWindow;
        fixture.controller = new AbortController();
        fixture.pending = fetch(write ? "/api/projects" : "/api/projects/synthetic/calculations", {
          method: write ? "POST" : "GET", signal: fixture.controller.signal,
          headers: { Authorization: "Bearer synthetic-adapter-only", "Content-Type": "application/json" },
          ...(write ? { body: JSON.stringify({ cancelWrite: true }) } : {}),
        }).catch(() => null);
      }, write);
      await expect.poll(() => !!held).toBe(true);
    },
    async cancelAndReplace(replace = true, wrongActor = false, wrongProject = false, delay = 0) {
      await page.evaluate(async ({ replace, wrongActor, wrongProject, delay }) => {
        const fixture = window as FixtureWindow;
        const controller = fixture.controller, pending = fixture.pending;
        if (!controller || !pending) throw new Error("Synthetic request fixture was not started");
        const act = async () => {
          controller.abort();
          const next = replace ? fetch(`/api/projects/${wrongProject ? "other" : "synthetic"}/calculations`, {
            headers: { Authorization: `Bearer ${wrongActor ? "wrong-synthetic-actor" : "synthetic-adapter-only"}` },
          }).then(response => response.json()).catch(() => null) : Promise.resolve();
          await Promise.all([pending, next]);
        };
        if (delay) await new Promise<void>(resolve => setTimeout(() => { void act().then(resolve); }, delay));
        else await act();
      }, { replace, wrongActor, wrongProject, delay });
      await expect.poll(() => failures.length).toBeGreaterThan(0);
    },
  };
}

test("adapter accepts a proven replaced read and current displayed proof", async ({ page }) => {
  const f = await fixture(page); await f.startHeld(); await f.cancelAndReplace();
  expect(await f.audit.unexpectedFailures(f.failures, proofApi)).toEqual([]);
});

for (const mode of ["missing replacement", "server failure", "wrong actor", "wrong project", "stale header", "malformed body", "timeout"]) {
  test(`adapter fails closed: ${mode}`, async ({ page }) => {
    const f = await fixture(page, mode); await f.startHeld();
    await f.cancelAndReplace(mode !== "missing replacement", mode === "wrong actor", mode === "wrong project", mode === "timeout" ? 6000 : 0);
    try {
      const unexpected = await f.audit.unexpectedFailures(f.failures, proofApi);
      expect(unexpected.length).toBeGreaterThan(0);
    } catch (error) {
      expect(String(error)).toContain("Current history proof did not settle");
    }
  });
}

test("adapter never forgives a canceled write", async ({ page }) => {
  const f = await fixture(page); await f.startHeld(true); await f.cancelAndReplace();
  expect(await f.audit.unexpectedFailures(f.failures, proofApi)).toEqual(f.failures);
});

test("one proven cancellation cannot remove two identical error entries", async ({ page }) => {
  const f = await fixture(page); await f.startHeld(); await f.cancelAndReplace();
  const failures = [...f.failures, f.failures[0]];
  expect(await f.audit.unexpectedFailures(failures, proofApi)).toEqual([f.failures[0]]);
});
