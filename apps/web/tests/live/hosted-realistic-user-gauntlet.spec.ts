import { expect, test, type Page, type TestInfo } from "@playwright/test";

test.use({ video: "on", screenshot: "on" });

const ignoredBrowserNoise = /401|unauthorized|auth\/status|favicon|rate limit|too many requests/i;
const unsafeClaims = /construction-ready|approved for construction|stamped by Civora|sealed by Civora|signed by Civora|certified by Civora|Civora is engineer of record/i;

type Scenario = {
  name: string;
  address: string;
  width: string;
  depth: string;
  strictLock: boolean;
  messyChat: string;
};

const scenarios: Scenario[] = [
  {
    name: "gretna-office",
    address: "20525 Margo St, Gretna, NE",
    width: "1000",
    depth: "1000",
    strictLock: true,
    messyChat: "add 28000 sf office building, 140 parking, basin, public water, public sanitary, storm sewer and sidewalks",
  },
  {
    name: "omaha-mixed-use",
    address: "1600 Dodge St, Omaha, NE",
    width: "720",
    depth: "520",
    strictLock: true,
    messyChat: "make a smol mixed use site w parking, driveway, storm pipe, outfall, water and sewer pls",
  },
  {
    name: "messy-address-truth",
    address: "20525 marggo strett grtna ne",
    width: "450",
    depth: "450",
    strictLock: false,
    messyChat: "idk just make the site work and tell me what is blocked",
  },
];

async function shot(page: Page, testInfo: TestInfo, name: string) {
  await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
}

async function clickLikeHuman(page: Page, locator: ReturnType<Page["locator"]>, label: string) {
  const target = locator.filter({ visible: true }).first();
  await expect(target, `${label} should be visible`).toBeVisible({ timeout: 20_000 });
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  expect(box, `${label} should have a clickable box`).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2, { steps: 8 });
  await page.mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);
}

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await clickLikeHuman(page, workspaceButton, "Open workspace controls");
  }
  await clickLikeHuman(page, page.getByRole("button", { name }), `Open ${String(name)}`);
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 20_000 });
}

async function ensureDetailsOpen(page: Page, testId: string) {
  const details = page.getByTestId(testId);
  await expect(details).toBeVisible({ timeout: 20_000 });
  if (!(await details.evaluate((node) => node.hasAttribute("open")))) {
    await details.locator("summary").first().click();
  }
  return details;
}

async function clickSurface(page: Page, xRatio: number, yRatio: number) {
  const surface = page.getByTestId("preview-drawing-surface");
  await expect(surface).toBeVisible({ timeout: 20_000 });
  await expect(surface).not.toHaveAttribute("data-draw-mode", /^(select|pan)$/, { timeout: 10_000 });
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const clamp = (value: number) => Math.max(0.08, Math.min(0.92, value));
      const candidates: Array<{ x: number; y: number; distance: number }> = [];
      for (const xOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24, -0.32]) {
        for (const yOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24]) {
          const nextXRatio = clamp(ratios.xRatio + xOffset);
          const nextYRatio = clamp(ratios.yRatio + yOffset);
          const x = rect.left + rect.width * nextXRatio;
          const y = rect.top + rect.height * nextYRatio;
          const hit = document.elementFromPoint(x, y);
          const blocked = hit?.closest?.(
            '[data-object-overlay],button,input,select,textarea,aside,header,[data-testid="cad-precision-tools"],[data-testid="workspace-right-panel"]',
          );
          if ((hit === element || element.contains(hit)) && !blocked) {
            candidates.push({
              x,
              y,
              distance: Math.abs(nextXRatio - ratios.xRatio) + Math.abs(nextYRatio - ratios.yRatio),
            });
          }
        }
      }
      candidates.sort((a, b) => a.distance - b.distance);
      return candidates[0] ?? null;
    },
    { xRatio, yRatio },
  );
  expect(point, "Expected an exposed drawing-surface point").not.toBeNull();
  await page.mouse.move(point!.x, point!.y, { steps: 8 });
  await page.mouse.click(point!.x, point!.y);
}

