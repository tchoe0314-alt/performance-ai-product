import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { openCadPrecisionTools } from "./testUiHelpers";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";
const ACTIVE_PROJECT_KEY = "civora.activeProjectId";
const DEFAULT_APP_URL = "https://civoraai.com/?debugPreview=1&aiRealismProvider=mock";
const DEFAULT_API_URL = "https://api.civoraai.com";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const configuredProjectId = process.env.CIVORA_HOSTED_VISION_PROJECT_ID || "";
const appUrl = process.env.PLAYWRIGHT_BASE_URL || DEFAULT_APP_URL;
const apiBaseUrl = (process.env.PLAYWRIGHT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_URL).replace(/\/+$/, "");

type HostedProject = {
  project_id: string;
  name?: string;
  project_input?: Record<string, unknown>;
};

type CandidateItem = {
  candidate_id?: string;
  status?: string;
  source?: string;
  provider?: string;
  candidate_type?: string;
  source_record?: Record<string, unknown>;
};

async function login(request: APIRequestContext) {
  const response = await request.post(`${apiBaseUrl}/api/auth/login`, {
    data: { email, password },
  });
  expect(response.status(), "hosted login should succeed").toBe(200);
  const payload = (await response.json()) as { token?: string };
  const token = String(payload.token || "");
  expect(token, "hosted login returned a bearer token").toBeTruthy();
  return token;
}

