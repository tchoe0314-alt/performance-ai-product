import { expect, test, type Page } from "@playwright/test";

async function runChatCommand(page: Page, command: string) {
  await page.getByRole("button", { name: "Chat" }).first().click();
  const input = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await input.fill(command);
  await input.press("Enter");
}

test("creates a dense editable civil concept from a fresh project", async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await runChatCommand(
    page,
    "I want the address to be 20525 Margo St Gretna NE and it is gonna be 1000ft by 1000 ft with the address as the center point",
  );
  await expect(page.getByText("SITE LOCKED").first()).toBeVisible({ timeout: 30_000 });

  await runChatCommand(
    page,
    "create a dense professional civil site plan with a 28000 sf office building, 140 parking spaces, detention basin, driveway, sidewalks, public water, public sanitary, and storm drainage utilities",
  );

  const canvas = page.getByTestId("workspace-canvas-shell");
  await expect(canvas).toContainText(/site locked/i, { timeout: 10_000 });
  await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 84 stalls"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 56 stalls"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Detention Basin A"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Internal Loop Drive"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Public Frontage Road"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Rear Service Drive"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Public Water Line"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Public Sanitary Line"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Storm Sewer"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Office Water Service Lateral"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Office Sanitary Lateral"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Outfall OF-1"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Frontage Landscape Buffer"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Contour 1025"]').first()).toBeVisible();

  await canvas.getByTestId("preview-quality-high").click();
  await expect(page.getByTestId("professional-building-footprint").first()).toBeVisible();
  await expect(page.getByTestId("plan-building-entry-cues").first()).toBeVisible();
  await expect(page.getByTestId("professional-parking-field").first()).toBeVisible();
  await expect(page.getByTestId("professional-basin-footprint").first()).toBeVisible();
  await expect(page.getByTestId("plan-road-corridor").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-stall-cues").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-module-detail").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-ada-symbol").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-ada-aisle").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-compact-symbol").first()).toBeVisible();
  await expect(page.getByTestId("plan-parking-aisle-cue").first()).toBeVisible();
  await expect(page.getByTestId("plan-landscape-contour-cues").first()).toBeVisible();
  await expect(page.getByTestId("plan-grading-contour-cues").first()).toBeVisible();
  await expect(page.getByTestId("plan-road-tie-ticks").first()).toBeVisible();
  await expect(page.getByTestId("plan-utility-pipe-halo")).toHaveCount(0);
  await expect(page.getByTestId("survey-base-plan-frame").first()).toBeVisible();
  await expect(page.getByTestId("plan-grading-context-lines")).toHaveCount(0);
  await expect(page.getByTestId("survey-boundary-annotation")).toHaveCount(0);
  await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(0);
  await expect(page.getByTestId("survey-utility-callout")).toHaveCount(0);
  await page.locator('[data-cad-object-hit-id][aria-label*="Public Water Line"]').first().click();
  await expect(page.getByTestId("plan-utility-pipe-halo").first()).toBeVisible();
  await expect(page.getByTestId("survey-utility-callout").first()).toBeVisible();
  await expect(canvas).toContainText(/concept plan/i);
  await expect(canvas).toContainText(/no survey \/ topo source/i);

  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  const objectPanel = page.getByTestId("object-manager-panel");
  await expect(objectPanel).toContainText("Office Building - 28,000 sf");
  await expect(objectPanel).toContainText("Parking Field - 84 stalls");
  await expect(objectPanel).toContainText("Parking Field - 56 stalls");
  await expect(objectPanel).toContainText("Detention Basin A");
  await expect(objectPanel).toContainText("Public Water Line");
  await expect(objectPanel).toContainText("Storm Sewer");

  const bodyText = await canvas.innerText();
  expect(bodyText).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => !message.includes("401") && !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
});

