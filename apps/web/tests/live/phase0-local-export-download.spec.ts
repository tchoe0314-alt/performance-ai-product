import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const localOrigin = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/;
const local = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && localOrigin.test(api)
  && localOrigin.test(process.env.PLAYWRIGHT_BASE_URL ?? "");

test("signed-in local website exports and downloads preliminary PDF and DXF with owner isolation", async ({ page, request }, testInfo) => {
  test.skip(!local, "Disposable localhost backend only; never mutates hosted customer data.");
  const register = async (suffix: string) => {
    const response = await request.post(`${api}/api/auth/register`, { data: {
      email: `export-${Date.now()}-${suffix}@example.test`, password: "Disposable-phase0-123", name: "Export fixture",
    } });
    expect(response.status()).toBe(200);
    return response.json();
  };
  const owner = await register("owner");
  const stranger = await register("stranger");
  const headers = { Authorization: `Bearer ${owner.token}` };
  const name = `Export fixture ${Date.now()}`;
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name,
    project_input: { input_mode: "user", strict_mode: false, allow_ai_fill_for_blanks: false,
      manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 900, h: 700 } },
    },
    latest_result: { final_plan: { project_name: name, units: "ft",
      actions: [{ task: "rectangle", layer: "BUILDING", origin: [100, 100], width: 80, height: 40 }],
      meta: { canonical_revision: "local-export-revision-1", system_dirty_state: { grading: { state: "stale" } },
        warnings: ["LOCAL_EXPORT_WARNING"], assumptions: ["Synthetic fixture, not a surveyed design."] },
    } },
  } });
  expect(created.status()).toBe(200);
  await page.addInitScript(token => {
    localStorage.setItem("civora-ai-token", token);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, owner.token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}` }).click();

  for (const [button, endpoint, extension] of [
    ["Review PDF", "review-pdf", "pdf"], ["Export DXF", "dxf", "dxf"],
  ]) {
    await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
    await expect(page.getByTestId("deliver-export-source-disclosure")).toContainText("not newer unsaved canvas edits");
    const queued = page.waitForResponse(response => response.url().endsWith(`/api/jobs/export/${endpoint}`) && response.request().method() === "POST");
    await page.getByRole("button", { name: button, exact: true }).first().click();
    const response = await queued;
    expect(response.status()).toBe(200);
    expect(response.request().postDataJSON().export_scope).toBe("review");
    const { job } = await response.json();
    let artifact: { download_path: string; filename: string } | undefined;
    await expect.poll(async () => {
      const status = await request.get(`${api}/api/jobs/${job.job_id}`, { headers });
      const payload = await status.json();
      artifact = payload.job?.artifact_history?.[0] ?? payload.job?.result?.artifact;
      return payload.job?.status;
    }, { timeout: 60_000 }).toBe("completed");
    expect(artifact?.download_path).toBeTruthy();
    const path = artifact!.download_path;
    const url = path.startsWith("http") ? path : `${api}${path}`;
    expect((await request.get(url)).status()).toBe(401);
    expect([403, 404]).toContain((await request.get(url, { headers: { Authorization: `Bearer ${stranger.token}` } })).status());
    await page.getByRole("button", { name: "Export progress and downloads", exact: true }).click();
    const row = page.getByTestId("async-jobs-panel").locator("div.flex.items-center.justify-between").filter({ hasText: artifact!.filename });
    const downloadEvent = page.waitForEvent("download");
    await row.getByRole("button", { name: "Download", exact: true }).first().click();
    const download = await downloadEvent;
    const file = testInfo.outputPath(`downloaded.${extension}`);
    await download.saveAs(file);
    expect(await download.failure()).toBeNull();
    const bytes = await readFile(file);
    if (extension === "pdf") expect(bytes.subarray(0, 4).toString()).toBe("%PDF");
    else {
      expect(bytes.toString()).toContain("PRELIMINARY");
      expect(bytes.toString()).toContain("LOCAL_EXPORT_WARNING");
      expect(bytes.toString()).toContain("local-export-revision-1");
      expect(bytes.toString()).toContain("grading");
    }
    // Reopen the workspace URL explicitly: mobile WebKit can retain the
    // download navigation as its reload target while a file is completing.
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
    await page.getByRole("button", { name: "Export progress and downloads", exact: true }).click();
    await expect(page.getByTestId("async-jobs-panel")).toContainText(artifact!.filename);
  }
});