function isVisionCandidate(candidate: CandidateItem) {
  const sourceRecord = candidate.source_record && typeof candidate.source_record === "object" ? candidate.source_record : {};
  const text = [
    candidate.source,
    candidate.provider,
    candidate.candidate_type,
    sourceRecord.source_type,
    sourceRecord.source_name,
    JSON.stringify(sourceRecord.properties || {}),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return /vision|imagery|image_detected_candidate|object detection/.test(text);
}

async function findDenseVisionProject(request: APIRequestContext, token: string) {
  const headers = { Authorization: `Bearer ${token}` };
  const projectsResponse = await request.get(`${apiBaseUrl}/api/projects`, { headers });
  expect(projectsResponse.status(), "hosted project list should load").toBe(200);
  const projectsPayload = (await projectsResponse.json()) as { projects?: HostedProject[] };
  const projects = projectsPayload.projects || [];
  const orderedProjects = configuredProjectId
    ? [
        ...projects.filter((project) => project.project_id === configuredProjectId),
        ...projects.filter((project) => project.project_id !== configuredProjectId),
      ]
    : projects;

  for (const project of orderedProjects.slice(0, 30)) {
    const projectResponse = await request.get(`${apiBaseUrl}/api/projects/${project.project_id}`, { headers });
    if (projectResponse.status() !== 200) continue;
    const projectPayload = (await projectResponse.json()) as { project?: HostedProject };
    const projectDetail = projectPayload.project || project;
    const projectInput = projectDetail.project_input && typeof projectDetail.project_input === "object" ? projectDetail.project_input : {};
    const meta = projectInput.meta && typeof projectInput.meta === "object" ? (projectInput.meta as Record<string, unknown>) : {};
    const siteInputs = meta.site_inputs && typeof meta.site_inputs === "object" ? (meta.site_inputs as Record<string, unknown>) : {};
    if (siteInputs.site_alignment_locked !== true) continue;

    const inboxResponse = await request.get(`${apiBaseUrl}/api/projects/${project.project_id}/candidate-review-inbox`, { headers });
    if (inboxResponse.status() !== 200) continue;
    const inboxPayload = (await inboxResponse.json()) as {
      candidate_review_inbox_v1?: { candidates?: CandidateItem[] };
    };
    const candidates = inboxPayload.candidate_review_inbox_v1?.candidates || [];
    const pendingVisionCandidates = candidates.filter(
      (candidate) => isVisionCandidate(candidate) && String(candidate.status || "pending").toLowerCase() === "pending",
    );
    if (candidates.length >= 13 && pendingVisionCandidates.length) {
      return {
        project: { ...project, ...projectDetail },
        candidateCount: candidates.length,
        pendingVisionCount: pendingVisionCandidates.length,
      };
    }
  }

  throw new Error("No hosted saved project has both a dense candidate inbox and a pending vision candidate.");
}

async function seedAuthAndProject(page: Page, token: string, projectId: string) {
  await page.addInitScript(
    ([tokenKey, restoreKey, activeProjectKey, authToken, activeProjectId]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem(restoreKey, "1");
      window.localStorage.setItem(activeProjectKey, activeProjectId);
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, ACTIVE_PROJECT_KEY, token, projectId] as const,
  );
}

async function openProject(page: Page, project: HostedProject) {
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(() => page.evaluate((activeProjectKey) => window.localStorage.getItem(activeProjectKey), ACTIVE_PROJECT_KEY))
    .toBe(project.project_id);
  await expect(page.getByTestId("project-status-summary")).not.toContainText(/Opening project/i, { timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

async function selectCorrectionRectangle(page: Page) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first().click();
  const rectangles = page.getByTestId("object-manager-row").filter({ hasText: /Command Rectangle/ });
  if ((await rectangles.count()) === 0) {
    const precision = await openCadPrecisionTools(page);
    const input = precision.getByLabel("Draft command input");
    await input.fill("RECTANGLE 20,20 80,80");
    await input.press("Enter");
  }
  const row = page.getByTestId("object-manager-row").filter({ hasText: /Command Rectangle/ }).last();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByTestId("object-manager-select").click();
  await expect(page.getByTestId("draw-selected-object-card")).toContainText(/Command Rectangle/i);
}

async function openCandidateReview(page: Page) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("auto-site-context-summary")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("review-found-context").click();
  const review = page.getByTestId("detected-items-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  return review;
}

test("hosted dense vision correction stays bounded and responsive after save", async ({ page, request }) => {
  test.setTimeout(5 * 60_000);
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted candidate-review stability proof.");

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (requestInfo) => {
    failedRequests.push(`${requestInfo.method()} ${requestInfo.url()} ${requestInfo.failure()?.errorText || "request failed"}`);
  });

  const token = await login(request);
  const denseProject = await findDenseVisionProject(request, token);
  await seedAuthAndProject(page, token, denseProject.project.project_id);
  await openProject(page, denseProject.project);
  await selectCorrectionRectangle(page);

  const review = await openCandidateReview(page);
  await expect(review.getByTestId("detected-item-candidate")).toHaveCount(12);
  await expect(review.getByTestId("detected-items-page-summary")).toContainText(/Showing 1-12 of \d+/);
  await review.getByRole("tab", { name: /Vision \d+/ }).click();
  await expect(review.getByTestId("detected-item-candidate")).toHaveCount(Math.min(12, denseProject.pendingVisionCount), { timeout: 15_000 });

  const pendingCard = review
    .getByTestId("detected-item-candidate")
    .filter({ hasText: /pending/i })
    .filter({ has: page.getByTestId("vision-use-selected-outline") })
    .first();
  await expect(pendingCard).toBeVisible();
  const typeSelect = pendingCard.getByLabel(/Correct detected type for/i);
  const originalType = await typeSelect.inputValue();
  await typeSelect.selectOption(originalType === "parking_area" ? "road_or_drive" : "parking_area");

  const useOutline = pendingCard.getByTestId("vision-use-selected-outline");
  await expect(useOutline).toBeEnabled();
  await useOutline.click();
  await expect(pendingCard).toHaveAttribute("aria-busy", "true");
  await expect(pendingCard).toContainText(/accepted/i, { timeout: 30_000 });

  await page.waitForTimeout(5_000);
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  await expect(review.getByTestId("detected-item-candidate")).toHaveCount(Math.min(12, denseProject.pendingVisionCount));
  await expect(page).toHaveTitle(/Civora/i);
  await expect(page.locator("body")).not.toContainText(/Aw, Snap|page crashed/i);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((line) => !/favicon/i.test(line))).toEqual([]);
  expect(
    failedRequests.filter((line) => !/favicon|api\.mapbox\.com\/.*net::ERR_ABORTED/i.test(line)),
  ).toEqual([]);
});
