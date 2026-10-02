import { expect, test } from "@playwright/test";

import type { BuildingPlacement } from "../../app/types";
import {
  applyCanonicalUpdateCommand,
  canonicalControlState,
  createCanonicalUpdateCommand,
} from "../../app/utils/canonicalEditCommands";
import {
  applyBuildingParkingDependency,
  setParkingDependencyObjectLinked,
} from "../../app/utils/canonicalDependencyPolicies";
import { buildLiveConstraintFeedback } from "../../app/utils/liveConstraintFeedback";
import { calculateParkingLayout } from "../../app/utils/parkingLayoutEngine";
import { buildPreviewParkingMapModules } from "../../app/utils/previewParkingMapModules";
import { generateLayoutAlternatives, parseLayoutGoals, rerankLayoutAlternatives } from "../../app/utils/layoutAlternatives";

test("canonical update commands preserve source, revision, and control state", () => {
  const building: BuildingPlacement = {
    id: "BLDG-1",
    label: "Building 1",
    type: "building",
    x: 100,
    y: 100,
    w: 120,
    d: 60,
    placed: true,
    meta: { canonical_revision: 3, canonical_control_state: "flexible" },
  };
  const command = createCanonicalUpdateCommand(
    building.id,
    { x: 130, meta: { canonical_edit_source: "chat" } },
    "chat",
    "tx-chat-move-1",
    "2026-10-01T12:00:00.000Z",
  );
  const result = applyCanonicalUpdateCommand(building, command);

  expect(result.blockedReason).toBeNull();
  expect(result.object.x).toBe(130);
  expect(result.object.meta?.canonical_revision).toBe(4);
  expect(result.object.meta?.canonical_last_edit).toEqual({
    transaction_id: "tx-chat-move-1",
    source: "chat",
    command: "update_object",
    changed_fields: ["x"],
    created_at: "2026-10-01T12:00:00.000Z",
  });
});

test("fixed canonical objects reject geometry edits until explicitly unlocked", () => {
  const building: BuildingPlacement = {
    id: "BLDG-FIXED",
    label: "Fixed Building",
    type: "building",
    x: 20,
    y: 20,
    w: 80,
    d: 40,
    locked: true,
    placed: true,
  };

  expect(canonicalControlState(building)).toBe("fixed");
  const blocked = applyCanonicalUpdateCommand(
    building,
    createCanonicalUpdateCommand(building.id, { x: 50 }, "chat", "tx-blocked"),
  );
  expect(blocked.object.x).toBe(20);
  expect(blocked.blockedReason).toContain("fixed");

  const unlocked = applyCanonicalUpdateCommand(
    building,
    createCanonicalUpdateCommand(building.id, { x: 50, locked: false }, "chat", "tx-unlocked"),
  );
  expect(unlocked.blockedReason).toBeNull();
  expect(unlocked.object.x).toBe(50);
  expect(unlocked.object.meta?.canonical_control_state).toBe("flexible");
});

test("building parking relationships honor follow, ask, and fixed policies", () => {
  const building: BuildingPlacement = {
    id: "BLDG-REL",
    label: "Anchor Building",
    type: "building",
    x: 100,
    y: 100,
    w: 120,
    d: 60,
    placed: true,
    meta: { canonical_relationships: { parking: { policy: "follow", object_ids: ["PARK-1"] } } },
  };
  const parking: BuildingPlacement = {
    id: "PARK-1",
    label: "Parking 1",
    type: "parking",
    x: 80,
    y: 190,
    w: 180,
    d: 90,
    placed: true,
    meta: { canonical_parent_id: building.id },
  };
  const command = createCanonicalUpdateCommand(building.id, { x: 125 }, "chat", "tx-follow", "2026-10-01T12:00:00.000Z");
  const movedBuilding = applyCanonicalUpdateCommand(building, command).object;
  const followed = applyBuildingParkingDependency([building, parking], building, movedBuilding, command);
  expect(followed.policy).toBe("follow");
  expect(followed.after[0].x).toBe(105);
  expect((followed.after[0].meta?.canonical_last_edit as { transaction_id?: string }).transaction_id).toBe("tx-follow");

  const askBuilding = { ...building, meta: { canonical_relationships: { parking: { policy: "ask", object_ids: ["PARK-1"] } } } };
  const asked = applyBuildingParkingDependency([askBuilding, parking], askBuilding, { ...askBuilding, x: 125 }, command);
  expect(asked.before[0].x).toBe(80);
  expect(asked.after[0].x).toBe(105);
  expect(asked.proposalObjectIds).toEqual(["PARK-1"]);

  const fixedBuilding = { ...building, meta: { canonical_relationships: { parking: { policy: "fixed", object_ids: ["PARK-1"] } } } };
  const fixed = applyBuildingParkingDependency([fixedBuilding, parking], fixedBuilding, { ...fixedBuilding, x: 125 }, command);
  expect(fixed.after[0].x).toBe(80);
  expect(fixed.proposalObjectIds).toEqual([]);
});