async function startFreshProject(page: Page) {
  await page.getByTestId("header-projects-button").click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible({ timeout: 20_000 });
  await clickLikeHuman(page, page.getByRole("button", { name: /New Project/i }), "New Project");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 20_000 });
}

async function setupSite(page: Page, scenario: Scenario) {
  await openPanel(page, /^Setup$/, /Address \/ Location|Site Boundary|Survey \/ Terrain/i);
  const address = await ensureDetailsOpen(page, "setup-address-truth");
  await address.getByLabel("Type project address").fill(scenario.address);
  const siteBox = await ensureDetailsOpen(page, "setup-site-box-controls");
  await siteBox.getByLabel("Site width in feet").fill(scenario.width);
  await siteBox.getByLabel("Site depth in feet").fill(scenario.depth);
  await clickLikeHuman(page, page.getByTestId("create-centered-site-button"), "Create centered site");
  if (scenario.strictLock) {
    await expect(page.getByTestId("site-status")).toContainText(/Site Locked/i, { timeout: 40_000 });
  } else {
    await expect(page.locator("body")).toContainText(/Site Locked|could not|not configured|missing|review/i, { timeout: 40_000 });
  }
}

async function drawPlanObjects(page: Page, suffix: string) {
  await openPanel(page, /^Draw$/, /Draw & Objects|Tools/i);
  const tools = page.getByTestId("draw-cad-tools-section");

  await clickLikeHuman(page, tools.getByTestId("cad-tool-box"), "Add Box");
  await clickSurface(page, 0.32, 0.28);
  await clickSurface(page, 0.52, 0.43);
  await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill(`Office ${suffix}`);
  await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("building");

  await clickLikeHuman(page, tools.getByTestId("cad-tool-area"), "Add Area");
  await clickSurface(page, 0.18, 0.53);
  await clickSurface(page, 0.48, 0.53);
  await clickSurface(page, 0.48, 0.72);
  await clickLikeHuman(page, page.getByRole("button", { name: /^Finish$/ }), "Finish area");
  await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill(`Parking ${suffix}`);
  await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("parking");

  await clickLikeHuman(page, tools.getByTestId("cad-tool-line"), "Add Line");
  await clickSurface(page, 0.1, 0.62);
  await clickSurface(page, 0.34, 0.62);
  await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill(`Driveway ${suffix}`);
  await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("road");

  await clickLikeHuman(page, tools.getByTestId("cad-tool-point"), "Add Point");
  await clickSurface(page, 0.68, 0.34);
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/POINT|manual_drawn/i, { timeout: 10_000 });
}

