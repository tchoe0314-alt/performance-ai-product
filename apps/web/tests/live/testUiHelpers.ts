import { expect, type Locator, type Page } from "@playwright/test";

export async function openCadPrecisionTools(page: Page): Promise<Locator> {
  const dock = page.getByTestId("cad-precision-tools").filter({ visible: true }).first();
  await expect(dock).toBeVisible();
  const isOpen = await dock.evaluate((element) => (element as HTMLDetailsElement).open);
  if (!isOpen) {
    await dock.locator(":scope > summary").click();
  }
  await expect(dock).toHaveAttribute("open", "");
  await expect(dock.getByLabel("Draft command input")).toBeVisible();
  return dock;
}