test("explicit unlinking overrides legacy parent metadata", () => {
  const building: BuildingPlacement = {
    id: "BLDG-LINK",
    label: "Linked Building",
    type: "building",
    x: 0,
    y: 0,
    w: 50,
    d: 50,
    placed: true,
    meta: { canonical_relationships: { parking: { policy: "follow", object_ids: ["PARK-LINK"] } } },
  };
  const parking: BuildingPlacement = {
    id: "PARK-LINK",
    label: "Linked Parking",
    type: "parking",
    x: 0,
    y: 60,
    w: 80,
    d: 40,
    placed: true,
    meta: { canonical_parent_id: building.id },
  };
  const unlinked = { ...building, ...setParkingDependencyObjectLinked(building, parking.id, false) };
  const command = createCanonicalUpdateCommand(building.id, { x: 10 }, "manual_cad", "tx-unlink");
  const result = applyBuildingParkingDependency([unlinked, parking], unlinked, { ...unlinked, x: 10 }, command);
  expect(result.before).toEqual([]);
  expect(result.after).toEqual([]);
});

test("parking reflow chooses an in-site collision-free alternative and preserves stalls", () => {
  const site: BuildingPlacement = { id: "SITE", label: "Site", type: "site", x: 0, y: 0, w: 300, d: 300, placed: true };
  const building: BuildingPlacement = {
    id: "BLDG-REFLOW",
    label: "Building",
    type: "building",
    x: 40,
    y: 40,
    w: 70,
    d: 50,
    placed: true,
    meta: { canonical_relationships: { parking: { policy: "follow", object_ids: ["PARK-REFLOW"] } } },
  };
  const parking: BuildingPlacement = {
    id: "PARK-REFLOW",
    label: "Parking",
    type: "parking",
    x: 40,
    y: 130,
    w: 100,
    d: 70,
    stallCount: 32,
    placed: true,
    meta: { parkingModuleCols: 4, parkingModuleRows: 2 },
  };
  const obstacle: BuildingPlacement = { id: "BLOCK", label: "Other Building", type: "building", x: 85, y: 115, w: 120, d: 110, placed: true };
  const command = createCanonicalUpdateCommand(building.id, { x: 90 }, "manual_cad", "tx-reflow");
  const movedBuilding = { ...building, x: 90 };
  const result = applyBuildingParkingDependency([site, building, parking, obstacle], building, movedBuilding, command);
  expect(result.after[0].stallCount).toBe(32);
  expect(result.reflowReports[0]).toMatchObject({ status: "clear", insideSite: true, stallCountPreserved: true });
  expect(result.reflowReports[0].collisionObjectIds).toEqual([]);
  expect(result.after[0].x).toBeGreaterThanOrEqual(12);
  expect(result.after[0].y).toBeGreaterThanOrEqual(12);
  expect((result.after[0].meta?.parking_reflow_v1 as { version?: number }).version).toBe(1);
});

