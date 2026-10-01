import { expect, test, type Page } from "@playwright/test";
import { defaultLayout } from "../../app/utils/culDeSacConcept";
import { PUBLIC_PLAN_REFERENCE } from "../../app/utils/publicPlanReference";

async function draw(page: Page) {
  const button = page.getByRole("button", { name: /^Draw$/ }).first();
  if (!(await button.isVisible())) await page.getByRole("button", { name: "Show left sidebar" }).click();
  await button.click();
  const list = page.getByTestId("object-manager-panel");
  if (!(await list.evaluate(el => (el as HTMLDetailsElement).open))) await list.locator(":scope > summary").click();
}
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", route => route.fulfill({ json: { success: true } }));
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=libraries");
});
test("native pipe profile controls validate, save, undo and redo reviewed depth evidence", async ({ page }) => {
  await page.getByTestId("add-project-pipe").click(); await draw(page);
  await page.getByTestId("object-manager-row").filter({ has: page.getByText("Pipe", { exact: true }) }).getByRole("button", { name: "Select", exact: true }).click();
  const detailed = page.getByTestId("object-detailed-geometry"); await detailed.locator("summary").click();
  await page.getByRole("button", { name: "Apply pipe depth profile", exact: true }).click();
  await expect(detailed.getByRole("alert")).toContainText("every route vertex");
  await page.getByLabel("Detailed elevation datum").fill("synthetic-test-datum");
  await page.getByLabel("Detailed geometry evidence source").fill("Synthetic software test, not surveyed");
  await page.getByLabel("Detailed required clearance (ft)").fill("1");
  const elevations = page.getByRole("spinbutton", { name: /^Pipe center elevation at vertex/ });
  for (let i = 0; i < await elevations.count(); i++) await elevations.nth(i).fill(String(-10 + i));
  await page.getByLabel("I reviewed this detailed geometry against its source.").check();
  await page.getByRole("button", { name: "Apply pipe depth profile", exact: true }).click();
  await expect(detailed.getByRole("alert")).toHaveCount(0);
  await detailed.locator("summary").click();
  await expect(page.getByLabel("Pipe center elevation at vertex 1 (ft)")).toHaveValue("-10");
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await detailed.locator("summary").click(); await expect(page.getByLabel("Pipe center elevation at vertex 1 (ft)")).toHaveValue("");
  await page.getByRole("button", { name: "Redo draft change", exact: true }).click();
  await detailed.locator("summary").click(); await expect(page.getByLabel("Pipe center elevation at vertex 1 (ft)")).toHaveValue("-10");
});
test("occupied parts save and require completeness instead of inferring a foundation", async ({ page }) => {
  await page.getByLabel("Import cul-de-sac study into project").setInputFiles({ name: "study.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(defaultLayout())) });
  await draw(page);
  await page.getByTestId("object-manager-row").filter({ has: page.getByText("Imported study building", { exact: true }) }).getByRole("button", { name: "Select", exact: true }).click();
  const detailed = page.getByTestId("object-detailed-geometry"); await detailed.locator("summary").click();
  await page.getByLabel("Detailed elevation datum").fill("test-datum");
  await page.getByLabel("Detailed geometry evidence source").fill("Synthetic completeness fixture");
  await page.getByLabel("Detailed required clearance (ft)").fill("1");
  await page.getByRole("button", { name: "Add occupied part", exact: true }).click();
  await page.getByLabel("Part 1 Lowest elevation (ft)").fill("0"); await page.getByLabel("Part 1 Highest elevation (ft)").fill("20");
  await page.getByRole("button", { name: "Add occupied part", exact: true }).click();
  await page.getByLabel("Part 2 kind").selectOption("foundation");
  await page.getByLabel("Part 2 Lowest elevation (ft)").fill("-8"); await page.getByLabel("Part 2 Highest elevation (ft)").fill("0");
  await page.getByLabel("I reviewed this detailed geometry against its source.").check();
  await page.getByRole("button", { name: "Apply occupied parts", exact: true }).click();
  await expect(detailed.getByRole("alert")).toContainText("complete occupied model");
  await page.getByLabel("This includes all occupied parts, foundations and supports.").check();
  await page.getByRole("button", { name: "Apply occupied parts", exact: true }).click();
  await detailed.locator("summary").click(); await expect(page.getByLabel("Part 2 Lowest elevation (ft)")).toHaveValue("-8");
});
test("public plan reference keeps attribution and missing data remains review-required", async ({ page }) => {
  await expect(page.getByRole("link", { name: "Open original utility plans (City of Madison)" })).toHaveAttribute("href", PUBLIC_PLAN_REFERENCE.url);
  await page.getByTestId("add-public-reference-segment").click(); await draw(page);
  await expect(page.getByTestId("site-interference-panel")).toContainText("outside diameter is missing");
  await page.getByTestId("object-manager-row").filter({ has: page.getByText("Public-plan sewer segment (schematic)", { exact: true }) }).getByRole("button", { name: "Select", exact: true }).click();
  await expect(page.getByLabel("Pipe outside diameter (ft)")).toHaveValue("");
  const detailed = page.getByTestId("object-detailed-geometry"); await detailed.locator("summary").click();
  await expect(page.getByLabel("Pipe center elevation at vertex 1 (ft)")).toHaveValue("");
});
