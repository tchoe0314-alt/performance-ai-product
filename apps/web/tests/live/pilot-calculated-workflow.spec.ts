import { expect, test } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

for (const { assisted, target } of [
  { assisted: false, target: "parking" },
  { assisted: true, target: "parking" },
  { assisted: true, target: "full" },
]) test(`website commercial ${target} ${assisted ? "assisted run saves and reopens" : "manual failure stays blocked"}`, async ({ page, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only; never runs hosted generation.");
  test.setTimeout(180_000);
  const name = `Calculated pilot ${randomUUID()}`;
  const small = target === "full";
  const registration = await request.post(`${api}/api/auth/register`, { data: { email: `calc-${randomUUID()}@example.test`, name: "Synthetic calculation test", password: "Disposable-123" } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json(), headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: withCanonicalCanvasSnapshot({
    input_mode: assisted ? "assisted" : "user", allow_ai_fill_for_blanks: assisted,
    manual_fields: { project_name: name, units: "ft", project_type: "commercial_pad", building_width: small ? 60 : 160, building_depth: small ? 40 : 90,
      terrain: "2% slope west to east", setback: 20, lot: { x: 0, y: 0, w: small ? 240 : 900, h: small ? 180 : 700 },
      site_plan: { building_program_sf: small ? 2400 : 14400, building_count: 1, building_type: "office", parking_count: small ? 12 : 60 },
      site_objects: [
        { id: "parcel", label: "Synthetic parcel", type: "site", x: 0, y: 0, w: small ? 240 : 900, d: small ? 180 : 700, placed: true },
        { id: "office", label: "Synthetic office", type: "office_building", x: small ? 80 : 300, y: small ? 40 : 120, w: small ? 60 : 160, d: small ? 40 : 90, placed: true },
        { id: "parking", label: "Synthetic parking", type: "parking", x: small ? 60 : 240, y: small ? 115 : 360, w: small ? 120 : 330, d: small ? 50 : 150, placed: true, meta: { requested_stalls: small ? 12 : 60 } },
      ] }, meta: { site_inputs: { site_alignment_locked: true }, system_dirty_state: { parking: "stale" } },
  }) } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await page.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  page.on("dialog", dialog => dialog.accept());
  await openWorkspaceTool(page, "Generate");
  const execution = page.waitForResponse(response => response.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(response.url()), { timeout: 20_000 });
  await page.getByTestId(target === "full" ? "generate-main-action" : "generate-parking").click();
  const response = await execution;
  expect(response.status()).toBe(200);
  const payload = await response.json();
  if (payload.job) {
    await expect.poll(async () => {
      const job = (await (await request.get(`${api}/api/jobs/${payload.job.job_id}`, { headers })).json()).job;
      if (job.status === "awaiting_approval") {
        // Approve synthetic stage checkpoints through the visible website,
        // exactly as the pilot user must, not through a hidden API bypass.
        const proceed = page.getByTestId("generate-main-action");
        if ((await proceed.textContent())?.includes("Continue after")) await proceed.click();
      }
      return job.status;
    }, { timeout: 120_000, intervals: [1000] }).toBe("completed");
  } else if (!assisted) {
    expect(payload.success).toBe(false);
    expect(payload.missing_requirements.missing_fields.length).toBeGreaterThan(0);
    await expect(page.getByTestId("project-status-summary")).toContainText("Calculation needs attention");
    await expect(page.getByTestId("generate-parking")).not.toContainText("Current");
    const unchanged = await (await request.get(`${api}/api/projects/${project.project_id}/result`, { headers })).json();
    expect(unchanged.latest_result ?? {}).toEqual({});
    return;
  } else expect(payload.success, payload.message).toBe(true);
  const saved = async () => {
    const record = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    const result = await (await request.get(`${api}/api/projects/${project.project_id}/result`, { headers })).json();
    return { ...record, latest_result: result.latest_result, result_freshness_v1: result.result_freshness_v1 };
  };
  await expect.poll(async () => Boolean((await saved()).latest_result?.final_plan), { timeout: 30_000 }).toBe(true);
  const checkpoint = await saved();
  expect(checkpoint.result_freshness_v1.status).toBe("current");
  expect(checkpoint.latest_result.final_plan.meta.quantities).toBeTruthy();
  const calculationId = checkpoint.latest_result.metadata.calculation_save_v1.calculation_id;
  const history = async () => (await (await request.get(`${api}/api/projects/${project.project_id}/calculations/${calculationId}`, { headers })).json()).calculation;
  const fingerprint = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
  const storedCalculation = fingerprint(await history());
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByText("Saved results are out of date. Recalculate for this layout.", { exact: true })).toHaveCount(0);
  expect(fingerprint(await history())).toBe(storedCalculation);
  expect((await saved()).latest_result.metadata.calculation_save_v1.calculation_id).toBe(calculationId);
  await openWorkspaceTool(page, "Generate");
  if (target === "parking") {
    await expect(page.getByTestId("generate-parking")).toContainText("Current");
    await expect(page.getByTestId("generate-grading")).not.toContainText("Current");
  } else {
    // Exercise calculated exports from a real engine result, not an injected
    // fixture. Preliminary release must retain its engineering limitations.
    await openWorkspaceTool(page, "Deliver");
    const stages = checkpoint.latest_result.final_plan.meta.stage_completeness?.statuses ?? {};
    const incomplete = Object.values(stages).some(value => value === "failed" || value === "partial");
    if (incomplete) {
      // A completed job/current input binding is not proof that every engine
      // produced a usable design. Keep this real unsupported-output probe.
      await expect(page.getByTestId("deliver-export-blocker")).toContainText("rerun", { timeout: 30_000 });
      expect(checkpoint.latest_result.final_plan.meta.cost_estimate?.totals?.production_usable).toBe(false);
      return;
    }
    await expect(page.getByTestId("deliver-export-blocker")).toHaveCount(0, { timeout: 30_000 });
    const exportResponse = page.waitForResponse(value => value.url().endsWith("/api/jobs/export/review-pdf") && value.request().method() === "POST", { timeout: 20_000 });
    await page.getByRole("button", { name: "Review PDF", exact: true }).first().click();
    const exported = await exportResponse;
    expect(exported.status()).toBe(200);
    const { job } = await exported.json();
    await expect.poll(async () => (await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json()).job.status, { timeout: 60_000 }).toBe("completed");
  }
});