test("live constraints identify selected objects outside the site and in collision", () => {
  const site: BuildingPlacement = { id: "SITE-LIVE", label: "Site", type: "site", x: 0, y: 0, w: 200, d: 200, placed: true };
  const selected: BuildingPlacement = { id: "BLDG-LIVE", label: "Selected", type: "building", x: 175, y: 40, w: 50, d: 50, placed: true };
  const obstacle: BuildingPlacement = { id: "BLDG-OTHER", label: "Other", type: "building", x: 160, y: 50, w: 30, d: 30, placed: true };
  const feedback = buildLiveConstraintFeedback([site, selected, obstacle], selected.id);
  expect(feedback.issues.map((issue) => issue.code)).toEqual(expect.arrayContaining(["outside_site_boundary", "surface_footprint_contact"]));
  expect(feedback.objectIds).toEqual(expect.arrayContaining([selected.id, obstacle.id]));
  expect(feedback.conflictCount).toBeGreaterThan(0);
});

test("parking capacity truthfully reports fit, shortfall, ADA aisles, and generated stall count", () => {
  const params = {
    stallWidth: 9,
    stallDepth: 18,
    aisleWidth: 24,
    adaAisleWidth: 8,
    adaCount: 2,
    compactCount: 2,
    compactWidth: 8,
    angleDeg: 90,
    loading: "double" as const,
    autoResizeToFitCount: false,
    useMixedAngles: false,
    compactZone: true,
  };
  const fits = calculateParkingLayout({ w: 100, d: 66 }, params, 20);
  expect(fits).toMatchObject({ status: "fits", maxStalls: 20, generatedStalls: 20, shortfall: 0 });
  const short = calculateParkingLayout({ w: 100, d: 66 }, params, 30);
  expect(short).toMatchObject({ status: "shortfall", maxStalls: 20, generatedStalls: 20, shortfall: 10 });

  const parking: BuildingPlacement = {
    id: "PARK-CAPACITY",
    label: "Capacity Parking",
    type: "parking",
    x: 0,
    y: 0,
    w: 100,
    d: 66,
    stallCount: 20,
    placed: true,
    meta: { parkingParams: params, parkingModuleCols: 1, parkingModuleRows: 1 },
  };
  const stalls = buildPreviewParkingMapModules(parking, []).flatMap((module) => module.stallPolygons);
  expect(stalls.filter((stall) => stall.kind !== "ada_aisle")).toHaveLength(20);
  expect(stalls.filter((stall) => stall.kind === "ada")).toHaveLength(2);
  expect(stalls.filter((stall) => stall.kind === "compact")).toHaveLength(2);
});

test("layout alternatives are distinct scored snapshots that do not mutate the source", () => {
  const source: BuildingPlacement[] = [
    { id: "ALT-SITE", label: "Site", type: "site", x: 0, y: 0, w: 600, d: 500, placed: true },
    { id: "ALT-BLDG", label: "Building", type: "building", x: 200, y: 80, w: 140, d: 80, placed: true },
    { id: "ALT-PARK", label: "Parking", type: "parking", x: 150, y: 220, w: 260, d: 130, stallCount: 60, placed: true },
  ];
  const alternatives = generateLayoutAlternatives(source, 5);
  expect(alternatives).toHaveLength(5);
  expect(source[2].y).toBe(220);
  expect(new Set(alternatives.map((item) => item.placements.find((placement) => placement.id === "ALT-PARK")?.y)).size).toBeGreaterThan(1);
  expect(alternatives.every((item) => Number.isFinite(item.metrics.capacity) && Number.isFinite(item.metrics.conflicts))).toBe(true);
  expect(alternatives.some((item) => item.differences.some((difference) => difference.id === "ALT-BLDG" && difference.moved))).toBe(true);
});

