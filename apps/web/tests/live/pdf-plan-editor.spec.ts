import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const API_BASE_URL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8002";
const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";
const defaultPdfFixtureCandidates = [
  path.resolve(process.cwd(), "backend/fixtures/plan_pdfs/pool-geometric.pdf"),
  path.resolve(process.cwd(), "../../backend/fixtures/plan_pdfs/pool-geometric.pdf"),
];
const POOL_PDF_PATH =
  process.env.CIVORA_PDF_PLAN_FIXTURE ||
  defaultPdfFixtureCandidates.find((candidate) => fs.existsSync(candidate)) ||
  defaultPdfFixtureCandidates[0];

const runId = Date.now();
const email = process.env.CIVORA_EMAIL || `pdf-plan-${runId}@civora.local`;
const password = process.env.CIVORA_PASSWORD || "pdf-plan-pass-123";

async function loginAndSeedToken(request: APIRequestContext, page: Page) {
  await request
    .post(`${API_BASE_URL.replace(/\/+$/, "")}/api/auth/register`, {
      data: { email, password, name: "PDF Plan Proof" },
    })
    .catch(() => null);

  const loginResponse = await request.post(`${API_BASE_URL.replace(/\/+$/, "")}/api/auth/login`, {
    data: { email, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([tokenKey, restoreKey, value]) => {
      window.localStorage.setItem(tokenKey, value);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, token] as const,
  );
  return token;
}

async function openPdfPanel(page: Page) {
  await page.goto("/?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const workflow = page.getByTestId("plan-pdf-workflow");
  if (await workflow.isVisible().catch(() => false)) {
    return workflow;
  }

  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }

  // Current stage navigation, not removed panel buttons or forced hidden clicks.
  await page.getByTestId("workspace-stage-brief").click();
  await page.getByTestId("workspace-stage-panel").selectOption("data");
  if (!(await workflow.isVisible())) {
    await page.getByText("Detailed source evidence and import tools", { exact: true }).click();
  }

  await expect(workflow).toBeVisible({ timeout: 30_000 });
  return workflow;
}

async function expectNoHorizontalPageOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.innerWidth + 1);
}

async function findPlanPdfProject(request: APIRequestContext, token: string) {
  const headers = { Authorization: `Bearer ${token}` };
  const projectsResponse = await request.get(`${API_BASE_URL.replace(/\/+$/, "")}/api/projects`, { headers });
  expect(projectsResponse.ok()).toBeTruthy();
  const projectsPayload = (await projectsResponse.json()) as { projects?: Array<{ project_id?: string }> };
  const projectIds = (projectsPayload.projects ?? [])
    .map((project) => String(project.project_id || ""))
    .filter(Boolean)
    .reverse();

  for (const projectId of projectIds) {
    const detailResponse = await request.get(`${API_BASE_URL.replace(/\/+$/, "")}/api/projects/${projectId}/result`, {
      headers,
    });
    if (!detailResponse.ok()) {
      continue;
    }
    const detailPayload = (await detailResponse.json()) as {
      project_id?: string;
      latest_result?: { final_plan?: { meta?: Record<string, unknown> } };
    };
    const meta = detailPayload.latest_result?.final_plan?.meta;
    if (detailPayload.project_id && meta?.plan_pdf_analysis_v1) {
      return { project_id: detailPayload.project_id };
    }
  }
  throw new Error("No saved project with plan_pdf_analysis_v1 was found.");
}

