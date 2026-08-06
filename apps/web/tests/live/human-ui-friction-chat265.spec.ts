import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&seedDemo=1") {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  return consoleErrors;
}

async function openDrawPanel(page: Page) {
  await page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
}

test.describe("Chat 265 human UI friction repair", () => {
  test("Enter submits sign-in and the support action opens the real support address", async ({ page }) => {
    let loginRequests = 0;
    await page.route("**/api/auth/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, account_setup: "configured" }),
      });
    });
    await page.route("**/api/auth/login", async (route) => {
      loginRequests += 1;
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password." }),
      });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("link", { name: "Email Civora support at support@civora.ai" })).toHaveAttribute(
      "href",
      "mailto:support@civora.ai?subject=Civora%20pilot%20support",
    );
    await page.getByRole("button", { name: "Sign In Mode" }).click();
    await page.getByLabel("Email", { exact: true }).fill("engineer@example.com");
    await page.getByLabel("Password", { exact: true }).fill("incorrect-password");
    await page.getByLabel("Password", { exact: true }).press("Enter");

    await expect.poll(() => loginRequests).toBe(1);
    await expect(page.getByText("Invalid email or password.")).toBeVisible();
  });

  test("Chat has one keyboard and a minimized drawer stays closed until explicitly reopened", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page);

    await page.keyboard.press("/");
    await expect(page.getByTestId("civora-command-input")).toHaveCount(1);
    await page.getByRole("button", { name: "Open Civora chat history" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Command Center/i);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(0);
    await expect(page.getByTestId("civora-chat-input")).toHaveCount(1);

    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await expect(page.getByTestId("civora-chat-input")).toBeFocused();
    await expect(page.getByTestId("civora-command-input")).toHaveCount(0);

    await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Minimize" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await page.waitForTimeout(700);
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);

    await page.getByTestId("header-chat-button").click();
    await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
    expect(consoleErrors).toEqual([]);
  });

  test("Select exits Line mode without adding a point and layer controls visibly change the canvas", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page);
    await openDrawPanel(page);

    await page.getByTestId("cad-tool-line").filter({ visible: true }).first().click();
    const drawingSurface = page.getByTestId("preview-drawing-surface").filter({ visible: true }).first();
    await expect(drawingSurface).toHaveAttribute("data-draw-mode", "polyline");

    const selectTool = page.getByRole("button", { name: "Select and edit objects" });
    await expect(selectTool).toBeVisible();
    await selectTool.click();
    await expect(selectTool).toHaveAttribute("aria-pressed", "true");
    await expect(drawingSurface).toHaveAttribute("data-draw-mode", "select");
    await expect(drawingSurface).toHaveAttribute("data-draft-point-count", "0");

    const objectCountBefore = await page.locator("[data-object-overlay]").count();
    const canvas = page.getByTestId("workspace-canvas-shell");
    const bounds = await canvas.boundingBox();
    expect(bounds).not.toBeNull();
    await page.mouse.click(bounds!.x + bounds!.width * 0.52, bounds!.y + bounds!.height * 0.55);
    await expect(drawingSurface).toHaveAttribute("data-draft-point-count", "0");
    expect(await page.locator("[data-object-overlay]").count()).toBe(objectCountBefore);

    await page.getByTestId("preview-layer-menu").locator("summary").click();
    const existingLayer = page.getByTestId("preview-source-layer-existing");
    await expect(existingLayer).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("preview-layer-visibility-summary")).toContainText("Existing context is shown");
    await existingLayer.click();
    await expect(existingLayer).toHaveAttribute("aria-pressed", "false");
    await expect(existingLayer).toContainText("Hidden");
    await expect(page.getByTestId("preview-layer-visibility-summary")).toContainText("Existing context is hidden");
    await existingLayer.click();
    await expect(existingLayer).toContainText("Shown");
    expect(consoleErrors).toEqual([]);
  });

  test("Select never pans the real map and Pan moves map-aligned geometry", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&mapDebug=1&seedDemo=1");
    const mapToggle = page.getByTestId("preview-inner-map-toggle");
    test.skip(await mapToggle.isDisabled(), "This environment has no configured map token.");
    if ((await mapToggle.textContent())?.includes("Off")) await mapToggle.click();
    await expect(page.locator("canvas.mapboxgl-canvas").first()).toBeVisible({ timeout: 30_000 });
    await openDrawPanel(page);

    const trackedObject = page.locator("[data-object-overlay]").filter({ visible: true }).first();
    await expect(trackedObject).toBeVisible();
    const emptyCanvasPoint = await page.locator("canvas.mapboxgl-canvas").first().evaluate((element) => {
      const rect = element.getBoundingClientRect();
      for (const xRatio of [0.82, 0.68, 0.5, 0.32, 0.18]) {
        for (const yRatio of [0.82, 0.68, 0.5, 0.32, 0.18]) {
          const x = rect.left + rect.width * xRatio;
          const y = rect.top + rect.height * yRatio;
          const blocked = document.elementsFromPoint(x, y).some((hit) =>
            hit.closest("button,input,textarea,select,aside,header,[data-object-overlay],[data-no-window-select]"),
          );
          if (!blocked) return { x, y };
        }
      }
      return { x: rect.left + rect.width * 0.75, y: rect.top + rect.height * 0.75 };
    });
    await page.getByRole("button", { name: "Select and edit objects" }).click();
    await expect(page.getByTestId("preview-drawing-surface").first()).toHaveAttribute("data-draw-mode", "select");
    const beforeSelectDrag = await trackedObject.boundingBox();
    expect(beforeSelectDrag).not.toBeNull();
    const beforeSelectViewport = await page.evaluate(() => {
      const value = (window as unknown as Record<string, unknown>).__civoraMapViewport;
      return value as { lat: number; lng: number; zoom: number } | null;
    });
    expect(beforeSelectViewport).not.toBeNull();
    await page.mouse.move(emptyCanvasPoint.x, emptyCanvasPoint.y);
    await page.mouse.down();
    await page.mouse.move(emptyCanvasPoint.x + 28, emptyCanvasPoint.y + 12, { steps: 4 });
    await page.mouse.up();
    const afterSelectDrag = await trackedObject.boundingBox();
    expect(afterSelectDrag).not.toBeNull();
    expect(Math.abs(afterSelectDrag!.x - beforeSelectDrag!.x)).toBeLessThan(2);
    expect(Math.abs(afterSelectDrag!.y - beforeSelectDrag!.y)).toBeLessThan(2);
    const afterSelectViewport = await page.evaluate(() => {
      const value = (window as unknown as Record<string, unknown>).__civoraMapViewport;
      return value as { lat: number; lng: number; zoom: number } | null;
    });
    expect(afterSelectViewport).not.toBeNull();
    expect(afterSelectViewport!.lat).toBeCloseTo(beforeSelectViewport!.lat, 8);
    expect(afterSelectViewport!.lng).toBeCloseTo(beforeSelectViewport!.lng, 8);
    expect(afterSelectViewport!.zoom).toBeCloseTo(beforeSelectViewport!.zoom, 8);

    await page.getByTestId("cad-tool-pan").filter({ visible: true }).first().click();
    await expect(page.getByTestId("preview-drawing-surface").first()).toHaveAttribute("data-draw-mode", "pan");
    await expect(page.getByTestId("canvas-quick-finish").filter({ visible: true })).toHaveCount(0);
    await expect(page.getByTestId("canvas-quick-cancel").filter({ visible: true })).toHaveCount(0);
    await page.mouse.move(emptyCanvasPoint.x, emptyCanvasPoint.y);
    await page.mouse.down();
    await page.mouse.move(emptyCanvasPoint.x + 110, emptyCanvasPoint.y + 35, { steps: 8 });
    await page.mouse.up();
    await expect.poll(async () => {
      const moved = await trackedObject.boundingBox();
      if (!moved) return 0;
      return Math.hypot(moved.x - afterSelectDrag!.x, moved.y - afterSelectDrag!.y);
    }).toBeGreaterThan(8);
    await expect.poll(async () => {
      const viewport = await page.evaluate(() => {
        const value = (window as unknown as Record<string, unknown>).__civoraMapViewport;
        return value as { lat: number; lng: number } | null;
      });
      if (!viewport) return 0;
      return Math.hypot(
        viewport.lat - afterSelectViewport!.lat,
        viewport.lng - afterSelectViewport!.lng,
      );
    }).toBeGreaterThan(0.000001);
  });

  test("an editable site reads as a normal state instead of an error", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&seedDemo=0");
    await expect(page.getByTestId("site-status")).toContainText("Site Editable");
    await expect(page.locator("body")).not.toContainText("Site not locked");
    await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
    const siteSection = page.getByTestId("setup-site-box-controls");
    await expect(siteSection).not.toContainText(/No boundary locked|Needs lock/i);
    await expect(siteSection).toContainText(/Editable|Add boundary/i);

    await expect(siteSection.getByRole("button", { name: "Enter Size First" })).toBeDisabled();
    await siteSection.getByRole("button", { name: "Use 1000 ft x 1000 ft" }).click();
    await expect(siteSection.getByRole("button", { name: "Lock Boundary" })).toBeEnabled();
    await siteSection.getByRole("button", { name: "Lock Boundary" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await page.waitForTimeout(700);
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
  });
});