test("natural-language layout goals produce ranked, explained conservative and aggressive options", () => {
  const source: BuildingPlacement[] = [
    { id: "GOAL-SITE", label: "Site", type: "site", x: 0, y: 0, w: 700, d: 520, placed: true },
    { id: "GOAL-ENTRY", label: "Entry", type: "entrance", x: 330, y: 500, w: 20, d: 20, placed: true },
    { id: "GOAL-BLDG", label: "Building", type: "building", x: 220, y: 90, w: 160, d: 90, placed: true },
    { id: "GOAL-PARK", label: "Parking", type: "parking", x: 170, y: 240, w: 330, d: 150, stallCount: 80, placed: true },
  ];
  const request = parseLayoutGoals("Show one conservative option and four aggressive options that maximize parking and minimize conflicts");
  const alternatives = generateLayoutAlternatives(source, 5, request);
  expect(request.goals?.map((goal) => goal.key)).toEqual(["maximize_parking", "minimize_conflicts"]);
  expect(request.profile).toBe("mixed");
  expect(alternatives.map((item) => item.score)).toEqual([...alternatives.map((item) => item.score)].sort((a, b) => b - a));
  expect(alternatives[0].rank).toBe(1);
  expect(alternatives.some((item) => item.profile === "conservative")).toBe(true);
  expect(alternatives.some((item) => item.profile === "aggressive")).toBe(true);
  expect(alternatives.every((item) => item.scoreReasons.length === 2)).toBe(true);
  const conflictsOnly = request.goals?.filter((goal) => goal.key === "minimize_conflicts") ?? [];
  const reranked = rerankLayoutAlternatives(alternatives, conflictsOnly);
  expect(reranked[0].rank).toBe(1);
  expect(reranked.every((item) => item.goalLabels.length === 1 && item.goalLabels[0] === "minimize conflicts")).toBe(true);
});

test("layout alternatives preserve fixed, existing, and reference geometry", () => {
  const source: BuildingPlacement[] = [
    { id: "FIX-SITE", label: "Site", type: "site", x: 0, y: 0, w: 600, d: 500, placed: true },
    { id: "FIX-BLDG", label: "Protected Building", type: "building", x: 200, y: 80, w: 140, d: 80, placed: true, locked: true },
    { id: "FLEX-PARK", label: "Flexible Parking", type: "parking", x: 150, y: 220, w: 260, d: 130, stallCount: 60, placed: true },
  ];
  const alternatives = generateLayoutAlternatives(source, 5);
  expect(alternatives.every((alternative) => alternative.placements.find((item) => item.id === "FIX-BLDG")?.x === 200)).toBe(true);
  expect(alternatives.every((alternative) => !alternative.differences.some((item) => item.id === "FIX-BLDG"))).toBe(true);
  expect(alternatives.every((alternative) => alternative.fixedObjectCount >= 1)).toBe(true);
  expect(alternatives[0].searchReport.explored).toBe(32);
  expect(alternatives[0].searchReport.accepted).toBeGreaterThanOrEqual(alternatives.length);
});

test("chat move and CAD editing share the canonical update path", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const row = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await row.getByTestId("object-manager-select").click();
  await row.getByTestId("object-manager-inspect").click();
  const xInput = page.getByTestId("selected-object-x-input");
  const initialX = Number(await xInput.inputValue());
  await page.getByTestId("parking-dependency-policy").selectOption("follow");

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const commandInput = page.getByTestId("civora-command-input");
  await commandInput.fill("move the selected building 25 ft east");
  await commandInput.press("Enter");

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) {
    await objectList.locator("summary").click();
  }
  await page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first().getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialX + 25));
  await expect(page.getByTestId("selected-object-status")).toContainText(/geometry changed.*Undo can restore/i);
});

test("user can opt linked parking into following a building edit", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) {
    await objectList.locator("summary").click();
  }

  const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "West Parking Field" }).first();
  await parkingRow.getByTestId("object-manager-select").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  const initialParkingX = Number(await page.getByTestId("selected-object-x-input").inputValue());

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) {
    await objectList.locator("summary").click();
  }
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await page.getByTestId("parking-dependency-policy").selectOption("follow");

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("move the selected building 25 ft east");
  await page.getByTestId("civora-command-input").press("Enter");

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) {
    await objectList.locator("summary").click();
  }
  await parkingRow.getByTestId("object-manager-inspect").click();
  await expect.poll(async () => Number(await page.getByTestId("selected-object-x-input").inputValue())).not.toBe(initialParkingX);
  await expect(page.getByTestId("selected-object-status")).toContainText(/linked parking reflowed/i);
  await expect(page.getByTestId("parking-reflow-status")).toBeVisible();
});

