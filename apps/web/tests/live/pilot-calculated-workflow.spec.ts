import { expect, test } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { canonicalPipeSegmentFromPlacement, detailedGeometryBinding, validatePipeProfile } from "../../app/utils/detailedObjectGeometry";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

for (const { assisted, target } of [
  { assisted: false, target: "parking" },
  { assisted: true, target: "parking" },
  { assisted: true, target: "full" },
]) test(`website commercial ${target} ${assisted ? "assisted run saves and reopens" : "manual failure stays blocked"}`, async ({ page, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only; never runs hosted generation.");
  test.setTimeout(600_000);
  page.setDefaultTimeout(15_000);
  const name = `Calculated pilot ${randomUUID()}`;
  let uiAuthoredPipe: { id: string; lengthFt: number; endInvertFt: number } | null = null;
  // The full multidisciplinary fixture intentionally leaves enough separation
  // for generated drainage and utility review geometry. The compact parking
  // fixture remains useful for the narrower parking-only probes.
  const small = target !== "full";
  const registration = await request.post(`${api}/api/auth/register`, { data: { email: `calc-${randomUUID()}@example.test`, name: "Synthetic calculation test", password: "Disposable-123" } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json(), headers = { Authorization: `Bearer ${token}` };
  const jobSummary = async (jobId: string) => {
    const jobsPage = await (await request.get(`${api}/api/jobs?limit=100`, { headers })).json();
    const job = jobsPage.jobs.find((item: { job_id: string }) => item.job_id === jobId);
    expect(job, `Job ${jobId} should remain visible in the bounded job summary`).toBeTruthy();
    return job;
  };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: withCanonicalCanvasSnapshot({
    input_mode: assisted ? "assisted" : "user", allow_ai_fill_for_blanks: assisted,
    manual_fields: { project_name: name, units: "ft", project_type: "commercial_pad", building_width: small ? 60 : 169, building_depth: small ? 40 : 85,
      terrain: "2% slope west to east", setback: 20, lot: { x: 0, y: 0, w: small ? 240 : 900, h: small ? 180 : 700 },
      site_plan: { building_program_sf: small ? 2400 : 14365, building_count: 1, building_type: "office", parking_count: small ? 12 : 60 },
      pipe_network: target === "full" ? [{
        id: "SYN-STORM-PIPE-1", label: "Synthetic storm trunk", utility_type: "storm",
        points: [[600, 420], [760, 500]], path: [[600, 420], [760, 500]],
        canonical_id: "SYN-STORM-PIPE-1", length_ft: 178.885, diameter_in: 18, slope_ft_ft: 0.01,
        from_node: "SYN-STORM-START", to_node: "SYN-STORM-END",
        invert_start_ft: 90, invert_end_ft: 88.21115,
        endpoint_structures: [
          { id: "SYN-STORM-START", name: "SYN-STORM-START", x: 600, y: 420, rim_elevation_ft: 100, sump_elevation_ft: 89 },
          { id: "SYN-STORM-END", name: "SYN-STORM-END", x: 760, y: 500, rim_elevation_ft: 99, sump_elevation_ft: 87.5 },
        ],
        source: "manual_drawn", review_required: true, construction_release_allowed: false,
      }] : [],
      site_objects: [
        { id: "parcel", label: "Synthetic parcel", type: "site", x: 0, y: 0, w: small ? 240 : 900, d: small ? 180 : 700, placed: true },
        { id: "office", label: "Synthetic office", type: "office_building", x: small ? 80 : 300, y: small ? 40 : 120, w: small ? 60 : 169, d: small ? 40 : 85, placed: true,
          ...(small ? {} : { source: "manual_drawn", generated: true, meta: { generated_review_concept: true, requested_project_type: "commercial_pad" } }) },
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
  if (target === "full") {
    // Prove this is the audited edited-concept 169 x 85 fixture before Generate. A similarly
    // named hosted QA project with only a 28,000-sf program auto-sizes a review
    // concept and is not evidence for this canonical edit/export contract.
    await openWorkspaceTool(page, "Draw");
    const objectList = page.getByTestId("object-manager-panel");
    if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Synthetic office" }).first();
    await officeRow.getByTestId("object-manager-select").click();
    await officeRow.getByTestId("object-manager-inspect").click();
    await expect(page.getByTestId("selected-object-width-input")).toHaveValue("169");
    await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("85");
    const stored = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    expect(stored.project_input.manual_fields.pipe_network).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: "SYN-STORM-PIPE-1",
        from_node: "SYN-STORM-START",
        to_node: "SYN-STORM-END",
        diameter_in: 18,
        slope_ft_ft: 0.01,
      }),
    ]));

    // Create a second valid storm segment through ordinary workspace controls.
    // This proves the editor, canonical project, recalculation and LandXML use
    // one saved source rather than relying on the API-seeded compatibility row.
    const savedProject = async () => (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    const addThroughCommand = async (command: string, label: string) => {
      await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
      await page.getByTestId("civora-command-input").fill(command);
      await page.getByTestId("civora-command-input").press("Enter");
      await expect.poll(async () => (await savedProject()).project_input.manual_fields.site_objects.some((item: { label: string }) => item.label === label), { timeout: 30_000 }).toBe(true);
    };
    await addThroughCommand("add storm sewer", "Storm Sewer");
    // Add the endpoint structures through the advertised Drainage workbench.
    // This is the ordinary editor path and avoids treating the chat parser as
    // a privileged fixture loader.
    await page.getByTestId("workspace-stage-analyze").click();
    await page.getByTestId("workspace-stage-panel").selectOption("drainage");
    await page.getByRole("button", { name: "Inlet", exact: true }).click();
    await expect.poll(async () => (await savedProject()).project_input.manual_fields.site_objects.some((item: { type: string }) => item.type === "inlet"), { timeout: 30_000 }).toBe(true);
    await page.getByRole("button", { name: "Outfall Point", exact: true }).click();
    await expect.poll(async () => (await savedProject()).project_input.manual_fields.site_objects.some((item: { type: string }) => item.type === "outfall"), { timeout: 30_000 }).toBe(true);
    let uiObjects = (await savedProject()).project_input.manual_fields.site_objects as Array<{ id: string; label: string; type: string; geometry?: Array<[number, number]> }>;
    const storm = uiObjects.find(item => item.label === "Storm Sewer")!, inlet = uiObjects.find(item => item.type === "inlet")!, outfall = uiObjects.find(item => item.type === "outfall")!;
    expect(storm.geometry!.length).toBeGreaterThanOrEqual(2);
    const routeStart = storm.geometry![0], routeEnd = storm.geometry![storm.geometry!.length - 1];
    await openWorkspaceTool(page, "Draw");
    await page.getByTestId("workspace-stage-panel").selectOption("details");
    const detailsPanel = page.getByTestId("workspace-right-panel");
    for (const [object, point] of [[inlet, routeStart], [outfall, routeEnd]] as const) {
      await detailsPanel.getByRole("button", { name: new RegExp(`^${object.label}`) }).click();
      await expect(page.getByLabel("Selected object name")).toHaveValue(object.label);
      await page.getByTestId("selected-object-x-input").fill(String(point[0]));
      await page.getByTestId("selected-object-x-input").blur();
      await page.getByTestId("selected-object-y-input").fill(String(point[1]));
      await page.getByTestId("selected-object-y-input").blur();
    }
    await expect.poll(async () => {
      const objects = (await savedProject()).project_input.manual_fields.site_objects;
      return [inlet, outfall].every((source, index) => {
        const object = objects.find((candidate: { id: string }) => candidate.id === source.id);
        const expected = index ? routeEnd : routeStart;
        return Number(object?.x) === expected[0] && Number(object?.y) === expected[1];
      });
    }, { timeout: 30_000 }).toBe(true);
    await detailsPanel.getByRole("button", { name: new RegExp(`^${storm.label}`) }).click();
    await expect(page.getByLabel("Selected object name")).toHaveValue(storm.label);
    await openWorkspaceTool(page, "Draw");
    if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
    await page.getByText("Engineering properties", { exact: true }).click();
    await page.getByLabel("Pipe outside diameter (ft)").fill("1.5");
    await page.getByRole("button", { name: "Apply pipe diameter", exact: true }).click();
    await page.getByText("Detailed geometry", { exact: true }).click();
    await page.getByTestId("object-detailed-geometry").locator("summary").click();
    await page.getByRole("button", { name: "Apply pipe depth profile", exact: true }).click();
    await expect(page.getByTestId("object-detailed-geometry").getByRole("alert")).toContainText("invert elevation");
    await page.getByLabel("Detailed elevation datum").fill("Synthetic QA datum");
    await page.getByLabel("Detailed geometry evidence source").fill("Synthetic UI fixture; not survey evidence");
    await page.getByLabel("Pipe network").selectOption("storm");
    await page.getByLabel("Pipe start structure").selectOption(inlet.id);
    await page.getByLabel("Pipe end structure").selectOption(inlet.id);
    const invertInputs = page.getByLabel(/Pipe invert elevation at vertex/);
    const routeLength = storm.geometry!.slice(1).reduce((sum, point, index) => sum + Math.hypot(point[0] - storm.geometry![index][0], point[1] - storm.geometry![index][1]), 0);
    let station = 0;
    for (let index = 0; index < storm.geometry!.length; index += 1) {
      if (index) station += Math.hypot(storm.geometry![index][0] - storm.geometry![index - 1][0], storm.geometry![index][1] - storm.geometry![index - 1][1]);
      await invertInputs.nth(index).fill(String(90 - station * 0.01));
    }
    const endInvert = 90 - routeLength * 0.01;
    await page.getByLabel("Pipe start rim elevation").fill("100");
    await page.getByLabel("Pipe start sump elevation").fill("89");
    await page.getByLabel("Pipe end rim elevation").fill("99");
    await page.getByLabel("Pipe end sump elevation").fill(String(endInvert - 1));
    await page.getByLabel("I reviewed this detailed geometry against its source.").check();
    await page.getByRole("button", { name: "Apply pipe depth profile", exact: true }).click();
    await expect(page.getByTestId("object-detailed-geometry").getByRole("alert")).toContainText("different explicit objects");
    await page.getByLabel("Pipe end structure").selectOption(outfall.id);
    await page.getByRole("button", { name: "Apply pipe depth profile", exact: true }).click();
    await expect(page.getByTestId("object-detailed-geometry").getByRole("alert")).toHaveCount(0);
    await expect.poll(async () => {
      const savedAfterProfile = await savedProject();
      const objects = savedAfterProfile.project_input.manual_fields.site_objects;
      const persistedStorm = objects.find((item: { id: string }) => item.id === storm.id);
      const persistedProfile = persistedStorm?.meta?.pipe_profile_v1;
      if (persistedStorm && persistedProfile) {
        const normalizedStorm = { ...persistedStorm, geometryType: persistedStorm.geometryType ?? persistedStorm.geometry_type };
        const normalizedObjects = objects.map((item: { geometryType?: string; geometry_type?: string }) => ({ ...item, geometryType: item.geometryType ?? item.geometry_type }));
        expect(validatePipeProfile(persistedProfile, normalizedStorm), `stored=${persistedProfile.geometryBinding} current=${detailedGeometryBinding(normalizedStorm)}`).toBeNull();
        expect(canonicalPipeSegmentFromPlacement(normalizedStorm, normalizedObjects)).not.toBeNull();
      }
      const pipe = (savedAfterProfile.project_input.manual_fields.pipe_network ?? []).find((item: { id: string }) => item.id === storm.id);
      return Boolean(pipe && pipe.diameter_in === 18 && pipe.from_node === inlet.id && pipe.to_node === outfall.id && Math.abs(pipe.slope_ft_ft - 0.01) < 1e-12);
    }, { timeout: 30_000 }).toBe(true);
    const persistedPipe = ((await savedProject()).project_input.manual_fields.pipe_network ?? []).find((item: { id: string }) => item.id === storm.id);
    expect(persistedPipe.endpoint_structures).toEqual([
      expect.objectContaining({ id: inlet.id, name: inlet.label, x: routeStart[0], y: routeStart[1], rim_elevation_ft: 100, sump_elevation_ft: 89 }),
      expect.objectContaining({ id: outfall.id, name: outfall.label, x: routeEnd[0], y: routeEnd[1], rim_elevation_ft: 99, sump_elevation_ft: endInvert - 1 }),
    ]);
    expect(persistedPipe.invert_start_ft).toBe(90);
    expect(persistedPipe.invert_end_ft).toBeCloseTo(endInvert, 9);
    uiAuthoredPipe = { id: storm.id, lengthFt: routeLength, endInvertFt: endInvert };
    await page.reload();
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    expect(((await savedProject()).project_input.manual_fields.pipe_network ?? []).find((item: { id: string }) => item.id === storm.id)).toMatchObject({ diameter_in: 18, invert_start_ft: 90, invert_end_ft: endInvert });
  }
  page.on("dialog", dialog => dialog.accept());
  await openWorkspaceTool(page, "Generate");
  const execution = page.waitForResponse(response => response.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(response.url()), { timeout: 20_000 });
  await page.getByTestId(target === "full" ? "generate-main-action" : "generate-parking").click();
  const response = await execution;
  expect(response.status()).toBe(200);
  const payload = await response.json();
  if (payload.job) {
    await expect.poll(async () => {
      const job = await jobSummary(payload.job.job_id);
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
  if (target === "full") expect(initialBuildingArea).toBe(169 * 85);
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
  if (target === "full") {
    await openWorkspaceTool(page, "Review");
    await expect(page.getByTestId("review-result-truth")).toHaveAttribute("data-result-state", "current");
    await expect(page.getByTestId("review-result-truth")).toContainText("Current calculation");
  }
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
    await openWorkspaceTool(page, "Review");
    await expect(page.getByTestId("review-result-truth")).toHaveAttribute("data-result-state", "stale");
    await expect(page.getByTestId("review-result-truth")).toContainText("Recalculation required");
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await page.getByTestId("civora-command-input").fill("what is blocked");
    await page.getByTestId("civora-command-input").press("Enter");
    await expect(page.getByText(/Recalculation required: The layout changed after the saved calculation/i)).toBeVisible();

    await openWorkspaceTool(page, "Generate");
    const recalculation = page.waitForResponse(value => value.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(value.url()), { timeout: 20_000 });
    const recalculationStartedAt = Date.now();
    await page.getByTestId("generate-main-action").click();
    const recalculationPayload = await (await recalculation).json();
    expect(recalculationPayload.job).toBeTruthy();
    let lastRecalculationState = "";
    await expect.poll(async () => {
      const job = await jobSummary(recalculationPayload.job.job_id);
      const state = JSON.stringify({ status: job.status, stage: job.stage, detail: job.stage_detail, progress: job.progress });
      if (state !== lastRecalculationState) {
        lastRecalculationState = state;
        console.log(`[recalculation ${new Date().toISOString()}] ${state}`);
      }
      if (job.status === "awaiting_approval") {
        const proceed = page.getByTestId("generate-main-action");
        if ((await proceed.textContent())?.includes("Continue after") && await proceed.isEnabled()) {
          // The job poller can switch this control to "Starting next stage"
          // between reading its label and clicking it. That is a normal
          // in-flight transition; retry on the next poll instead of blocking
          // the entire acceptance loop on a now-disabled button.
          await proceed.click({ timeout: 2_000 }).catch(() => undefined);
        }
      }
      return job.status;
    }, {
      timeout: Number(process.env.CIVORA_RECALC_DIAGNOSTIC_TIMEOUT_MS || 120_000),
      intervals: [1000],
    }).toBe("completed");
    const recalculationElapsedMs = Date.now() - recalculationStartedAt;
    console.log(`[recalculation completed] elapsed_ms=${recalculationElapsedMs}`);
    if (process.env.CIVORA_RECALC_DIAGNOSTIC_TIMEOUT_MS) {
      // A diagnostic observation may continue into downstream correctness
      // checks, but the unchanged 120-second product acceptance remains a
      // separately reported soft failure.
      expect.soft(recalculationElapsedMs, "full recalculation must complete within 120 seconds").toBeLessThanOrEqual(120_000);
    } else {
      expect(recalculationElapsedMs).toBeLessThanOrEqual(120_000);
    }
    await expect.poll(async () => (await saved()).result_freshness_v1.status, { timeout: 30_000 }).toBe("current");
    const revisedCheckpoint = await saved();
    expect(revisedCheckpoint.latest_result.metadata.calculation_save_v1.calculation_id).not.toBe(calculationId);
    const revisedOffice = revisedCheckpoint.latest_result.final_plan.actions.find((action: { canonical_source_id?: string; layer?: string }) => action.canonical_source_id === "office" && action.layer === "BUILDING");
    expect(revisedOffice?.width).toBe(revisedWidth);
    expect(revisedOffice?.height).toBe(originalDepth);
    const expectedBuildingAreaDelta = 10 * originalDepth;
    expect(revisedOffice.width * revisedOffice.height - originalWidth * originalDepth).toBe(expectedBuildingAreaDelta);
    const revisedBuildingArea = revisedCheckpoint.latest_result.final_plan.meta.quantities?.totals?.building_area_sf;
    expect(revisedBuildingArea).toBe(revisedWidth * originalDepth);
    expect(revisedBuildingArea - initialBuildingArea).toBe(expectedBuildingAreaDelta);
    const revisedStages = revisedCheckpoint.latest_result.final_plan.meta.stage_results ?? [];
    for (const stageName of ["grading", "drainage", "storm_pipes", "sanitary", "utility_network"]) {
      const stages = revisedStages.filter((item: { stage_name?: string }) => item.stage_name === stageName);
      expect(stages.length, `${stageName} must remain in the building-resize dependency closure`).toBeGreaterThan(0);
      expect(
        stages.some((stage: { meta?: { resumed_from_checkpoint?: boolean } }) => !(stage.meta?.resumed_from_checkpoint ?? false)),
        `${stageName} must include an executed result for the revised model`,
      ).toBe(true);
    }
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
    await openWorkspaceTool(page, "Review");
    await expect(page.getByTestId("review-result-truth")).toHaveAttribute("data-result-state", "current");
    await expect(page.getByTestId("review-result-truth")).toContainText("Current calculation");

    // Exercise calculated exports from a real engine result, not an injected
    // fixture. Preliminary release must retain its engineering limitations.
    await openWorkspaceTool(page, "Deliver");
    const freshnessBeforePackage = (await saved()).result_freshness_v1.status;
    expect(freshnessBeforePackage).toBe("current");
    await page.getByRole("button", { name: "Make Review Package", exact: true }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toBeVisible();
    await expect.poll(async () => (await saved()).result_freshness_v1.status, { timeout: 30_000 }).toBe("current");
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
      await page.waitForTimeout(6_500);
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
    const expectedPipeId = uiAuthoredPipe?.id ?? "SYN-STORM-PIPE-1";
    const authoredPipe = xml.match(new RegExp(`<Pipe\\b(?=[^>]*civoraCanonicalId="${expectedPipeId}")[^>]*>[\\s\\S]*?<\\/Pipe>`))?.[0];
    expect(authoredPipe).toBeTruthy();
    const attr = (name: string) => authoredPipe!.match(new RegExp(`${name}="([^"]+)"`))?.[1];
    expect(Number(attr("length"))).toBeCloseTo(uiAuthoredPipe?.lengthFt ?? 178.885, 3);
    expect(Number(attr("slope"))).toBeCloseTo(1, 6); // LandXML slope is percent.
    expect(Number(authoredPipe!.match(/<CircPipe\b[^>]*diameter="([^"]+)"/)?.[1])).toBeCloseTo(18 / 12, 6);
    expect(attr("civoraReviewOnly")).toBe("true");
    expect(attr("civoraConstructionReleaseAllowed")).toBe("false");
    expect(attr("civoraCivil3dVerificationStatus")).toBe("not_verified");
  }
});
