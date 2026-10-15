import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { expect, test } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import ts from "typescript";
import { WORKSPACE_STATES } from "../../app/components/WorkspaceStateBadge";
import { sourceVisualState } from "../../app/utils/workspaceVisualState";

// Playwright transforms imported TSX into its own component representation.
// Compile this real React component with the project's JSX runtime instead.
const badgeModule = { exports: {} as { WorkspaceStateBadge: import("react").ComponentType<{ state: keyof typeof WORKSPACE_STATES }> } };
const badgeSource = readFileSync(path.resolve("app/components/WorkspaceStateBadge.tsx"), "utf8");
const badgeCode = ts.transpileModule(badgeSource, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } }).outputText;
new Function("require", "module", "exports", badgeCode)(createRequire(path.resolve("package.json")), badgeModule, badgeModule.exports);

const sizes = [
  [320, 568], [390, 844], [844, 390], [1024, 600],
  [1280, 720], [1920, 1080], [2560, 1440],
];
for (const [width, height] of sizes) {
  test(`compact centered controls and contained panels at ${width}x${height}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    await page.goto("/demo/workspace?debugPreview=1");
    await openWorkspaceTool(page, "Draw");
    const drawer = page.getByTestId("workspace-right-panel");
    await expect(drawer).toBeVisible();
    const grid = page.locator(".civora-tool-grid").first();
    await expect(grid).toBeVisible();
    const line = grid.getByRole("button", { name: "Line", exact: true });
    await expect(line).toHaveAttribute("title", /Line/);
    await expect(line.locator("span")).toHaveClass("sr-only");
    const alignment = await line.evaluate(el => {
      const box = el.getBoundingClientRect(), icon = el.querySelector("svg")!.getBoundingClientRect();
      return { x: Math.abs(box.x + box.width / 2 - icon.x - icon.width / 2), y: Math.abs(box.y + box.height / 2 - icon.y - icon.height / 2), height: box.height };
    });
    expect(alignment.x).toBeLessThan(1);
    expect(alignment.y).toBeLessThan(1);
    expect(alignment.height).toBeLessThanOrEqual(44);
    expect(alignment.height).toBeGreaterThanOrEqual(info.project.use.isMobile ? 44 : 32);
    const panelBounds = (await drawer.boundingBox())!;
    expect(panelBounds.x).toBeGreaterThanOrEqual(0);
    expect(panelBounds.x + panelBounds.width).toBeLessThanOrEqual(width + 1);
    expect(panelBounds.y).toBeGreaterThanOrEqual(0);
    expect(panelBounds.height).toBeGreaterThan(90);
    if (height < 500 && width < 1024) await expect(page.getByTestId("floating-command-bar")).toBeHidden();
    const overflow = await drawer.evaluate(el => el.scrollWidth - el.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`draw-controls-${width}.png`) });
    await page.getByRole("button", { name: "Minimize", exact: true }).click();
    await expect(drawer).toBeHidden();
    await page.getByTestId("preview-layer-menu").locator("summary").click();
    const menu = page.getByTestId("preview-semantic-layer-controls");
    await expect(menu).toBeVisible();
    const menuBounds = (await menu.boundingBox())!;
    expect(menuBounds.x).toBeGreaterThanOrEqual(0);
    expect(menuBounds.x + menuBounds.width).toBeLessThanOrEqual(width + 1);
    expect(menuBounds.y + menuBounds.height).toBeLessThanOrEqual(height + 1);
    await page.screenshot({ path: info.outputPath(`compact-${width}.png`) });
  });
}

test("visual states retain distinct text and icons even without color", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1");
  const html = Object.keys(WORKSPACE_STATES).map(state => renderToStaticMarkup(createElement(badgeModule.exports.WorkspaceStateBadge, { state: state as keyof typeof WORKSPACE_STATES }))).join("");
  // Reuse the real compiled stylesheet, while testing every state independently
  // of whether this demo currently has a running job or an engineering review.
  await page.locator("body").evaluate((el, markup) => {
    const fixture = document.createElement("section");
    fixture.id = "design-state-fixture";
    fixture.style.cssText = "position:fixed;inset:60px 10px auto;z-index:9999;background:white;padding:16px";
    fixture.innerHTML = markup;
    el.appendChild(fixture);
  }, html);
  for (const [state, definition] of Object.entries(WORKSPACE_STATES)) {
    const badge = page.locator(`#design-state-fixture [data-ui-state="${state}"]`);
    await expect(badge).toContainText(definition.label);
    await expect(badge.locator("svg")).toHaveCount(1);
  }
  expect(await page.locator('#design-state-fixture [data-ui-state="fixed"]').evaluate(el => getComputedStyle(el).borderStyle)).toBe("double");
  expect(await page.locator('#design-state-fixture [data-ui-state="hidden"]').evaluate(el => getComputedStyle(el).borderStyle)).toBe("dashed");
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await page.locator("#design-state-fixture .civora-state-spinner").evaluate(el => getComputedStyle(el).animationName)).toBe("none");
});