test("ask mode previews the whole transaction and rejection preserves building and parking", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();

  const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "West Parking Field" }).first();
  await parkingRow.getByTestId("object-manager-select").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  const initialParkingX = Number(await page.getByTestId("selected-object-x-input").inputValue());

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("parking-dependency-policy")).toHaveValue("ask");
  const initialBuildingX = await page.getByTestId("selected-object-x-input").inputValue();

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("move the selected building 25 ft east");
  await page.getByTestId("civora-command-input").press("Enter");
  await expect(page.getByTestId("dependency-proposal-card")).toBeVisible();
  await expect(page.getByTestId("dependency-proposal-geometry")).toBeVisible();
  await expect(page.getByTestId("dependency-proposal-card")).toContainText("3-object change");
  await page.getByTestId("dependency-proposal-reject").click();
  await expect(page.getByTestId("dependency-proposal-card")).toHaveCount(0);

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(initialBuildingX);
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialParkingX));
});

test("accepting an ask-mode proposal commits linked parking as one undoable change", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "West Parking Field" }).first();
  await parkingRow.getByTestId("object-manager-select").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  const initialParkingX = Number(await page.getByTestId("selected-object-x-input").inputValue());

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  const initialBuildingX = Number(await page.getByTestId("selected-object-x-input").inputValue());
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("move the selected building 10 ft east");
  await page.getByTestId("civora-command-input").press("Enter");
  await page.getByTestId("dependency-proposal-accept").click();
  await expect(page.getByTestId("dependency-proposal-card")).toHaveCount(0);

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialBuildingX + 10));
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  await expect.poll(async () => Number(await page.getByTestId("selected-object-x-input").inputValue())).not.toBe(initialParkingX);
  await expect(page.getByTestId("selected-object-status")).toContainText(/proposal accepted.*Undo restores/i);
  await expect(page.getByTestId("parking-reflow-status")).toBeVisible();
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialParkingX));
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialBuildingX));
});

test("users can visually unlink and relink parking from a building", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();

  const westParkingLink = page.getByTestId("parking-relationship-demo-parking-north");
  await expect(westParkingLink).toBeChecked();
  await expect(page.getByTestId("dependency-link-demo-building-a-demo-parking-north")).toBeVisible();
  await westParkingLink.uncheck();
  await expect(westParkingLink).not.toBeChecked();
  await expect(page.getByTestId("dependency-link-demo-building-a-demo-parking-north")).toHaveCount(0);
  await westParkingLink.check();
  await expect(westParkingLink).toBeChecked();
  await expect(page.getByTestId("dependency-link-demo-building-a-demo-parking-north")).toBeVisible();
});

test("constraint warnings update immediately when a selected building moves outside the site", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  const xInput = page.getByTestId("selected-object-x-input");
  await page.getByTestId("parking-dependency-policy").selectOption("fixed");
  await xInput.fill("980");
  await expect(page.getByTestId("live-constraint-card")).toContainText(/extends beyond the current site boundary/i);
  await expect(page.getByTestId("live-constraint-geometry")).toBeVisible();
  await xInput.fill("350");
  await expect(page.getByTestId("live-constraint-card")).toHaveCount(0);
});

test("parking inspector reports capacity shortfalls and recovers when the request fits", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "West Parking Field" }).first();
  await parkingRow.getByTestId("object-manager-select").click();
  await parkingRow.getByTestId("object-manager-inspect").click();
  const requested = page.getByTestId("parking-requested-stalls");
  await requested.fill("500");
  await expect(page.getByTestId("parking-layout-status")).toContainText(/short/i);
  await requested.fill("40");
  await expect(page.getByTestId("parking-layout-status")).toHaveText(/fits/i);
});

test("outdated layout alternatives cannot overwrite newer manual edits", async ({ page }) => {
  await page.route("**/api/**", async route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) }));
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const list = page.getByTestId("object-manager-panel");
  if (!(await list.evaluate(element => element.hasAttribute("open")))) await list.locator("summary").click();
  const row = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await row.getByTestId("object-manager-select").click();
  await row.getByTestId("object-manager-inspect").click();
  const initialX = Number(await page.getByTestId("selected-object-x-input").inputValue());
  await page.getByTestId("parking-dependency-policy").selectOption("follow");
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("show me 5 layout options");
  await page.getByTestId("civora-command-input").press("Enter");
  await expect(page.getByTestId("layout-alternatives-card")).toBeVisible();
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await list.evaluate(element => element.hasAttribute("open")))) await list.locator("summary").click();
  await row.getByTestId("object-manager-inspect").click();
  await page.getByTestId("selected-object-x-input").fill(String(initialX + 7));
  await page.getByTestId("selected-object-x-input").blur();
  await page.getByTestId("layout-alternatives-apply").click();
  await expect(page.getByTestId("layout-alternatives-card")).toHaveCount(0);
  await expect(page.getByTestId("selected-object-status")).toContainText("Generate fresh alternatives");
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialX + 7));
});

