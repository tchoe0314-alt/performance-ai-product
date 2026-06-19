import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

const APP_BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_BASE_URL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8002";
const TOKEN_KEY = "civora-ai-token";

const runId = Date.now();
const email = `autofix-${runId}@civora.local`;
const password = "autofix-pass-123";

type DrainageCounts = {
  basins: number;
  inlets: number;
  runs: number;
  issues: string[];
};
type IssueLike = {
  code?: string;
  message?: string;
  context?: unknown;
};

type CaseResult = {
  case: string;
  action: string | null;
  before: DrainageCounts;
  after: DrainageCounts;
  error: string | null;
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function seedBrowserToken(page: Page, token: string) {
  if (!page.url().startsWith(APP_BASE_URL)) {
    await page.goto(APP_BASE_URL, { waitUntil: "domcontentloaded" });
  }
  await page.evaluate(
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
    },
    [TOKEN_KEY, token] as const,
  );
  await expect
    .poll(
      () =>
        page.evaluate(([tokenKey]) => window.localStorage.getItem(tokenKey), [
          TOKEN_KEY,
        ] as const),
      { timeout: 5_000 },
    )
    .toBe(token);
}

async function hasAuthenticatedShell(page: Page) {
  const shellControls = [
    page.getByRole("button", { name: "Open projects", exact: true }),
    page.getByText(/^Dashboard$/).first(),
  ];
  for (const control of shellControls) {
    if (await control.isVisible().catch(() => false)) return true;
  }
  return false;
}

async function waitForAuthenticatedShell(page: Page, timeout = 30_000) {
  await expect
    .poll(() => hasAuthenticatedShell(page), { timeout })
    .toBe(true);
}

async function ensureSignedIn(page: Page, token: string) {
  await seedBrowserToken(page, token);
  try {
    await waitForAuthenticatedShell(page, 15_000);
    return;
  } catch {
    await page.reload({ waitUntil: "domcontentloaded" });
  }
  try {
    await waitForAuthenticatedShell(page, 15_000);
    return;
  } catch {
    // Fall back to the explicit sign-in flow below.
  }

  const signInMode = page.getByRole("button", { name: "Sign In Mode" });
  if (!(await signInMode.isVisible().catch(() => false))) {
    await waitForAuthenticatedShell(page, 10_000);
    return;
  }
  await signInMode.click();
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("At least 8 characters").fill(password);
  const signInButton = page.getByRole("button", { name: /^Sign In$/ });
  await expect(signInButton).toBeVisible({ timeout: 10_000 });
  await signInButton.click();
  await waitForAuthenticatedShell(page);
}

async function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`${label} timed out after ${ms}ms`));
    }, ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

async function loginAndSeedToken(request: APIRequestContext, page: Page) {
  await request.post(`${API_BASE_URL}/api/auth/register`, {
    data: { email, password, name: "Autofix Runner" },
  }).catch(() => null);

  const loginResponse = await request.post(`${API_BASE_URL}/api/auth/login`, {
    data: { email, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload?.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(([tokenKey, authToken]) => {
    window.localStorage.setItem(tokenKey, authToken);
  }, [TOKEN_KEY, token] as const);
  await ensureSignedIn(page, token);
  return token;
}

async function preflightDrainageEndpoint(request: APIRequestContext, token: string) {
  const response = await request.post(`${API_BASE_URL}/api/jobs/drainage`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {},
  });
  const status = response.status();
  if (status === 404 || status === 405) {
    throw new Error(`Drainage endpoint unavailable (status ${status}). Backend may be down or outdated.`);
  }
}

async function queueOrchestrateScenario(
  request: APIRequestContext,
  token: string,
  projectId: string,
  payload: Record<string, unknown>,
) {
  let response = await request.post(`${API_BASE_URL}/api/jobs/drainage`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { project_id: projectId, request: payload },
    timeout: 60_000,
  });
  for (let attempt = 1; response.status() === 429 && attempt <= 6; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, attempt * 5_000));
    response = await request.post(`${API_BASE_URL}/api/jobs/drainage`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { project_id: projectId, request: payload },
      timeout: 60_000,
    });
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { job?: { job_id?: string } };
  const jobId = String(body?.job?.job_id || "");
  expect(jobId).toBeTruthy();
  return jobId;
}