async function askChatApi(request: APIRequestContext, token: string, projectId: string, message: string, expected: RegExp) {
  const response = await request.post(`${API_BASE_URL.replace(/\/+$/, "")}/api/chat/decide`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      message,
      context: {
        current_project: { project_id: projectId },
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { assistant_message?: string };
  expect(String(payload.assistant_message || "")).toMatch(expected);
}

test("PDF Plan Editor imports, edits, reviews, exports, and chats truthfully", async ({ page, request }) => {
  test.setTimeout(240_000);
  test.skip(
    !fs.existsSync(POOL_PDF_PATH),
    "PDF plan fixture is unavailable; set CIVORA_PDF_PLAN_FIXTURE or add backend/fixtures/plan_pdfs/pool-geometric.pdf.",
  );

  const token = await loginAndSeedToken(request, page);
  const privateFileRequests: Array<{ url: string; authorization: string }> = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/uploads/")) {
      privateFileRequests.push({ url: request.url(), authorization: request.headers()["authorization"] ?? "" });
    }
  });
  const workflow = await openPdfPanel(page);
  await expectNoHorizontalPageOverflow(page);

  const fileInput = workflow.locator('input[type="file"][accept*=".pdf"]');
  await fileInput.setInputFiles(POOL_PDF_PATH);
  await expect(workflow).toContainText("pool-geometric.pdf", { timeout: 120_000 });
  await expect(workflow).toContainText("imported_pdf_review_required");
  await expect(workflow.locator('iframe[title="Plan PDF source preview"]')).toHaveAttribute("src", /^blob:/);
  expect(privateFileRequests.length).toBeGreaterThan(0);
  for (const fileRequest of privateFileRequests) {
    expect(fileRequest.url).not.toContain("access_token");
    expect(fileRequest.url).not.toContain(token);
    expect(fileRequest.authorization === `Bearer ${token}`).toBe(true);
  }

  for (const label of ["Text", "Labels", "Dimensions", "Title block", "Scale", "Elevations", "Matchlines", "Details"]) {
    await expect(workflow.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(workflow).toContainText("FFE:");
  // PDF encodings may preserve the source's typographic foot mark.
  // Require the same numeric scale, not one specific apostrophe glyph.
  await expect(workflow).toContainText(/1["″]\s*=\s*20['’′]/);
  await expect(workflow).toContainText("MATCHLINE");
  await expect(workflow).toContainText("raster preview blocked");
  await expect(workflow).toContainText("vector geometry extraction blocked");

  const textarea = workflow.locator("textarea").first();
  await expect(textarea).toBeVisible();
  await textarea.fill("PDF PLAN EDITOR REVIEW TEXT");
  await workflow.getByRole("button", { name: "Save" }).click();
  await expect(workflow.getByTestId("plan-pdf-changed-elements")).toContainText("PDF PLAN EDITOR REVIEW TEXT", {
    timeout: 30_000,
  });

  await workflow.getByLabel("X0").fill("120");
  await workflow.getByLabel("Y0").fill("640");
  await workflow.getByRole("button", { name: "Move" }).click();
  await expect(workflow.getByTestId("plan-pdf-changed-elements")).toContainText("moved", { timeout: 30_000 });

  await workflow.getByRole("button", { name: "Accept" }).click();
  await expect(workflow).toContainText("accepted", { timeout: 30_000 });
  await workflow
    .getByTestId("plan-pdf-extracted-elements")
    .getByRole("button", { name: /MAIN FFE: 100\.50/i })
    .click();
  await workflow.getByRole("button", { name: "Reject" }).click();
  await expect(workflow).toContainText("rejected", { timeout: 30_000 });

  const downloadPromise = page.waitForEvent("download");
  await workflow.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("plan_pdf_extraction_report.json");
  const downloadedPath = await download.path();
  expect(downloadedPath).toBeTruthy();
  const report = JSON.parse(fs.readFileSync(downloadedPath!, "utf8")) as {
    construction_release_allowed?: boolean;
    changed_elements?: { elements?: Array<{ text?: string; bbox?: { x0?: number; y0?: number }; review_status?: string }> };
  };
  const savedEdit = report.changed_elements?.elements?.find((item) => item.text === "PDF PLAN EDITOR REVIEW TEXT");
  expect(savedEdit).toMatchObject({ bbox: { x0: 120, y0: 640 }, review_status: "accepted" });
  expect(report.construction_release_allowed).toBe(false);

  const popupPromise = page.waitForEvent("popup");
  await workflow.getByRole("button", { name: "Export PDF" }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState("domcontentloaded").catch(() => null);
  await expect(popup.locator("body")).toContainText("imported source evidence only");
  await popup.close();

  const project = await findPlanPdfProject(request, token);
  const projectId = String(project.project_id || "");
  await askChatApi(request, token, projectId, "what is on this plan?", /review-required plan PDF analysis|Extracted candidates/i);
  await askChatApi(request, token, projectId, "what changed?", /changed PDF-derived element|text edit|move/i);
  await askChatApi(request, token, projectId, "show unreadable text", /Unreadable or blocked PDF text|ocr|raster/i);
  await askChatApi(request, token, projectId, "change pool deck elevation", /exact replacement|imported_pdf_review_required/i);
  await askChatApi(request, token, projectId, "move this PDF label", /explicit target x0\/y0/i);

  const restoredWorkflow = await openPdfPanel(page);
  await expect(restoredWorkflow.getByTestId("plan-pdf-changed-elements")).toContainText("PDF PLAN EDITOR REVIEW TEXT");

  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoHorizontalPageOverflow(page);
});
