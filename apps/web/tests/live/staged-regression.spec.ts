import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const prompt = process.env.CIVORA_PROMPT || "";
const TOKEN_KEY = "civora-ai-token";
const API_BASE_URL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://api.civoraai.com";
const APP_BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  "https://civoraai.com";
const FALLBACK_BASE_URL =
  process.env.PLAYWRIGHT_FALLBACK_BASE_URL ||
  "https://civoraai.com";

async function ensureAppUrl(page: Page) {
  const currentUrl = page.url();
  if (currentUrl.includes("vercel.com/")) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  const vercelLogin = page.getByRole("heading", { name: "Log in to Vercel" });
  const emailLogin = page.getByRole("button", { name: "Continue with Email" });
  const deploymentProtection = page.getByText("Deployment Protection", { exact: false });
  const authRequired = page.getByText("Authentication Required", { exact: false });
  if (await vercelLogin.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await emailLogin.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await deploymentProtection.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await authRequired.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  return false;
}

type JobSummary = {
  job_id: string;
  status?: string;
  stage?: string;
  stage_detail?: string;
  project_id?: string | null;
  created_at?: number;
  updated_at?: number;
};

type JobDetailResponse = {
  success?: boolean;
  job?: {
    job_id: string;
    status?: string;
    stage?: string;
    stage_detail?: string;
    project_id?: string | null;
    payload?: Record<string, unknown>;
  };
};

type ProjectResultResponse = {
  success?: boolean;
  project_id?: string;
  latest_result?: PlanResult;
};

type PlanResult = {
  final_plan?: {
    actions?: unknown[];
    meta?: {
      runtime_phase_checkpoint?: {
        stage_name?: string;
      };
    };
  };
};

type PreviewResponse = {
  success?: boolean;
  preview_image_data_url?: string;
};

async function ensureArtifactDir(): Promise<string> {
  const dir = path.resolve(process.cwd(), "playwright-artifacts", "staged-regression");
  await fs.mkdir(dir, { recursive: true });
  return dir;
}

function decodeDataUrl(dataUrl: string): Buffer {
  const match = /^data:image\/png;base64,(.+)$/i.exec(dataUrl);
  if (!match) {
    throw new Error("Preview response did not return a PNG data URL.");
  }
  return Buffer.from(match[1], "base64");
}

async function apiJson<T>(
  request: APIRequestContext,
  token: string,
  pathName: string,
  options?: { method?: "GET" | "POST"; data?: unknown },
): Promise<T> {
  const method = options?.method || "GET";
  const requestUrl = `${API_BASE_URL.replace(/\/+$/, "")}${pathName}`;
  let lastStatus = 0;
  let lastBody = "";

  for (let attempt = 0; attempt < 4; attempt += 1) {
    let response;
    try {
      response =
        method === "POST"
          ? await request.post(requestUrl, {
              data: options?.data,
              headers: {
                Authorization: `Bearer ${token}`,
              },
            })
          : await request.get(requestUrl, {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            });
    } catch (error) {
      lastBody = String((error as Error)?.message || error || "");
      await new Promise((resolve) => setTimeout(resolve, 1000 * (attempt + 1)));
      continue;
    }

    if (response.ok()) {
      return (await response.json()) as T;
    }

    lastStatus = response.status();
    lastBody = await response.text().catch(() => "");
    await new Promise((resolve) => setTimeout(resolve, 1000 * (attempt + 1)));
  }

  expect(
    false,
    `${pathName} should respond OK (last status: ${lastStatus}, body: ${lastBody.slice(0, 240)})`,
  ).toBeTruthy();
  throw new Error(`${pathName} did not respond OK`);
}

async function waitForNewJob(
  page: Page,
  request: APIRequestContext,
  token: string,
  knownJobIds: Set<string>,
): Promise<JobSummary> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const payload = await apiJson<{ jobs: JobSummary[] }>(request, token, "/api/jobs");
    const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
    const newest = jobs
      .filter((job) => !knownJobIds.has(job.job_id))
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))[0];
    if (newest?.job_id && newest.project_id) {
      return newest;
    }
    const bodyText = (await page.locator("body").innerText().catch(() => "")) || "";
    const jobMatch = bodyText.match(/job_[a-z0-9]+/i);
    if (jobMatch?.[0] && !knownJobIds.has(jobMatch[0])) {
      const detailPayload = await apiJson<JobDetailResponse>(request, token, `/api/jobs/${jobMatch[0]}`);
      const job = detailPayload.job;
      if (job?.job_id && job.project_id) {
        return {
          job_id: job.job_id,
          status: job.status,
          stage: job.stage,
          stage_detail: job.stage_detail,
          project_id: job.project_id,
        };
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error("Timed out waiting for a newly created staged job.");
}

async function waitForApprovalCheckpoint(
  request: APIRequestContext,
  token: string,
  jobId: string,
  projectId: string,
  expectedStageName: string,
) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const jobPayload = await apiJson<JobDetailResponse>(request, token, `/api/jobs/${jobId}`);
    const resultPayload = await apiJson<ProjectResultResponse>(
      request,
      token,
      `/api/projects/${projectId}/result`,
    );

    const job = (jobPayload.job ?? {}) as NonNullable<JobDetailResponse["job"]>;
    const latestResult = resultPayload.latest_result ?? {};
    const finalPlan = latestResult.final_plan ?? {};
    const actions = Array.isArray(finalPlan.actions) ? finalPlan.actions : [];
    const checkpoint = (finalPlan.meta || {}).runtime_phase_checkpoint || {};

    const approvalReached =
      String(job.status || "").toLowerCase() === "awaiting_approval" &&
      String(checkpoint.stage_name || "") === expectedStageName &&
      actions.length > 0;

    if (approvalReached) {
      return {
        job,
        latestResult,
        checkpoint,
        actionCount: actions.length,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`Timed out waiting for ${expectedStageName} approval checkpoint.`);
}

async function savePreviewArtifact(
  request: APIRequestContext,
  token: string,
  artifactDir: string,
  projectId: string,
  result: PlanResult,
  phaseName: string,
) {
  const previewPayload = await apiJson<PreviewResponse>(request, token, "/api/preview", {
    method: "POST",
    data: {
      project_id: projectId,
      result,
      filename_stem: "staged-regression",
    },
  });
  expect(previewPayload.preview_image_data_url).toBeTruthy();
  const pngBytes = decodeDataUrl(String(previewPayload.preview_image_data_url));
  const pngPath = path.join(artifactDir, `${phaseName}.png`);
  await fs.writeFile(pngPath, pngBytes);
  return pngPath;
}

async function waitForComposer(page: Page) {
  const composer = page.getByPlaceholder(
    "Message Civora AI with what you want to create or change...",
  );

  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (await ensureAppUrl(page)) {
      continue;
    }
    await page.waitForLoadState("networkidle").catch(() => null);
    const chatButton = page.getByRole("button", { name: "Chat" });
    if (!(await composer.isVisible().catch(() => false))) {
      if (await chatButton.isVisible().catch(() => false)) {
        await chatButton.click();
        await page.waitForTimeout(500);
      }
    }
    if (await composer.isVisible().catch(() => false)) {
      return composer;
    }

    if (await ensureAppUrl(page)) {
      continue;
    }

    const loadError = page.getByText("This page couldn’t load");
    if (await loadError.isVisible().catch(() => false)) {
      await page.goto(APP_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    } else {
      await page.reload({ waitUntil: "domcontentloaded" });
    }
  }

  await expect(composer).toBeVisible({ timeout: 15_000 });
  return composer;
}

async function answerClarificationIfNeeded(page: Page) {
  const clarificationPrompt = page.getByText(
    "Before I move forward, I still need the site type or land use",
    { exact: false },
  );
  try {
    await clarificationPrompt.waitFor({ state: "visible", timeout: 30_000 });
  } catch {
    return;
  }
  const clarificationComposer = await waitForComposer(page);
  await clarificationComposer.fill("Mixed-use");
  await expect(clarificationComposer).toHaveValue("Mixed-use");
  await page.getByRole("button", { name: "Send" }).click();
}

async function ensureNewProject(page: Page) {
  const projectsButton = page.getByRole("button", { name: "Projects" });
  if (await projectsButton.isVisible().catch(() => false)) {
    await projectsButton.click();
  }
  const newProjectButton = page.getByRole("button", { name: /New Project/i });
  if (await newProjectButton.isVisible().catch(() => false)) {
    await newProjectButton.click();
    await page.waitForLoadState("networkidle");
  }
}

test("staged regression flow", async ({ page, request, baseURL }) => {
  test.setTimeout(8 * 60_000);
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");
  test.skip(!prompt.trim(), "CIVORA_PROMPT is required.");

  const artifactDir = await ensureArtifactDir();

  const loginResponse = await request.post(`${API_BASE_URL.replace(/\/+$/, "")}/api/auth/login`, {
    data: { email, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload.token || "");
  expect(token).toBeTruthy();

  const existingJobs = await apiJson<{ jobs: JobSummary[] }>(request, token, "/api/jobs");
  const knownJobIds = new Set((existingJobs.jobs || []).map((job) => job.job_id));

  await page.addInitScript(
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
    },
    [TOKEN_KEY, token] as const,
  );

  await page.goto(baseURL!, { waitUntil: "domcontentloaded" });
  await waitForComposer(page);

  await ensureNewProject(page);

  const composer = await waitForComposer(page);
  const enrichedPrompt = /site type|land use|mixed-use|residential|commercial/i.test(prompt)
    ? prompt
    : `${prompt}\nSite type: mixed-use.`;
  await composer.fill(enrichedPrompt);
  await page.getByRole("button", { name: "Send" }).click();

  await answerClarificationIfNeeded(page);

  const newJob = await waitForNewJob(page, request, token, knownJobIds);
  const jobId = String(newJob.job_id);
  const projectId = String(newJob.project_id);

  const layoutCheckpoint = await waitForApprovalCheckpoint(
    request,
    token,
    jobId,
    projectId,
    "layout",
  );

  await expect(page.getByRole("button", { name: /Approve & Continue/i })).toBeVisible({
    timeout: 60_000,
  });
  await page.screenshot({
    path: path.join(artifactDir, "layout-browser.png"),
    fullPage: true,
  });
  await savePreviewArtifact(
    request,
    token,
    artifactDir,
    projectId,
    layoutCheckpoint.latestResult,
    "layout-preview",
  );

  const approveButton = page.getByRole("button", { name: /Approve & Continue/i });
  await approveButton.scrollIntoViewIfNeeded();
  await approveButton.click({ force: true });

  const gradingCheckpoint = await waitForApprovalCheckpoint(
    request,
    token,
    jobId,
    projectId,
    "grading",
  );

  await expect(page.getByRole("button", { name: /Approve & Continue/i })).toBeVisible({
    timeout: 60_000,
  });
  await page.screenshot({
    path: path.join(artifactDir, "grading-browser.png"),
    fullPage: true,
  });
  await savePreviewArtifact(
    request,
    token,
    artifactDir,
    projectId,
    gradingCheckpoint.latestResult,
    "grading-preview",
  );

  expect(gradingCheckpoint.actionCount).toBeGreaterThan(0);
  expect(layoutCheckpoint.actionCount).toBeGreaterThan(0);
});
