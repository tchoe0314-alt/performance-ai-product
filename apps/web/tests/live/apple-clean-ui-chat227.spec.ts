import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1") {
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function visibleButtonCount(page: Page, name: RegExp | string) {
  const buttons = page.getByRole("button", { name });
  const count = await buttons.count();
  let visible = 0;
  for (let index = 0; index < count; index += 1) {
    if (await buttons.nth(index).isVisible()) visible += 1;
  }
  return visible;
}

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible()) {
    await workspaceButton.click();
  }
  const navName = name === "Object Manager" ? /^Draw$/ : name;
  await page.getByRole("button", { name: navName }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

test.describe("Chat 227 Apple-clean UI", () => {
  test("desktop first viewport is preview-first with restrained chrome", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openDemoWorkspace(page);

    await expect(page.getByTestId("workspace-canvas-frame")).toBeVisible();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await expect(page.getByTestId("primary-workflow-sidebar")).toBeVisible();
    await expect(page.getByRole("button", { name: "Open chat from header" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open projects from header" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Search unavailable" })).toHaveCount(0);
    await expect(page.getByTestId("preview-inner-mode-2d").filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByTestId("preview-inner-quality-high").filter({ visible: true }).first()).toBeVisible();

    expect(await visibleButtonCount(page, "Generate")).toBe(1);
    expect(await visibleButtonCount(page, /^Deliver$/)).toBe(1);

    await expect(page.getByTestId("preview-source-review-object-badge")).toHaveCount(0);

    await page.getByRole("button", { name: "Open projects from header" }).click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.getByRole("button", { name: "Minimize" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
  });

  test("mobile has no horizontal overflow and keeps chat/projects reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoWorkspace(page);

    const showSidebar = page.getByRole("button", { name: "Show left sidebar" });
    if (await showSidebar.isVisible().catch(() => false)) {
      await showSidebar.click();
    }
    await expect(page.getByTitle("Projects")).toBeVisible();
    await page.getByTitle("Projects").click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.getByRole("button", { name: "Minimize" }).click();
    await expect(page.getByTitle("Chat")).toBeVisible();
    await page.getByTitle("Chat").click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("drawer sections and major workflow actions stay focused", async ({ page }) => {
    await openDemoWorkspace(page);

    await openPanel(page, /^Setup$/, /Project Setup/);
    await expect(page.getByTestId("setup-address-truth")).toHaveAttribute("open", "");
    await expect(page.getByLabel(/Type project address/i)).toBeVisible();
    expect(await visibleButtonCount(page, /Enter Address First|Apply Address/i)).toBe(1);

    await openPanel(page, "Generate", /Generate Systems/);
    expect(await visibleButtonCount(page, /^Generate$/)).toBe(1);

    await openPanel(page, /^Deliver$/, /Review package|Deliver/);
    await expect(page.getByTestId("deliver-review-package-flow").getByRole("button", { name: /Make Review Package/i })).toHaveCount(1);
  });

  test("Object Manager can select, rename, color, layer, hide, focus, and delete", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&seedDemo=1");
    await openPanel(page, "Object Manager", /Draw & Objects|Tools/);

    const rows = page.getByTestId("object-manager-row");
    await expect(rows.first()).toBeVisible();
    const editable = rows.filter({ has: page.getByTestId("object-manager-rename") }).first();
    await expect(editable).toBeVisible();

    await editable.getByTestId("object-manager-select").click();
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/2D|3D|High|Standard/);

    await editable.getByTestId("object-manager-rename").fill("Apple Clean Test Object");
    await expect(editable).toContainText("Apple Clean Test Object");

    await editable.getByTestId("object-manager-color").fill("#0f766e");
    await editable.getByTestId("object-manager-type").selectOption("parking");
    await expect(editable).toContainText("Parking Field");

    await editable.getByTestId("object-manager-visibility").click();
    await expect(editable.getByTestId("object-manager-visibility")).toContainText("Show");
    await editable.getByTestId("object-manager-visibility").click();
    await expect(editable.getByTestId("object-manager-visibility")).toContainText("Hide");

    await editable.getByTestId("object-manager-focus").click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);

    await openPanel(page, "Object Manager", /Draw & Objects|Tools/);
    const renamed = page.getByTestId("object-manager-row").filter({ hasText: "Apple Clean Test Object" }).first();
    await renamed.getByTestId("object-manager-delete").click();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Apple Clean Test Object" })).toHaveCount(0);
  });
});
