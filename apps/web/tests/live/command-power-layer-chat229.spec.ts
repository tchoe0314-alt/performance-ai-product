import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock", options?: { requireLockedSite?: boolean }) {
  const params = new URLSearchParams(query);
  if (!params.has("seedDemo")) {
    params.set("seedDemo", "1");
  }
  const consoleErrors: string[] = [];
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/demo/workspace?${params.toString()}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  if (options?.requireLockedSite !== false) {
    await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  }
  return consoleErrors;
}

async function focusCommand(page: Page) {
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByTestId("civora-command-input")).toBeFocused({ timeout: 5_000 });
}

async function runCommand(page: Page, command: string) {
  await focusCommand(page);
  await page.getByTestId("civora-command-input").fill(command);
  await page.getByTestId("civora-command-input").press("Enter");
}

async function openDrawPanel(page: Page) {
  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Objects|Tools/, { timeout: 5_000 });
}

test.describe("Chat 229 command power layer and shortcuts", () => {
  test("keeps one command surface and focuses it with shortcuts", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page);

    await expect(page.getByTestId("floating-command-bar")).toHaveCount(0);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(0);

    await page.keyboard.press("/");
    await expect(page.getByTestId("floating-command-bar")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toBeFocused();
    await expect(page.getByTestId("command-context-chips")).toContainText(/Mode/i);
    await expect(page.getByTestId("command-context-chips")).toContainText(/Layer/i);
    await expect(page.getByTestId("command-context-chips")).toContainText(/View/i);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("civora-command-input")).not.toBeFocused();
    await page.keyboard.press("G");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);

    await page.locator("body").click({ position: { x: 20, y: 20 } });
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcuts-help-overlay")).toBeVisible();
    await expect(page.getByTestId("shortcuts-help-overlay")).toContainText("Cmd/Ctrl S");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("shortcuts-help-overlay")).toHaveCount(0);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(consoleErrors).toEqual([]);
  });

  test("commands create real pending office and parking objects", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add 28000 sf office building");
    await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 5_000 });

    await runCommand(page, "add 140 parking spaces");
    await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 140 stalls"]').first()).toBeVisible({ timeout: 5_000 });

    await openDrawPanel(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Parking Field - 140 stalls");
  });

  test("natural comma-formatted office project wording creates the requested footprint", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock&seedDemo=0", { requireLockedSite: false });

    await runCommand(page, "Set the site to 1000 ft by 1000 ft with 20525 Margo St Gretna NE as the center point");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Site Locked/i, { timeout: 8_000 });

    await runCommand(
      page,
      "make this a 28,000 sf office project with 140 parking stalls, a detention basin, driveway, sidewalks, public water, sanitary, and storm sewer",
    );

    await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 8_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 140 stalls"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Basin / Detention"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Storm Sewer"]').first()).toBeVisible();
    await expect(page.getByText(/Added and placed 28,000 sf office building/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("messy site-program wording preserves quantities and common drafting typos", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock&seedDemo=0", { requireLockedSite: false });

    await runCommand(page, "Set the site to 720 ft by 520 ft with 1600 Dodge St Omaha NE as the center point");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Site Locked/i, { timeout: 8_000 });

    await runCommand(
      page,
      "put in a 32,000 sqft office, 165 parking spots, a detention pond, drveway, storm sewer, water, sanitary, and ADA walks",
    );

    await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 32,000 sf"]').first()).toBeVisible({ timeout: 8_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 165 stalls"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Basin / Detention"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Driveway"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Sidewalk / ADA Route"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Public Water Line"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Public Sanitary Line"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Storm Sewer"]').first()).toBeVisible();
    await expect(page.getByText(/32,000 sf office building, 165 parking stalls/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("natural grading and drainage context commands create editable review geometry", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add grading and drainage context");

    await expect(page.locator('[data-cad-object-id][aria-label*="Review Grading Fall Line"]').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Review Drainage Area Cue"]').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/editable review context/i).first()).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/not survey\/control evidence/i);

    await page.getByRole("button", { name: /^Generate$/ }).first().click();
    await expect(page.getByTestId("generate-current-drawing-context")).toContainText("Review Grading Fall Line");
    await expect(page.getByTestId("generate-current-drawing-context")).toContainText("Review Drainage Area Cue");
    await expect(page.getByTestId("generate-current-drawing-context")).toContainText(/grading, drainage|drainage, grading/);
    await page.getByTestId("generate-drainage").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Using from drawing/i);
    await expect(page.getByTestId("generate-flow-summary")).toContainText("Review Drainage Area Cue");

    await openDrawPanel(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Review Grading Fall Line");
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Review Drainage Area Cue");
  });

  test("chat explains preview marks like a human instead of leaving mystery geometry", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add detention basin");
    await runCommand(page, "add water line");
    await runCommand(page, "what are these random circles and lines?");

    await expect(page.getByText("Civora: The preview is a review canvas", { exact: false }).first()).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    const panel = page.getByTestId("workspace-right-panel");
    await expect(panel).toContainText("The preview is a review canvas", { timeout: 5_000 });
    await expect(panel).toContainText("Lines are usually roads, driveways, sidewalks, utilities, or draft linework");
    await expect(panel).toContainText("Circles/points are usually hydrants, inlets, outfalls, manholes, or point markers");
    await expect(panel).toContainText("Object Manager");
    await expect(panel).not.toContainText(/construction-ready|approved for construction/i);

    const chatInput = page.getByRole("textbox", {
      name: "Message Civora AI with what you want to create or change...",
    });
    await chatInput.focus();
    await expect(chatInput).toBeFocused();
    await runCommand(page, "what am I looking at?");
    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    await expect(panel).toContainText("The preview is a review canvas", { timeout: 5_000 });
    await expect(panel).toContainText(/select, rename, hide, recolor, or delete|rename, change type\/color/i);
    await expect(panel).not.toContainText("Opened the 3D civil model workspace");
  });

  test("chat explains how to draw, finish, and cancel without generic clarification", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "how do I finish drawing a boundary?");

    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    const panel = page.getByTestId("workspace-right-panel");
    await expect(panel).toContainText("Draw Canvas works like this", { timeout: 5_000 });
    await expect(panel).toContainText("Draw Site Boundary");
    await expect(panel).toContainText("Press Finish to commit");
    await expect(panel).toContainText("Press Cancel or Escape");
    await expect(panel).toContainText("Object Manager");
    await expect(panel).not.toContainText(/Before I move forward, I still need|site type or land use/i);
  });

  test("state questions tolerate ordinary spelling and grammar mistakes", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "whats changeed?");
    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    const panel = page.getByTestId("workspace-right-panel");
    await expect(panel).toContainText(/What changed|Changed\/stale systems|Last Generate|No stale generated systems|Project status/i, { timeout: 5_000 });
    await expect(panel).not.toContainText(/Before I move forward, I still need|site type or land use/i);
  });

  test("chat explains recent UI performance timings instead of guessing about lag", async ({ page }) => {
    await openDemoWorkspace(page);

    await page.evaluate(() => {
      (window as typeof window & {
        __civoraPerf?: {
          entries: Array<{ label: string; durationMs: number; startedAt?: number; endedAt?: number }>;
          last: Record<string, { label: string; durationMs: number; startedAt?: number; endedAt?: number }>;
        };
      }).__civoraPerf = {
        entries: [
          { label: "preview.quality.high", durationMs: 64 },
          { label: "preview.mode.3d", durationMs: 1240 },
          { label: "projects.new_project", durationMs: 180 },
        ],
        last: {
          "preview.quality.high": { label: "preview.quality.high", durationMs: 64 },
          "preview.mode.3d": { label: "preview.mode.3d", durationMs: 1240 },
          "projects.new_project": { label: "projects.new_project", durationMs: 180 },
        },
      };
    });

    await runCommand(page, "why is the website laggy?");

    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    const panel = page.getByTestId("workspace-right-panel");
    await expect(panel).toContainText("Recent UI timings from this browser", { timeout: 5_000 });
    await expect(panel).toContainText("Preview mode 3d");
    await expect(panel).toContainText("slow, worth checking");
    await expect(panel).toContainText("Preview quality high");
    await expect(panel).toContainText("instant");
    await expect(panel).not.toContainText(/Before I move forward, I still need|site type or land use/i);
  });

  test("natural language address and site size setup bypasses generic design clarification", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock&seedDemo=0", { requireLockedSite: false });

    await runCommand(
      page,
      "I want the address to be 20525 Margo St gretna ne and its gonna be 1000ft by 1000 ft with the address to be the center point",
    );

    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Site Locked/i, { timeout: 8_000 });
    await page.getByRole("button", { name: "Setup" }).first().click();
    await expect(page.getByTestId("setup-site-box-controls")).toContainText("1000 ft x 1000 ft");
    await expect(page.getByTestId("setup-address-truth")).toContainText(/20525 Margo St/i);
    await expect(page.getByTestId("setup-address-truth")).toContainText(/Local|Applied/i);
    await expect(page.getByTestId("setup-address-truth")).not.toContainText(/Needs apply/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/site type or land use/i);
  });

  test("site size first with address center wording locks the site", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock&seedDemo=0", { requireLockedSite: false });

    await runCommand(
      page,
      "Set the site to 1000 ft by 1000 ft with 20525 Margo St Gretna NE as the center point",
    );

    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Site Locked/i, { timeout: 8_000 });
    await page.getByRole("button", { name: "Setup" }).first().click();
    await expect(page.getByTestId("setup-site-box-controls")).toContainText("1000 ft x 1000 ft");
    await expect(page.getByTestId("setup-address-truth")).toContainText(/20525 Margo St/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/site type or land use/i);
  });

  test("one messy command can set site and place a draft site program", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock&seedDemo=0", { requireLockedSite: false });

    await runCommand(
      page,
      "20525 Margo St Gretna NE should be the center point, make it 1000 ft by 1000 ft with a 28000 sf office building, 140 parking spaces, detention basin, driveway, sidewalks, public water, sanitary, and storm sewer",
    );

    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Site Locked/i, { timeout: 8_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 8_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Detention Basin"]').first()).toBeVisible();
    await expect(page.locator('[data-cad-object-id][aria-label*="Public Water Line"]').first()).toBeVisible();

    await page.getByRole("button", { name: "Setup" }).first().click();
    await expect(page.getByTestId("setup-site-box-controls")).toContainText("1000 ft x 1000 ft");
    await expect(page.getByTestId("setup-address-truth")).toContainText(/20525 Margo St/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/site type or land use|which systems/i);

    await openDrawPanel(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Storm Sewer");
  });

  test("explicitly reuses drawn objects without creating a duplicate program", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const beforeRows = await page.getByTestId("object-manager-row").allTextContents();
    expect(beforeRows.length).toBeGreaterThan(5);

    await runCommand(
      page,
      "Use this locked 1000 ft by 1000 ft site at 20525 Margo St for a 28,000 SF office with 140 parking spaces, detention, public water, public sanitary, storm sewer, a driveway, sidewalks, and ADA access. Keep the objects already drawn and do not create duplicates.",
    );

    await expect(page.getByText(/kept \d+ existing drawn objects/i).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/did not create duplicate concept geometry/i).first()).toBeVisible();
    await expect(page.getByText(/140-space parking target/i).first()).toBeVisible();
    await expect(page.getByText(/site at site at/i)).toHaveCount(0);

    await page.getByRole("button", { name: "Setup" }).first().click();
    await expect(page.getByTestId("setup-address-truth")).toContainText(/20525 Margo St/i);
    await expect(page.getByTestId("setup-address-truth")).not.toContainText(/for a 28,000|objects already drawn/i);

    await openDrawPanel(page);
    const afterRows = await page.getByTestId("object-manager-row").allTextContents();
    expect(afterRows.slice(1)).toEqual(beforeRows.slice(1));
    expect(afterRows[0]).toContain("1000 ft x 1000 ft");
  });

  test("commands open generate, deliver, blocker view, layers, and AI realism mode", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "hide utilities");
    await expect(page.getByText("Utility and drainage layers are hidden in the preview.").first()).toBeVisible();

    await runCommand(page, "show only blockers");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Review|Issue|blocker/i);

    await runCommand(page, "generate");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);

    await runCommand(page, "make review package");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Review package|Plan Sheets|Deliver/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/construction-ready|approved for construction/i);

    await runCommand(page, "create AI realism");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("High Quality", { timeout: 5_000 });
    await expect(page.getByTestId("ai-realism-toggle").first()).toBeVisible();

    await runCommand(page, "turn AI realism off");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Standard", { timeout: 5_000 });
  });

  test("shortcuts open panels, cancel tools, delete selected objects, save truthfully, and refuse unsafe commands", async ({ page }) => {
    await openDemoWorkspace(page);

    await page.keyboard.press("G");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);
    await page.keyboard.press("D");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Objects|Tools/i);
    await page.keyboard.press("P");
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("projects-drawer")).toHaveCount(0);

    await runCommand(page, "draw site boundary");
    await expect(page.getByTestId("draw-active-tool")).toContainText(/site/i);
    await expect(page.getByTestId("canvas-quick-finish")).toBeVisible();
    await expect(page.getByTestId("canvas-quick-cancel")).toBeVisible();

    await runCommand(page, "add 28000 sf office building");
    const officeOverlay = page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first();
    await expect(officeOverlay).toBeVisible({ timeout: 5_000 });
    await officeOverlay.click();
    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    });
    await expect(page.getByText(/Deleted Office Building - 28,000 sf|DELETE removed Office Building - 28,000 sf/i).first()).toBeVisible({ timeout: 5_000 });

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, ctrlKey: true, bubbles: true }));
    });
    await expect(page.getByText(/Undo: restored Office Building - 28,000 sf/).first()).toBeVisible();

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "s", metaKey: true, ctrlKey: true, bubbles: true }));
    });
    await expect(page.getByText(/Demo workspace changes stay local|Sign in\/connect backend to save projects|Saved project/).first()).toBeVisible();

    await runCommand(page, "stamp this");
    await expect(page.getByText(/can't stamp, seal, sign, certify/i).first()).toBeVisible();
    await runCommand(page, "act as engineer of record");
    await expect(page.getByText(/can't stamp, seal, sign, certify/i).first()).toBeVisible();

    await page.locator("body").click({ position: { x: 20, y: 20 } });
    await page.keyboard.press("G");
    const generatePanel = page.getByTestId("workspace-right-panel");
    await expect(generatePanel).toContainText(/Generate Systems/i);
    await expect(generatePanel).not.toContainText(/Command refused|Construction authorization refused/i);
  });
});