test("chat creates five preview-only alternatives and applies only the chosen option", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.goto("/demo/workspace?seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  const buildingRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await buildingRow.getByTestId("object-manager-select").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  const initialX = Number(await page.getByTestId("selected-object-x-input").inputValue());

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("show me 5 layout options that maximize parking and minimize conflicts");
  await page.getByTestId("civora-command-input").press("Enter");
  await expect(page.getByTestId("layout-alternatives-card")).toBeVisible();
  await expect(page.getByTestId("layout-alternatives-card")).toContainText("maximize parking + minimize conflicts");
  await expect(page.getByTestId("layout-alternative-reasons")).toContainText(/parking capacity/i);
  const optionButtons = page.locator('[data-testid^="layout-alternative-layout-alternative-"]');
  await expect(optionButtons).toHaveCount(5);
  await expect(page.getByTestId("layout-search-report")).toContainText(/Searched 32 candidates/);
  await expect(page.getByTestId("layout-priority-maximize_parking")).toHaveAttribute("aria-pressed", "true");
  const previewOptionTestId = await optionButtons.nth(1).getAttribute("data-testid");
  await optionButtons.nth(1).click();
  await page.getByTestId("layout-priority-maximize_parking").click();
  await expect(page.getByTestId("layout-alternatives-card")).toContainText("Ranked for minimize conflicts");
  await expect(page.getByTestId(String(previewOptionTestId))).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("layout-priority-minimize_conflicts")).toBeDisabled();
  await page.getByTestId("layout-priority-building_near_entrance").click();
  await expect(page.getByTestId("layout-alternatives-card")).toContainText("keep buildings near the entrance");
  await page.getByTestId("layout-alternatives-cancel").click();

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue(String(initialX));

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("show me 5 layout options");
  await page.getByTestId("civora-command-input").press("Enter");
  const buildingChangeOption = page.locator('[data-testid^="layout-alternative-layout-alternative-"][data-changed-types*="building"]').first();
  await expect(buildingChangeOption).toBeVisible();
  await buildingChangeOption.click();
  await expect(page.getByTestId("layout-alternative-change-summary")).toContainText(/changed object/i);
  await expect(page.getByTestId("layout-difference-overlay")).toBeVisible();
  await expect(page.getByTestId("layout-difference-item")).not.toHaveCount(0);
  await page.getByTestId("layout-alternatives-apply").click();
  await expect(page.getByTestId("layout-alternatives-card")).toHaveCount(0);

  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  if (!(await objectList.evaluate((element) => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await buildingRow.getByTestId("object-manager-inspect").click();
  await expect.poll(async () => Number(await page.getByTestId("selected-object-x-input").inputValue())).not.toBe(initialX);
  await expect(page.getByTestId("selected-object-status")).toContainText(/working plan.*Undo restores/i);

  const layerMenu = page.getByTestId("preview-layer-menu");
  await layerMenu.locator("summary").click();
  await page.getByTestId("preview-layer-select-roads").click();
  await layerMenu.locator("summary").click();
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  await expect(page.getByTestId("object-manager-selected-count")).toContainText(/Selected [2-9]/);
  await layerMenu.locator("summary").click();
  await page.getByTestId("preview-layer-toggle-roads").click();
  await expect(page.getByTestId("preview-layer-toggle-roads")).toHaveAttribute("aria-pressed", "false");
  await page.getByTestId("preview-layer-show-all").click();
  await expect(page.getByTestId("preview-layer-toggle-roads")).toHaveAttribute("aria-pressed", "true");
});