test("confidence never masquerades as verification", () => {
  expect(sourceVisualState({entry_id: "source", confidence_band: "higher"})).toBe("unverified");
  expect(sourceVisualState({entry_id: "source", verified: true, stale: true})).toBe("stale");
  expect(sourceVisualState({entry_id: "source", verified: true, needs_verification: true})).toBe("unverified");
  expect(sourceVisualState({entry_id: "source", verified: true, needs_survey_control: true})).toBe("unverified");
  expect(sourceVisualState({entry_id: "source", verified: true})).toBe("verified");
});

test("an open drawer stays contained when the same workspace is resized", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1");
  await openWorkspaceTool(page, "Draw");
  const drawer = page.getByTestId("workspace-right-panel");
  for (const [width, height] of [[1280,720],[390,844],[844,390],[1920,1080]]) {
    await page.setViewportSize({width,height});
    await expect(drawer).toBeVisible();
    await expect.poll(async () => {
      const box = (await drawer.boundingBox())!;
      return box.x >= 0 && box.x + box.width <= width + 1 && box.y >= 0 && box.y + box.height <= height + 1;
    }).toBe(true);
    await expect(page.getByTestId("cad-tool-line")).toBeEnabled();
  }
});

test("populated object actions stay centered and share one compact row height", async ({ page }, info) => {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1");
  await openWorkspaceTool(page, "Draw");
  const panel = page.getByTestId("object-manager-panel");
  if (!await panel.evaluate(el => el.hasAttribute("open"))) await panel.locator(":scope > summary").click();
  const row = page.getByTestId("object-manager-row").filter({hasText:"Office Headquarters"}).first();
  const actions = row.locator(".civora-panel-actions button");
  await expect(actions).toHaveCount(10);
  const dimensions = await actions.evaluateAll(buttons => buttons.map(button => {
    const b = button.getBoundingClientRect(), i = button.querySelector("svg")?.getBoundingClientRect();
    return { height:b.height, overflow:button.scrollWidth-button.clientWidth, dx:i ? Math.abs(b.x+b.width/2-i.x-i.width/2) : 0, dy:i ? Math.abs(b.y+b.height/2-i.y-i.height/2) : 0 };
  }));
  for (const d of dimensions) {
    expect(d.height).toBe(info.project.use.isMobile ? 44 : 32);
    expect(d.overflow).toBe(0);
    expect(d.dx).toBeLessThan(1);
    expect(d.dy).toBeLessThan(1);
  }
});

test("icon tools stay keyboard-operable with a visible focus ring", async ({ page, browserName }) => {
  await page.goto("/demo/workspace?debugPreview=1");
  await openWorkspaceTool(page, "Draw");
  const line = page.getByTestId("cad-tool-line");
  await line.focus();
  // WebKit's default platform tab mode skips button controls; its all-control
  // navigation shortcut must still land on the same next accessible tool.
  await page.keyboard.press(browserName === "webkit" ? "Alt+Tab" : "Tab");
  const focused = page.getByTestId("cad-tool-polyline");
  await expect(focused).toBeFocused();
  expect(await focused.evaluate(el => getComputedStyle(el).outlineStyle)).toBe("solid");
  await page.keyboard.press("Enter");
  if (!test.info().project.use.isMobile) await expect(page.getByTestId("active-draw-hud")).toBeVisible();
});
