import { expect, test } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

for (const { assisted, target } of [
  { assisted: false, target: "parking" },
  { assisted: true, target: "parking" },
  { assisted: true, target: "full" },
]) test(`website commercial ${target} ${assisted ? "assisted run saves and reopens" : "manual failure stays blocked"}`, async ({ page, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only; never runs hosted generation.");
  test.setTimeout(600_000);
  const name = `Calculated pilot ${randomUUID()}`;
  // The full multidisciplinary fixture intentionally leaves enough separation
  // for generated drainage and utility review geometry. The compact parking
  // fixture remains useful for the narrower parking-only probes.
  const small = target !== "full";
  const registration = await request.post(`${api}/api/auth/register`, { data: { email: `calc-${randomUUID()}@example.test`, name: "Synthetic calculation test", password: "Disposable-123" } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json(), headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: withCanonicalCanvasSnapshot({
    input_mode: assisted ? "assisted" : "user", allow_ai_fill_for_blanks: assisted,
    manual_fields: { project_name: name, units: "ft", project_type: "commercial_pad", building_width: small ? 60 : 160, building_depth: small ? 40 : 90,
      terrain: "2% slope west to east", setback: 20, lot: { x: 0, y: 0, w: small ? 240 : 900, h: small ? 180 : 700 },
      site_plan: { building_program_sf: small ? 2400 : 14400, building_count: 1, building_type: "office", parking_count: small ? 12 : 60 },
      pipe_network: target === "full" ? [{
        id: "SYN-STORM-PIPE-1", label: "Synthetic storm trunk", utility_type: "storm",
        points: [[600, 420], [760, 500]], path: [[600, 420], [760, 500]],
        canonical_id: "SYN-STORM-PIPE-1", length_ft: 178.885, diameter_in: 18, slope_ft_ft: 0.01,
        source: "manual_drawn", review_required: true, construction_release_allowed: false,
      }] : [],
      site_objects: [
        { id: "parcel", label: "Synthetic parcel", type: "site", x: 0, y: 0, w: small ? 240 : 900, d: small ? 180 : 700, placed: true },
        { id: "office", label: "Synthetic office", type: "office_building", x: small ? 80 : 300, y: small ? 40 : 120, w: small ? 60 : 160, d: small ? 40 : 90, placed: true },
        { id: "parking", label: "Synthetic parking", type: "parking", x: small ? 60 : 240, y: small ? 115 : 360, w: small ? 120 : 330, d: small ? 50 : 150, placed: true, meta: { requested_stalls: small ? 12 : 60 } },
      ] }, meta: {
        site_inputs: { site_alignment_locked: true },
        system_dirty_state: target === "parking" ? { parking: "stale" } : {},
      },
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
  let checkpoint = await saved();
  const initialBuildingArea = checkpoint.latest_result.final_plan.meta.quantities?.totals?.building_area_sf;
  if (target === "full") expect(initialBuildingArea).toBe(14_400);
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
    // Make a real canonical building edit, prove the prior calculation becomes
    // stale, then run the same visible approval workflow again.
    await openWorkspaceTool(page, "Draw");
    const objectList = page.getByTestId("object-manager-panel");
    if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Synthetic office" }).first();
    await officeRow.getByTestId("object-manager-select").click();
    await officeRow.getByTestId("object-manager-inspect").click();
    const widthInput = page.getByTestId("selected-object-width-input");
    const originalWidth = Number(await widthInput.inputValue());
    const originalDepth = Number(await page.getByTestId("selected-object-depth-input").inputValue());
    const revisedWidth = originalWidth + 10;
    await widthInput.fill(String(revisedWidth));
    await widthInput.blur();
    await expect.poll(async () => (await saved()).result_freshness_v1.status, { timeout: 30_000 }).not.toBe("current");

    await openWorkspaceTool(page, "Generate");
    const recalculation = page.waitForResponse(value => value.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(value.url()), { timeout: 20_000 });
    await page.getByTestId("generate-main-action").click();
    const recalculationPayload = await (await recalculation).json();
    expect(recalculationPayload.job).toBeTruthy();
    await expect.poll(async () => {
      const job = (await (await request.get(`${api}/api/jobs/${recalculationPayload.job.job_id}`, { headers })).json()).job;
      if (job.status === "awaiting_approval") {
        const proceed = page.getByTestId("generate-main-action");
        if ((await proceed.textContent())?.includes("Continue after")) await proceed.click();
      }
      return job.status;
    }, { timeout: 120_000, intervals: [1000] }).toBe("completed");
    await expect.poll(async () => (await saved()).result_freshness_v1.status, { timeout: 30_000 }).toBe("current");
    const revisedCheckpoint = await saved();
    expect(revisedCheckpoint.latest_result.metadata.calculation_save_v1.calculation_id).not.toBe(calculationId);
    const revisedOffice = revisedCheckpoint.latest_result.final_plan.actions.find((action: { canonical_source_id?: string; layer?: string }) => action.canonical_source_id === "office" && action.layer === "BUILDING");
    expect(revisedOffice?.width).toBe(revisedWidth);
    expect(revisedOffice?.height).toBe(originalDepth);
    expect(revisedOffice.width * revisedOffice.height - originalWidth * originalDepth).toBe(900);
    const revisedBuildingArea = revisedCheckpoint.latest_result.final_plan.meta.quantities?.totals?.building_area_sf;
    expect(revisedBuildingArea).toBe(15_300);
    expect(revisedBuildingArea - initialBuildingArea).toBe(900);
    checkpoint = revisedCheckpoint;
    const branchDialog = page.getByTestId("project-tab-branch-dialog");
    if (await branchDialog.isVisible().catch(() => false)) {
      // Preserve the generated backend result and leave the intentional
      // concurrent-edit safeguard in place; this fixture does not overwrite.
      await branchDialog.getByRole("button", { name: "Keep editing", exact: true }).click();
    }
    await page.reload();
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    await expect(page.getByText("Saved results are out of date. Recalculate for this layout.", { exact: true })).toHaveCount(0);

    // Exercise calculated exports from a real engine result, not an injected
    // fixture. Preliminary release must retain its engineering limitations.
    await openWorkspaceTool(page, "Deliver");
    const stages = checkpoint.latest_result.final_plan.meta.stage_completeness?.statuses ?? {};
    const incomplete = Object.values(stages).some(value => value === "failed" || value === "partial");
    if (incomplete) {
      // Review exports may truthfully package incomplete work, but they must
      // never become construction-ready merely because the snapshot is current.
      expect(checkpoint.latest_result.final_plan.meta.cost_estimate?.totals?.production_usable ?? false).toBe(false);
    }
    await expect(page.getByTestId("deliver-export-blocker")).toHaveCount(0, { timeout: 30_000 });
    const downloadCalculatedArtifact = async (label: "Review PDF" | "Export DXF", endpoint: string) => {
      await openWorkspaceTool(page, "Deliver");
      const action = page.getByTestId("deliver-export-actions").getByRole("button", { name: label, exact: true });
      await expect(action).toBeEnabled({ timeout: 30_000 });
      const queued = page.waitForResponse(value => value.url().endsWith(`/api/jobs/export/${endpoint}`) && value.request().method() === "POST", { timeout: 20_000 });
      await action.click();
      const response = await queued;
      expect(response.status()).toBe(200);
      const { job } = await response.json();
      let artifact: { download_path: string } | undefined;
      await expect.poll(async () => {
        const detail = (await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json()).job;
        artifact = detail.artifact_history?.[0] ?? detail.result?.artifact;
        return detail.status;
      }, { timeout: 60_000 }).toBe("completed");
      expect(artifact?.download_path).toBeTruthy();
      const artifactResponse = await request.get(`${api}${artifact!.download_path}`, { headers });
      expect(artifactResponse.status()).toBe(200);
      // Let the workspace's job poller observe completion before requesting a
      // second export; the API receipt can lead the rendered job state briefly.
      await page.waitForTimeout(2_500);
      return artifactResponse.body();
    };
    const pdf = await downloadCalculatedArtifact("Review PDF", "review-pdf");
    expect(pdf.subarray(0, 4).toString()).toBe("%PDF");
    const dxf = (await downloadCalculatedArtifact("Export DXF", "dxf")).toString();
    expect(dxf).toContain("PRELIMINARY");
    expect(dxf).toContain(name);

    await page.getByTestId("workspace-project-actions").locator("summary").click();
    const [landxml, download] = await Promise.all([
      page.waitForResponse(value => value.url().endsWith("/api/export/landxml") && value.request().method() === "POST", { timeout: 20_000 }),
      page.waitForEvent("download", { timeout: 20_000 }),
      page.getByRole("button", { name: "Export LandXML", exact: true }).click(),
    ]);
    expect(landxml.status()).toBe(200);
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    const xml = await readFile(downloadPath!, "utf8");
    expect(xml).toContain("<LandXML");
    expect(xml).toContain('civoraCanonicalId="SYN-STORM-PIPE-1"');
    expect(xml).toContain('length="178.885"');
    expect(xml).toContain('diameter="1.500"');
    expect(xml).toContain('slope="0.010000"');
    expect(xml).toContain('civoraReviewOnly="true"');
    expect(xml).toContain('civoraConstructionReleaseAllowed="false"');
    expect(xml).toContain('civoraCivil3dVerificationStatus="not_verified"');
  }
});
