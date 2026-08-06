import { expect, test, type Locator, type Page } from "@playwright/test";

test.use({ video: "on", screenshot: "on" });

const ignoredRuntimeNoise = /favicon|ERR_CONNECTION_REFUSED|401|api\/auth|api\/orchestrate/i;

async function openFreshProject(page: Page) {
  await page.goto(`/demo/workspace?debugPreview=1&seedDemo=0&hostile=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Projects" }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
  await page.getByRole("button", { name: "New Project" }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("site-status")).toContainText("Site Open");
}

async function openPanel(page: Page, name: RegExp | string) {
  const showSidebar = page.getByRole("button", { name: "Show left sidebar" });
  if (await showSidebar.isVisible().catch(() => false)) {
    await showSidebar.click();
  }
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
}

async function openAllDraftToolGroups(page: Page) {
  const tools = page.getByTestId("draw-cad-tools-section");
  const summaries = tools.locator("details > summary");
  for (let index = 0; index < (await summaries.count()); index += 1) {
    const summary = summaries.nth(index);
    const details = summary.locator("xpath=parent::details");
    if (!(await details.evaluate((element) => (element as HTMLDetailsElement).open))) {
      await summary.click();
    }
  }
}

async function clickSurface(surface: Locator, xRatio: number, yRatio: number) {
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const x = rect.left + rect.width * ratios.xRatio;
      const y = rect.top + rect.height * ratios.yRatio;
      return { x, y };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

function collectRuntimeFailures(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`);
  });
  return {
    assertClean() {
      expect(pageErrors).toEqual([]);
      expect(consoleErrors.filter((line) => !ignoredRuntimeNoise.test(line))).toEqual([]);
      expect(failedRequests.filter((line) => !ignoredRuntimeNoise.test(line))).toEqual([]);
    },
  };
}

async function expectNoUnreachableVisibleButtons(page: Page) {
  const issues = await page.locator("button:visible").evaluateAll((buttons) =>
    buttons.flatMap((button, index) => {
      const element = button as HTMLButtonElement;
      const rect = element.getBoundingClientRect();
      const fullyInViewport =
        rect.left >= 0 &&
        rect.top >= 0 &&
        rect.right <= window.innerWidth &&
        rect.bottom <= window.innerHeight;
      if (!fullyInViewport) return [];
      const name = element.getAttribute("aria-label")?.trim() || element.innerText.trim() || element.title.trim();
      const style = window.getComputedStyle(element);
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      let clippingAncestor = element.parentElement;
      let centerInsideClippingAncestors = true;
      while (clippingAncestor) {
        const ancestorStyle = window.getComputedStyle(clippingAncestor);
        const clipsX = /auto|scroll|hidden|clip/.test(ancestorStyle.overflowX);
        const clipsY = /auto|scroll|hidden|clip/.test(ancestorStyle.overflowY);
        if (clipsX || clipsY) {
          const ancestorRect = clippingAncestor.getBoundingClientRect();
          if (
            (clipsX && (centerX < ancestorRect.left || centerX > ancestorRect.right)) ||
            (clipsY && (centerY < ancestorRect.top || centerY > ancestorRect.bottom))
          ) {
            centerInsideClippingAncestors = false;
            break;
          }
        }
        clippingAncestor = clippingAncestor.parentElement;
      }
      if (!centerInsideClippingAncestors) return [];
      const center = document.elementFromPoint(centerX, centerY);
      const centerReachesButton = center === element || Boolean(center && element.contains(center));
      const failures = [];
      if (!name) failures.push("missing accessible name");
      if (rect.width < 20 || rect.height < 20) failures.push(`tiny target ${Math.round(rect.width)}x${Math.round(rect.height)}`);
      if (!element.disabled && style.pointerEvents === "none") failures.push("pointer-events none");
      if (!element.disabled && !centerReachesButton) {
        failures.push(`center intercepted by ${center?.tagName.toLowerCase() ?? "nothing"}`);
      }
      return failures.length ? [{ index, name: name || "unnamed", failures }] : [];
    }),
  );
  expect(issues, JSON.stringify(issues, null, 2)).toEqual([]);
}

