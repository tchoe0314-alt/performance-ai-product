import { expect, type Locator, type Page } from "@playwright/test";

export async function openCadPrecisionTools(page: Page): Promise<Locator> {
  let dock = page.getByTestId("cad-precision-tools").filter({ visible: true }).first();
  if (!(await dock.isVisible().catch(() => false))) {
    let toggle = page.getByTestId("preview-precision-tools-toggle").filter({ visible: true }).first();
    if (!(await toggle.isVisible().catch(() => false))) {
      await page.getByLabel("Preview view options").filter({ visible: true }).first().click();
      toggle = page.getByTestId("preview-precision-tools-toggle").filter({ visible: true }).first();
    }
    await toggle.click();
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

export async function setPreviewQuality(page: Page, quality: "standard" | "high") {
  let control = page.getByTestId(`preview-quality-${quality}`).filter({ visible: true }).first();
  if (!(await control.isVisible().catch(() => false))) {
    await page.getByLabel("Preview view options").filter({ visible: true }).first().click();
    control = page.getByTestId(`preview-quality-${quality}`).filter({ visible: true }).first();
  }
  await expect(control).toBeVisible();
  await control.click();
}
