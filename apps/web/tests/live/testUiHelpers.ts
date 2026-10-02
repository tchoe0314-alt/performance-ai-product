import { expect, type Locator, type Page } from "@playwright/test";

export async function openCadPrecisionTools(page: Page): Promise<Locator> {
  await revealPreviewCanvas(page);
  let dock = page.getByTestId("cad-precision-tools").filter({ visible: true }).first();
  if (!(await dock.isVisible().catch(() => false))) {
    let toggle = page.getByTestId("preview-precision-tools-toggle").filter({ visible: true }).first();
    if (!(await toggle.isVisible().catch(() => false))) {
      await page.getByLabel("Preview view options").filter({ visible: true }).first().click();
      toggle = page.getByTestId("preview-precision-tools-toggle").filter({ visible: true }).first();
    }
    await toggle.click();
    const options = page.getByLabel("Preview view options").filter({ visible: true }).first();
    if (await options.isVisible() && await options.evaluate(element => element.closest("details")?.open === true)) await options.click();
    dock = page.getByTestId("cad-precision-tools").filter({ visible: true }).first();
  }
  await expect(dock).toBeVisible();
  const isOpen = await dock.evaluate((element) => (element as HTMLDetailsElement).open);
  if (!isOpen) {
    await dock.locator(":scope > summary").click();
  }
  await expect(dock).toHaveAttribute("open", "");
  await expect(dock.getByLabel("Draft command input")).toBeVisible();
  return dock;
}

export async function revealPreviewCanvas(page: Page) {
  if ((page.viewportSize()?.width ?? 1440) < 1024) {
    const closePanel = page.getByRole("button", { name: "Close panel", exact: true }).filter({ visible: true }).first();
    if (await closePanel.isVisible()) await closePanel.click();
  }
}

export async function setPreviewQuality(page: Page, quality: "standard" | "high") {
  await revealPreviewCanvas(page);
  let control = page.getByTestId(`preview-quality-${quality}`).filter({ visible: true }).first();
  if (!(await control.isVisible().catch(() => false))) {
    await page.getByLabel("Preview view options").filter({ visible: true }).first().click();
    control = page.getByTestId(`preview-quality-${quality}`).filter({ visible: true }).first();
  }
  await expect(control).toBeVisible();
  await control.click();
  const viewOptions = page.getByLabel("Preview view options").filter({ visible: true }).first();
  if (await viewOptions.isVisible() && await viewOptions.evaluate((element) => element.closest("details")?.open === true)) {
    await viewOptions.click();
  }
}