test("understands recreate-the-image wording without a prebuilt site", async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await runChatCommand(
    page,
    "literally recreate the image I sent you as a dense civil site plan with as many real plan elements and stuff as possible",
  );

  const canvas = page.getByTestId("workspace-canvas-shell");
  await expect(canvas).toContainText(/site locked/i, { timeout: 10_000 });
  await expect(canvas).toContainText(/1200 FT x 820 FT/i);
  await expect(page.locator('[data-cad-object-id][aria-label*="B1-1"]').first()).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('[data-cad-object-id][aria-label*="Central Loop Road"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Central Amenity Green"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="North Blue Hatched Parking"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Red Feature Court A"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Contour 710"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Water Main Loop"]').first()).toBeVisible();

  await expect(page.locator("body")).toContainText(/Dense subdivision review plan created/i);
  await expect(page.locator("body")).not.toContainText(/site type or land use|which systems to include/i);

  const actionStrip = page.getByTestId("dense-concept-action-strip");
  await expect(actionStrip).toHaveCount(0);

  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  const objectPanel = page.getByTestId("object-manager-panel");
  await expect(objectPanel).toContainText("Central Loop Road");
  await expect(objectPanel).toContainText("Contour 710");
  await expect(objectPanel).toContainText("Water Main Loop");
  await expect(objectPanel).toContainText("B1-1");

  await canvas.getByTestId("preview-quality-high").click();
  await expect(page.getByTestId("plan-road-corridor").first()).toBeVisible();
  await expect(page.getByTestId("survey-base-plan-frame").first()).toBeVisible();

  const bodyText = await canvas.innerText();
  expect(bodyText).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => !message.includes("401") && !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
});

test("creates an urbanization campus plan with colored sheet objects and 3D massing", async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await runChatCommand(
    page,
    "make an urbanization campus master plan like this with boulevard roads, parcel rows, civic buildings, plaza, park, trees, parking courts, utilities, and a 3d massing model",
  );

  const canvas = page.getByTestId("workspace-canvas-shell");
  await expect(canvas).toContainText(/1120 FT x 720 FT/i, { timeout: 10_000 });
  await expect(page.locator('[data-cad-object-id][aria-label*="Civic Hall"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Central Plaza"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Municipal Park"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Boulevard Lambramani"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Cyan Water Service Network"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Tree 1"]').first()).toBeVisible();
  await expect(page.locator("body")).toContainText(/Urbanization\/campus review model created/i);
  await expect(page.locator("body")).not.toContainText(/site type or land use|which systems to include/i);

  await canvas.getByTestId("preview-quality-high").click();
  await expect(canvas).toContainText(/Plan Sheet/i);
  await expect(page.getByTestId("professional-building-footprint").first()).toBeVisible();
  await expect(page.getByTestId("plan-building-entry-cues").first()).toBeVisible();
  await expect(page.getByTestId("plan-road-edge-lines").first()).toBeVisible();
  await expect(page.getByTestId("plan-tree-symbol").first()).toBeVisible();
  await expect(page.getByTestId("plan-plaza-module-lines").first()).toBeVisible();
  await expect(page.getByTestId("plan-utility-node-cues")).toHaveCount(0);
  await page.locator('[data-cad-object-hit-id][aria-label*="Cyan Water Service Network"]').first().click();
  await expect(page.getByTestId("plan-utility-node-cues").first()).toBeVisible();
  await expect(page.getByTestId("plan-landscape-contour-cues").first()).toBeVisible();
  await expect(page.locator('svg [data-semantic-layer="lots"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][data-semantic-layer="lots"]').first()).toBeVisible();
  await page.getByTestId("preview-layer-toggle-lots").click();
  await expect(page.locator('svg [data-semantic-layer="lots"]')).toHaveCount(0);
  await expect(page.locator('[data-cad-object-id][data-semantic-layer="lots"]')).toHaveCount(0);
  await expect(page.locator('[data-cad-object-id][aria-label*="Civic Hall"]').first()).toBeVisible();
  await page.getByTestId("preview-layer-show-all").click();
  await expect(page.locator('svg [data-semantic-layer="lots"]').first()).toBeVisible();
  await page.getByTestId("preview-mode-3d").click();
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("civil-3d-terrain-state")).toContainText(/review contour surface/i);
  await expect(page.getByTestId("civil-3d-massing-summary")).toContainText(/3D massing:/i);
  await expect(page.getByTestId("civil-3d-massing-summary")).toContainText(/detailed buildings/i);
  const massingText = await page.getByTestId("civil-3d-massing-summary").innerText();
  const verticalCount = Number(massingText.match(/(\d+)\s+vertical/i)?.[1] ?? 0);
  expect(verticalCount).toBeGreaterThan(8);
  await expect(page.getByTestId("civil-3d-object-strip")).toContainText(/Civic Hall|Library|Market Hall/i, { timeout: 20_000 });

  const bodyText = await canvas.innerText();
  expect(bodyText).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => !message.includes("401") && !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
});
