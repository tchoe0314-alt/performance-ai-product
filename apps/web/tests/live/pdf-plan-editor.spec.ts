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
const POOL_PDF_PATH =
  process.env.CIVORA_PDF_PLAN_FIXTURE ||
  path.resolve(process.cwd(), "../../backend/fixtures/plan_pdfs/pool-geometric.pdf");

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
  await page.waitForLoadState("networkidle").catch(() => null);

  const workflow = page.getByTestId("plan-pdf-workflow");
  if (await workflow.isVisible().catch(() => false)) {
    return workflow;
  }

  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }

  const directPanels = [
    page.getByRole("button", { name: /^Deliver$/ }).first(),
    page.getByRole("button", { name: /^Setup$/ }).first(),
    page.getByRole("button", { name: /^Import$/ }).first(),
  ];
  for (const panelButton of directPanels) {
    if (await panelButton.isVisible().catch(() => false)) {
      await panelButton.click();
      await page.waitForTimeout(150);
      for (const sectionName of ["Survey / Terrain / Sources", "Auto Site Context Results"]) {
        const section = page.getByText(sectionName, { exact: true }).first();
        if (await section.isVisible().catch(() => false)) {
          await section.click();
          await page.waitForTimeout(150);
        }
      }
      for (const panelName of [/Files \/ PDFs/i, /Online Sources/i, /Plan PDF/i]) {
        const nestedButton = page.getByRole("button", { name: panelName }).first();
        if (await nestedButton.isVisible().catch(() => false)) {
          await nestedButton.click();
          await page.waitForTimeout(150);
          const details = page.getByText("Detailed source evidence and import tools", { exact: true }).first();
          if (await details.isVisible().catch(() => false)) {
            await details.click();
          }
          if (await workflow.isVisible({ timeout: 5_000 }).catch(() => false)) {
            return workflow;
          }
        }
      }
    }
  }

  for (const name of [/Survey \/ Import/i, /Files \/ PDFs/i, /Files/i, /Plan PDF visual editor/i, /^Plan PDF$/i, /^Data$/i, /Data/i]) {
    const button = page.getByRole("button", { name }).first();
    if ((await button.count().catch(() => 0)) > 0) {
      await button.scrollIntoViewIfNeeded().catch(() => null);
      await button.click({ force: true }).catch(() => null);
      const planPdfButton = page.getByRole("button", { name: /Plan PDF visual editor|^Plan PDF$/i }).first();
      if ((await planPdfButton.count().catch(() => 0)) > 0) {
        await planPdfButton.scrollIntoViewIfNeeded().catch(() => null);
        await planPdfButton.click({ force: true }).catch(() => null);
      }
      const details = page.getByText("Detailed source evidence and import tools", { exact: true }).first();
      if ((await details.count().catch(() => 0)) > 0) {
        await details.scrollIntoViewIfNeeded().catch(() => null);
        await details.click({ force: true }).catch(() => null);
      }
      if (await workflow.isVisible({ timeout: 5_000 }).catch(() => false)) {
        return workflow;
      }
    }
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
  const workflow = await openPdfPanel(page);
  await expectNoHorizontalPageOverflow(page);

  const fileInput = workflow.locator('input[type="file"][accept*=".pdf"]');
  await fileInput.setInputFiles(POOL_PDF_PATH);
  await expect(workflow).toContainText("pool-geometric.pdf", { timeout: 120_000 });
  await expect(workflow).toContainText("imported_pdf_review_required");

  for (const label of ["Text", "Labels", "Dimensions", "Title block", "Scale", "Elevations", "Matchlines", "Details"]) {
    await expect(workflow.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(workflow).toContainText("FFE:");
  await expect(workflow).toContainText("1\" = 20'");
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

  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoHorizontalPageOverflow(page);
});