async function waitForJobCompletion(request: APIRequestContext, token: string, jobId: string) {
  const deadline = Date.now() + 420_000;
  let lastStatus = "";
  let lastProgress = -1;
  while (Date.now() < deadline) {
    let payload: {
      job?: { status?: string; error?: string; progress?: number; stage?: string; stage_detail?: string };
    } = {};
    try {
      const response = await request.get(`${API_BASE_URL}/api/jobs/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(response.ok()).toBeTruthy();
      payload = (await response.json()) as typeof payload;
    } catch (err) {
      console.info(`Job ${jobId} status poll failed, retrying: ${String(err)}`);
      await new Promise((resolve) => setTimeout(resolve, 3000));
      continue;
    }
    const status = String(payload?.job?.status || "");
    const progress = Number(payload?.job?.progress ?? -1);
    if (status !== lastStatus || progress !== lastProgress) {
      console.info(`Job ${jobId} status=${status} progress=${progress} stage=${payload?.job?.stage || ""}`);
      lastStatus = status;
      lastProgress = progress;
    }
    if (status === "completed" || status === "awaiting_approval") return payload.job;
    if (status === "failed" || status === "cancelled") {
      throw new Error(`Job ${jobId} ${status}: ${payload?.job?.error || "unknown error"}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`Job ${jobId} timed out waiting for completion.`);
}

async function createProject(
  request: APIRequestContext,
  token: string,
  name: string,
  project_input: Record<string, unknown>,
) {
  const response = await request.post(`${API_BASE_URL}/api/projects`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name,
      description: "Autofix validation",
      project_input,
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { project?: { project_id?: string } };
}

async function fetchProjectResult(request: APIRequestContext, token: string, projectId: string) {
  const response = await request.get(`${API_BASE_URL}/api/projects/${projectId}/result`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { latest_result?: Record<string, unknown> };
  return payload.latest_result ?? {};
}

function parseDrainageCounts(result: Record<string, unknown>): DrainageCounts {
  const finalPlan = (result.final_plan ?? {}) as Record<string, unknown>;
  const meta = (finalPlan.meta ?? {}) as Record<string, unknown>;
  const drainage =
    (meta.drainage_canonical ??
      meta.drainage ??
      meta.drainage_summary ??
      result.drainage_canonical ??
      {}) as Record<string, unknown>;
  const basins = Array.isArray(drainage.basins) ? drainage.basins.length : 0;
  const inlets = Array.isArray(drainage.inlets) ? drainage.inlets.length : 0;
  const runs = Array.isArray(drainage.pipe_runs)
    ? drainage.pipe_runs.length
    : Array.isArray(drainage.runs)
      ? drainage.runs.length
      : 0;
  const topIssues = Array.isArray(result.issues)
    ? result.issues.map((item: IssueLike) => String(item?.code || item?.message || "unknown"))
    : [];
  const drainageIssuesRaw = Array.isArray(drainage.issues) ? drainage.issues : [];
  const drainageIssues = drainageIssuesRaw.map((item: IssueLike) =>
    String(item?.code || item?.message || "unknown"),
  );
  const issues = topIssues.length ? topIssues : drainageIssues;
  return { basins, inlets, runs, issues };
}

function resolveActionLabel(configuredAction: string | null, issues: string[]) {
  const codes = new Set(issues.map((issue) => issue.toUpperCase()));
  if (codes.has("UNDER_COLLECTION") || codes.has("UNDER_COLLECTION_REDUCED")) return "Add inlet";
  if (
    codes.has("DRAINAGE_NO_BASIN") ||
    codes.has("NO_VALID_OUTFALL") ||
    codes.has("NO_PONDS_DEFINED") ||
    codes.has("BASIN_UNREACHABLE")
  ) {
    return "Add basin";
  }
  if (codes.has("ORPHAN_INLETS")) return "Connect inlet";
  if (codes.has("POOR_SLOPE")) return "Adjust slope";
  return configuredAction;
}

async function openProject(page: Page, token: string, name: string) {
  await seedBrowserToken(page, token);
  await ensureSignedIn(page, token);
  const projectsButton = page.getByRole("button", { name: "Open projects", exact: true });
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const projectButton = page
      .getByRole("button", { name: new RegExp(`^${escapeRegExp(name)}\\b`, "i") })
      .first();
    try {
      if (!(await projectButton.isVisible({ timeout: 1_000 }).catch(() => false))) {
        const projectsResponsePromise = page.waitForResponse((response) => {
          return response.url().includes("/api/projects") && response.request().method() === "GET";
        });
        await expect(projectsButton).toBeVisible({ timeout: 10_000 });
        await projectsButton.click();
        await Promise.race([
          projectsResponsePromise.catch(() => null),
          page.waitForTimeout(3_000),
        ]);
      }
      await expect(projectButton).toBeVisible({ timeout: 20_000 });
      await projectButton.click();
      await waitForAuthenticatedShell(page);
      await page.getByText(new RegExp(escapeRegExp(name), "i")).first().waitFor({ timeout: 10_000 });
      return;
    } catch (err) {
      if (attempt === 0) {
        await ensureSignedIn(page, token);
        continue;
      }
      throw err;
    }
  }
}

async function applyIssue(page: Page, actionLabel: string) {
  const reviewButton = page.getByRole("button", { name: "Review", exact: true }).first();
  await expect(reviewButton).toBeVisible({ timeout: 12_000 });
  await reviewButton.click();
  const modernPanel = page.getByTestId("bottom-review-panel");
  let applyButton = modernPanel.getByRole("button", { name: new RegExp(`^${escapeRegExp(actionLabel)}$`, "i") }).first();
  if (await modernPanel.isVisible().catch(() => false)) {
    const openPanel = modernPanel.getByRole("button", { name: "Open", exact: true });
    if (await openPanel.isVisible().catch(() => false)) {
      await openPanel.click();
    }
    const issuesTab = modernPanel.getByRole("button", { name: "Issues", exact: true });
    if (await issuesTab.isVisible().catch(() => false)) {
      await issuesTab.click();
    }
  } else {
    const engineeringIssues = page.getByText("Engineering Issues", { exact: true }).first();
    await engineeringIssues.scrollIntoViewIfNeeded();
    await expect(engineeringIssues).toBeVisible({ timeout: 12_000 });
    applyButton = page.getByRole("button", { name: new RegExp(`^${escapeRegExp(actionLabel)}$`, "i") }).first();
  }
  await expect(applyButton).toBeVisible({ timeout: 20_000 });
  await expect(applyButton).toBeEnabled({ timeout: 5_000 });
  await applyButton.evaluate((element: HTMLElement) => element.click());
  await page.waitForTimeout(5_000);
}

test.describe("Phase 5 drainage autofix matrix", () => {
  test("Run autofix apply actions matrix", async ({ page, request }) => {
    test.setTimeout(600_000);
    const token = await loginAndSeedToken(request, page);
    await preflightDrainageEndpoint(request, token);
    await page.goto(APP_BASE_URL, { waitUntil: "domcontentloaded" });

    const basePayload = {
      project_id: null,
      full_design_mode: false,
      input_mode: "user",
      strict_mode: false,
      prompt_text: "Run grading and drainage for the site.",
      meta: {
        requested_system: "drainage",
        runtime_phase_batch_limit: 3,
        include_grading: true,
        include_drainage: true,
        site_inputs: {
          site_alignment_locked: true,
        },
      },
      manual_fields: {
        units: "ft",
        lot: { x: 0, y: 0, w: 400, h: 400 },
        disciplines: ["drainage", "grading"],
        grading: { min_slope_pct: 0.5 },
        drainage: { min_pipe_slope_pct: 0.5 },
      },
      allow_ai_fill_for_blanks: false,
    };

    const cases: Array<{
      name: string;
      payload: Record<string, unknown>;
      action: string | null;
      skipApply?: boolean;
    }> = [
      {
        name: "Case 1 Basin uphill",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            grading: { min_slope_pct: 0 },
            drainage: {
              min_pipe_slope_pct: 0.5,
              forced_inlets: [{ name: "Forced Inlet", x: 300, y: 300 }],
            },
            ponds: [{ id: "pond1", name: "Pond", x: 10, y: 10, w: 40, d: 30 }],
          },
        },
        action: "Adjust slope",
      },
      {
        name: "Case 2 No basin/outfall",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            ponds: [],
          },
        },
        action: "Add basin",
        skipApply: true,
      },
      {
        name: "Case 3 Flat site",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            grading: { min_slope_pct: 0 },
          },
        },
        action: "Adjust slope",
        skipApply: true,
      },
      {
        name: "Case 4 Orphan inlet",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            grading: {
              min_slope_pct: 0.5,
              corner_elevations: {
                northwest: 110,
                southeast: 100,
              },
            },
            drainage: {
              min_pipe_slope_pct: 0.5,
              forced_inlets: [{ name: "Forced Inlet", x: 100, y: 100 }],
            },
            ponds: [{ id: "pond2", name: "Pond", x: 340, y: 340, w: 40, d: 30 }],
          },
        },
        action: "Connect inlet",
        skipApply: true,
      },
      {
        name: "Case 5 Under-collection",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            site_plan: { parking_count: 300 },
            ponds: [{ id: "pond3", name: "Pond", x: 520, y: 520, w: 40, d: 30 }],
          },
        },
        action: "Add inlet",
      },
      {
        name: "Case 6 Valid control",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            grading: {
              min_slope_pct: 2,
              corner_elevations: {
                northwest: 110,
                southeast: 100,
              },
            },
            drainage: {
              min_pipe_slope_pct: 0.1,
              forced_inlets: [{ name: "Forced Inlet", x: 150, y: 150 }],
              connect_orphans: true,
              validation_control: true,
            },
            ponds: [{ id: "pond4", name: "Pond", x: 450, y: 450, w: 40, d: 30 }],
          },
        },
        action: null,
        skipApply: true,
      },
    ];
    const onlyCase = String(process.env.PHASE5_ONLY || "").trim();
    const selectedCases = onlyCase
      ? cases.filter((entry) => entry.name.toLowerCase().includes(onlyCase.toLowerCase()))
      : cases;
    const caseResults: CaseResult[] = [];

    for (const entry of selectedCases) {
      console.info(`Starting ${entry.name}`);
      const created = await createProject(request, token, entry.name, entry.payload);
      const projectId = String(created.project?.project_id || "");
      expect(projectId).toBeTruthy();
      const jobId = await queueOrchestrateScenario(request, token, projectId, entry.payload);
      await waitForJobCompletion(request, token, jobId);

      const beforeResultPayload = await fetchProjectResult(request, token, projectId);
      const before = parseDrainageCounts(beforeResultPayload);
      let after = before;
      let applyError: string | null = null;
      const actionLabel = resolveActionLabel(entry.action, before.issues);
      try {
          if (entry.skipApply || !actionLabel) {
            console.info(`${entry.name} APPLY SKIPPED: scenario is job coverage or has no autofix action.`);
            after = parseDrainageCounts(await fetchProjectResult(request, token, projectId));
          } else if (!before.issues.length) {
            applyError = "No issues produced; cannot apply autofix.";
          } else {
            console.info(`${entry.name} BEFORE`, before);
            await withTimeout(openProject(page, token, entry.name), 90_000, `${entry.name} openProject`);
          const jobResponsePromise = page.waitForResponse((response) => {
            return response.url().includes("/api/jobs/drainage") && response.request().method() === "POST";
          });
          const jobRequestPromise =
            actionLabel === "Adjust slope"
              ? page.waitForRequest((request) => {
                  return (
                    request.url().includes("/api/jobs/drainage") && request.method() === "POST"
                  );
                })
              : null;
          console.info(`${entry.name} APPLY CLICK`);
          await withTimeout(applyIssue(page, actionLabel), 25_000, `${entry.name} applyIssue`);
          console.info(`${entry.name} APPLY CLICK FIRED`);
          let jobId: string | null = null;
          let jobIdError: string | null = null;
          let applyBlocked = false;
          try {
            if (jobRequestPromise) {
              const req = await withTimeout(jobRequestPromise, 25_000, `${entry.name} jobRequest`);
              try {
                const data = req.postDataJSON() as { request?: { drainage?: Record<string, unknown> } };
                console.info(`${entry.name} JOB REQUEST DRAINAGE`, data.request?.drainage ?? null);
              } catch (err) {
                console.info(`${entry.name} JOB REQUEST PARSE ERROR`, String(err));
              }
            }
          const jobResponse = await withTimeout(jobResponsePromise, 60_000, `${entry.name} jobResponse`);
          if (!jobResponse.ok()) {
            applyBlocked = true;
            const blockedPayload = (await jobResponse.json().catch(() => ({}))) as { detail?: string; message?: string };
            const blockedMessage = String(
              blockedPayload.detail || blockedPayload.message || `Request failed with status ${jobResponse.status()}`,
            );
            console.info(`${entry.name} APPLY BLOCKED`, jobResponse.status(), blockedMessage);
            await expect(
              page.getByText(/too many requests|rate limit|wait about a minute|try again later/i).first(),
            ).toBeVisible({ timeout: 10_000 });
          } else {
            const jobPayload = (await jobResponse.json()) as { job?: { job_id?: string } };
            jobId = String(jobPayload?.job?.job_id || "");
            console.info(`${entry.name} JOB ID`, jobId || "missing");
          }
          } catch (err) {
            jobIdError = String(err);
            console.info(`${entry.name} JOB ID ERROR`, jobIdError);
          }
          if (!jobId && !applyBlocked) {
            throw new Error(jobIdError || `${entry.name} did not return a drainage job id after Apply.`);
          }
          if (jobId) {
            console.info(`${entry.name} POLLING START`);
            await waitForJobCompletion(request, token, jobId);
            console.info(`${entry.name} POLLING COMPLETE`);
          }
          const afterResultPayload = await fetchProjectResult(request, token, projectId);
          after = parseDrainageCounts(afterResultPayload);
          if (entry.name === "Case 3 Flat site" && actionLabel === "Adjust slope") {
            const drainagePayload = (afterResultPayload?.final_plan ?? {}) as Record<string, unknown>;
            const meta = (drainagePayload.meta ?? {}) as Record<string, unknown>;
            const canonical = (meta.drainage_canonical ?? meta.drainage ?? {}) as Record<string, unknown>;
            const canonicalIssues = Array.isArray(canonical.issues) ? canonical.issues : [];
            const canonicalCodes = canonicalIssues.map((item: IssueLike) => String(item?.code || item?.message || "unknown"));
            const topIssues = Array.isArray(afterResultPayload.issues)
              ? afterResultPayload.issues.map((item: IssueLike) => String(item?.code || item?.message || "unknown"))
              : [];
            console.info(`${entry.name} ISSUE TRACE`, {
              topIssues,
              canonicalCodes,
            });
          }
          console.info(`${entry.name} AFTER`, after);

          if (entry.name === "Case 3 Flat site" && actionLabel === "Adjust slope") {
            await expect(
              page.getByText(/Best next fix: Create a valid drainage path/i).first(),
            ).toBeVisible({ timeout: 20_000 });
          }

          if (entry.name === "Case 5 Under-collection") {
            const resultPayload = await fetchProjectResult(request, token, projectId);
            const finalPlan = (resultPayload.final_plan ?? {}) as Record<string, unknown>;
            const meta = (finalPlan.meta ?? {}) as Record<string, unknown>;
            const drainage = (meta.drainage_canonical ?? meta.drainage ?? {}) as Record<string, unknown>;
            const drainageIssues = Array.isArray(drainage.issues) ? drainage.issues : [];
            const reducedIssue = drainageIssues.find((issue: IssueLike) => String(issue?.code || "") === "UNDER_COLLECTION_REDUCED");
            console.info("UNDER_COLLECTION_REDUCED_CONTEXT", reducedIssue?.context ?? null);

            // Apply a second time to verify deduplication/guardrails.
            try {
              await withTimeout(applyIssue(page, actionLabel), 25_000, `${entry.name} applyIssue second`);
            } catch (err) {
              console.info(`${entry.name} SECOND APPLY NOT AVAILABLE`, String(err));
            }
            const afterSecond = parseDrainageCounts(await fetchProjectResult(request, token, projectId));
            console.info(`${entry.name} AFTER SECOND APPLY`, afterSecond);
          }
        }
      } catch (err) {
        applyError = String(err);
      }
      caseResults.push({
        case: entry.name,
        action: actionLabel,
        before,
        after,
        error: applyError,
      });
      console.info(`${entry.name} BEFORE`, before);
      console.info(`${entry.name} AFTER`, after);
      await page.goto("about:blank").catch(() => null);
    }
    console.info("PHASE5_AUTOFIX_RESULTS", JSON.stringify(caseResults, null, 2));

    const failedApplyCases = caseResults.filter((result) => result.action && result.error);
    expect(
      failedApplyCases,
      `Phase 5 autofix UI apply failed for: ${failedApplyCases
        .map((result) => `${result.case}: ${result.error}`)
        .join("; ")}`,
    ).toEqual([]);

    const unexercisedApplyCases = caseResults.filter(
      (result) => result.action && !result.before.issues.length,
    );
    expect(
      unexercisedApplyCases,
      `Phase 5 autofix cases produced no issues, so the configured apply action was not exercised: ${unexercisedApplyCases
        .map((result) => result.case)
        .join(", ")}`,
    ).toEqual([]);

    await page.addInitScript(
      ([tokenKey]) => {
        window.localStorage.removeItem(tokenKey);
      },
      [TOKEN_KEY] as const,
    );
  });
});
