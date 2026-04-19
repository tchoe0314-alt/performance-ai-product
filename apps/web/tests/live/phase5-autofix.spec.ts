import { expect, test } from "@playwright/test";

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

async function loginAndSeedToken(request: any, page: any) {
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

  await page.addInitScript(
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
    },
    [TOKEN_KEY, token] as const,
  );
  return token;
}

async function orchestrateScenario(request: any, token: string, payload: Record<string, unknown>) {
  const response = await request.post(`${API_BASE_URL}/api/orchestrate`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
    timeout: 180_000,
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as Record<string, unknown>;
}

async function saveProject(
  request: any,
  token: string,
  name: string,
  project_input: Record<string, unknown>,
  latest_result: Record<string, unknown>,
) {
  const response = await request.post(`${API_BASE_URL}/api/projects`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name,
      description: "Autofix validation",
      project_input,
      latest_result,
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { project_id?: string };
}

async function fetchProjectResult(request: any, token: string, projectId: string) {
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
  const issues = Array.isArray(result.issues)
    ? result.issues.map((item: any) => String(item?.code || item?.message || "unknown"))
    : [];
  return { basins, inlets, runs, issues };
}

async function openProject(page: any, name: string) {
  const projectsButton = page.getByRole("button", { name: "Projects" });
  await projectsButton.click();
  const projectButton = page.getByRole("button", { name: new RegExp(name, "i") });
  await projectButton.click();
  await page.waitForLoadState("networkidle");
}

async function applyIssue(page: any, actionLabel: string) {
  const applyButton = page.getByRole("button", { name: new RegExp(actionLabel, "i") }).first();
  await expect(applyButton).toBeVisible({ timeout: 20_000 });
  await applyButton.click();
  await page.waitForTimeout(5_000);
}

test.describe("Phase 5 drainage autofix matrix", () => {
  test("Run autofix apply actions matrix", async ({ page, request }) => {
    test.setTimeout(300_000);
    const token = await loginAndSeedToken(request, page);
    await page.goto(APP_BASE_URL, { waitUntil: "domcontentloaded" });

    const basePayload = {
      project_id: null,
      full_design_mode: false,
      input_mode: "user",
      strict_mode: false,
      prompt_text: null,
      meta: {
        requested_system: "drainage",
      },
      manual_fields: {
        units: "ft",
        lot: { x: 0, y: 0, w: 600, h: 600 },
        disciplines: ["drainage", "grading"],
        buildings: [
          {
            id: "b1",
            name: "Building 1",
            x: 200,
            y: 200,
            w: 80,
            d: 60,
          },
        ],
        grading: { min_slope_pct: 0.5 },
        drainage: { min_pipe_slope_pct: 0.5 },
      },
      allow_ai_fill_for_blanks: false,
    };

    const cases: Array<{
      name: string;
      payload: Record<string, unknown>;
      action: string;
    }> = [
      {
        name: "Case 1 Basin uphill",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            ponds: [{ id: "pond1", name: "Pond", x: 10, y: 10, w: 40, d: 30 }],
          },
        },
        action: "Add basin",
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
      },
      {
        name: "Case 4 Orphan inlet",
        payload: {
          ...basePayload,
          manual_fields: {
            ...(basePayload.manual_fields as Record<string, unknown>),
            drainage_structures: [{ id: "inlet1", x: 100, y: 100 }],
            ponds: [{ id: "pond2", name: "Pond", x: 500, y: 500, w: 40, d: 30 }],
          },
        },
        action: "Connect inlet",
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
    ];

    for (const entry of cases) {
      const result = await orchestrateScenario(request, token, entry.payload);
      const saved = await saveProject(request, token, entry.name, entry.payload, result);
      const projectId = String(saved.project_id || "");
      expect(projectId).toBeTruthy();

      const before = parseDrainageCounts(await fetchProjectResult(request, token, projectId));
      await openProject(page, entry.name);

      await applyIssue(page, entry.action);

      const after = parseDrainageCounts(await fetchProjectResult(request, token, projectId));
      console.info(`${entry.name} BEFORE`, before);
      console.info(`${entry.name} AFTER`, after);
    }

    const controlResult = await orchestrateScenario(request, token, basePayload);
    const controlSaved = await saveProject(request, token, "Case 6 Control", basePayload, controlResult);
    const controlId = String(controlSaved.project_id || "");
    const controlBefore = parseDrainageCounts(await fetchProjectResult(request, token, controlId));
    await openProject(page, "Case 6 Control");
    const controlAfter = parseDrainageCounts(await fetchProjectResult(request, token, controlId));
    console.info("Case 6 Control BEFORE", controlBefore);
    console.info("Case 6 Control AFTER", controlAfter);

    await page.addInitScript(
      ([tokenKey]) => {
        window.localStorage.removeItem(tokenKey);
      },
      [TOKEN_KEY] as const,
    );
  });
});