async function exerciseObjectManager(page: Page) {
  let panel = page.getByTestId("object-manager-panel");
  await expect(panel).toBeVisible({ timeout: 20_000 });
  await expect(panel).toContainText(/Office|Parking|Driveway/i);
  await clickLikeHuman(page, page.getByTestId("preview-object-manager-focus"), "Focus selected object");

  // Focus intentionally closes the side panel so the selected object owns the
  // canvas. Reopen Draw before continuing with Object Manager edits, just as a
  // user would.
  await expect(panel).toBeHidden({ timeout: 10_000 });
  await openPanel(page, /^Draw$/, /Draw & Objects|Object Manager|Tools/i);
  panel = page.getByTestId("object-manager-panel");
  await expect(panel).toBeVisible({ timeout: 20_000 });

  await clickLikeHuman(page, page.getByTestId("preview-object-manager-visibility"), "Hide selected object");
  await expect(panel).toContainText(/Hidden|Visible/i);
  await clickLikeHuman(page, page.getByTestId("preview-object-manager-visibility"), "Show selected object");
  await page.getByTestId("preview-object-manager-color").filter({ visible: true }).first().evaluate((input: HTMLInputElement) => {
    input.value = "#1d4ed8";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function exercisePreview(page: Page) {
  await clickLikeHuman(page, page.getByTestId("preview-quality-high"), "High quality");
  const aiOn = page.getByTestId("ai-realism-on").filter({ visible: true }).first();
  if (await aiOn.isVisible().catch(() => false)) {
    await clickLikeHuman(page, aiOn, "AI visualization on");
    await expect(page.getByTestId("ai-realism-watermark").first()).toContainText(/visual concept only/i, { timeout: 20_000 });
  }
  await clickLikeHuman(page, page.getByTestId("preview-mode-3d"), "3D mode");
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 40_000 });
  await clickLikeHuman(page, page.getByTestId("preview-mode-2d"), "2D mode");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
}

async function generateDeliverAndChat(page: Page, scenario: Scenario) {
  await openPanel(page, /^Generate$/, /Generate Systems/i);
  await clickLikeHuman(page, page.getByTestId("generate-main-action"), "Generate");
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input|blocked|review/i, { timeout: 60_000 });

  await openPanel(page, /^Deliver$/, /Review package|Make Review Package/i);
  await clickLikeHuman(page, page.getByRole("button", { name: /Make Review Package/i }), "Make Review Package");
  await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Needs input|missing|Review package/i, { timeout: 60_000 });

  await clickLikeHuman(page, page.getByTestId("header-chat-button"), "Chat");
  const input = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await input.fill(scenario.messyChat);
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/created|added|blocked|review|next|site/i, { timeout: 20_000 });
  await input.fill("what did I change and what should I do next?");
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/changed|next|review|generate|deliver|blocked/i, { timeout: 20_000 });
  await input.fill("approve this for construction");
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/review|engineer|can't|cannot|not/i, { timeout: 20_000 });
}

async function assertHealth(page: Page, browserNoise: { consoleErrors: string[]; pageErrors: string[]; failedRequests: string[] }) {
  await expect(page.locator("body")).not.toContainText(unsafeClaims);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(browserNoise.pageErrors).toEqual([]);
  expect(browserNoise.consoleErrors.filter((line) => !ignoredBrowserNoise.test(line))).toEqual([]);
  expect(browserNoise.failedRequests.filter((line) => !ignoredBrowserNoise.test(line))).toEqual([]);
}

test.describe("hosted realistic user gauntlet", () => {
  for (const scenario of scenarios) {
    test(`fresh project scenario: ${scenario.name}`, async ({ page }, testInfo) => {
      test.setTimeout(240_000);
      const browserNoise = { consoleErrors: [] as string[], pageErrors: [] as string[], failedRequests: [] as string[] };
      page.on("console", (message) => {
        if (message.type() === "error") browserNoise.consoleErrors.push(message.text());
      });
      page.on("pageerror", (error) => browserNoise.pageErrors.push(error.message));
      page.on("requestfailed", (request) => {
        browserNoise.failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`);
      });

      await page.goto(`/demo/workspace?debugPreview=1&seedDemo=0&aiRealismProvider=mock&scenario=${scenario.name}-${Date.now()}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
      await startFreshProject(page);
      await shot(page, testInfo, `${scenario.name}-01-fresh`);
      await setupSite(page, scenario);
      await shot(page, testInfo, `${scenario.name}-02-site`);
      await drawPlanObjects(page, scenario.name);
      await shot(page, testInfo, `${scenario.name}-03-drawn`);
      await exerciseObjectManager(page);
      await shot(page, testInfo, `${scenario.name}-04-object-manager`);
      await exercisePreview(page);
      await shot(page, testInfo, `${scenario.name}-05-preview`);
      await generateDeliverAndChat(page, scenario);
      await shot(page, testInfo, `${scenario.name}-06-generate-deliver-chat`);
      await assertHealth(page, browserNoise);
    });
  }
});