test.describe("hostile-use UI recovery", () => {
  test("wrong-order primary actions explain recovery and never crash", async ({ page }) => {
    const runtime = collectRuntimeFailures(page);
    await openFreshProject(page);

    await openPanel(page, /^Generate$/);
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/needs.*site|site boundary|locked site/i);

    await openPanel(page, /^Deliver$/);
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/needs input|missing|generate|site/i);

    await openPanel(page, /^Draw$/);
    const tools = page.getByTestId("draw-cad-tools-section");
    await openAllDraftToolGroups(page);
    for (const tool of ["move", "rotate", "scale", "delete", "undo", "redo"]) {
      const control = tools.getByTestId(`cad-tool-${tool}`).filter({ visible: true }).first();
      await control.click();
      await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/needs input|blocked|no.*selected|nothing to|select/i);
    }

    await page.keyboard.press("Escape");
    await page.keyboard.press("Delete");
    await page.keyboard.press("Control+Z");
    await page.keyboard.press("Control+S");
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

    await expectNoUnreachableVisibleButtons(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    runtime.assertClean();
  });

  test("unfinished boundary drawing stays reversible with Finish, Cancel, and Escape", async ({ page }) => {
    const runtime = collectRuntimeFailures(page);
    await openFreshProject(page);
    await openPanel(page, /^Setup$/);
    await page
      .getByRole("button", { name: "Start a blank site from detailed setup controls and clear address map evidence" })
      .click();

    const surface = page.getByTestId("preview-drawing-surface");
    const finish = page.getByRole("button", { name: "Finish", exact: true }).filter({ visible: true }).first();
    const cancel = page.getByRole("button", { name: "Cancel", exact: true }).filter({ visible: true }).first();
    await expect(finish).toBeDisabled();
    await clickSurface(surface, 0.3, 0.42);
    await expect(finish).toBeDisabled();
    await clickSurface(surface, 0.66, 0.42);
    await expect(finish).toBeDisabled();
    await cancel.click();
    await expect(page.getByRole("button", { name: "Finish", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("site-status")).toContainText("Site Open");

    await openPanel(page, /^Setup$/);
    await page
      .getByRole("button", { name: "Start a blank site from detailed setup controls and clear address map evidence" })
      .click();
    await clickSurface(surface, 0.4, 0.5);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Finish", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("site-status")).toContainText("Site Open");
    runtime.assertClean();
  });

  test("rapid panel and preview switching remains singular, responsive, and aligned", async ({ page }) => {
    const runtime = collectRuntimeFailures(page);
    await openFreshProject(page);
    await openPanel(page, /^Setup$/);

    const widths = page.getByLabel("Site width in feet");
    const depths = page.getByLabel("Site depth in feet");
    await widths.fill("-10");
    await depths.fill("0");
    await page.getByRole("button", { name: "Lock Boundary" }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText("Apply site needs size");
    await expect(page.getByTestId("site-status")).toContainText("Site Open");
    await widths.fill("300");
    await depths.fill("300");
    await page.getByRole("button", { name: "Lock Boundary" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 20_000 });

    const started = Date.now();
    for (let pass = 0; pass < 3; pass += 1) {
      for (const panel of [/^Setup$/, /^Draw$/, /^Generate$/, /^Deliver$/]) {
        await openPanel(page, panel);
      }
      await page.getByRole("button", { name: "Hide left sidebar" }).click();
      await page.getByRole("button", { name: "Show left sidebar" }).click();
    }
    expect(Date.now() - started).toBeLessThan(12_000);
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(1);
    await expect(page.getByTestId("generate-main-action")).toHaveCount(0);

    const mode3d = page.getByTestId("preview-mode-3d").filter({ visible: true }).first();
    const mode2d = page.getByTestId("preview-mode-2d").filter({ visible: true }).first();
    const qualityHigh = page.getByTestId("preview-quality-high").filter({ visible: true }).first();
    const qualityStandard = page.getByTestId("preview-quality-standard").filter({ visible: true }).first();
    for (let pass = 0; pass < 2; pass += 1) {
      await qualityHigh.click();
      await qualityStandard.click();
      await mode3d.click();
      await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 30_000 });
      await mode2d.click();
      await expect(page.getByTestId("preview-drawing-surface")).toBeVisible();
    }

    await expectNoUnreachableVisibleButtons(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    runtime.assertClean();
  });
});
