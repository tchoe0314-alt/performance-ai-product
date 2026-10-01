import { expect, test, type Page } from "@playwright/test";
import { defaultLayout } from "../../app/utils/culDeSacConcept";

async function openDraw(page: Page) {
  const button = page.getByRole("button", { name: /^Draw$/ }).first();
  if (!(await button.isVisible())) await page.getByRole("button", { name: "Show left sidebar" }).click();
  await button.click();
  const disclosure = page.getByTestId("object-manager-panel");
  if (!(await disclosure.evaluate(el => (el as HTMLDetailsElement).open))) await disclosure.locator(":scope > summary").click();
}
test("cul-de-sac and pipe are native editable project objects", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await page.route("**/api/**", route => route.fulfill({ json: { success: true } }));
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=libraries");
  await page.getByTestId("add-project-cul-de-sac").click();
  await expect(page.getByTestId("project-cul-de-sac-render")).toHaveCount(1);
  await page.getByTestId("add-project-pipe").click();
  await openDraw(page);
  const road = page.getByTestId("object-manager-row").filter({ has: page.getByText("Cul-de-sac", { exact: true }) });
  await road.getByRole("button", { name: "Select", exact: true }).click();
  const slider = page.getByRole("slider", { name: "Project cul-de-sac road width" });
  await expect(slider).toHaveValue("30"); await slider.press("ArrowRight");
  await expect(slider).toHaveValue("31");
  await expect(page.getByTestId("project-cul-de-sac-render")).toHaveCount(1);
  const pipe = page.getByTestId("object-manager-row").filter({ has: page.getByText("Pipe", { exact: true }) });
  await pipe.getByRole("button", { name: "Select", exact: true }).click();
  await expect(page.getByLabel("Pipe outside diameter (ft)")).toHaveValue("1");
  await page.getByLabel("Lowest occupied elevation (ft)").fill("-6");
  await page.getByLabel("Highest occupied elevation (ft)").fill("-5");
  await page.getByLabel("Elevation datum", { exact: true }).fill("project-benchmark");
  await page.getByLabel("Elevation evidence source").fill("Reviewed fixture drawing");
  await page.getByLabel("Required project clearance (ft)").fill("1");
  await page.getByLabel("I reviewed the occupied extents and elevation datum.").check();
  await page.getByRole("button", { name: "Apply elevation envelope", exact: true }).click();
  await expect(page.getByLabel("Lowest occupied elevation (ft)")).toHaveValue("-6");
  await expect(page.getByTestId("site-interference-panel")).toContainText("Type-aware draft checks");
  expect(errors).toEqual([]);
});

test("standalone JSON imports road and building into the main project without replacing existing objects", async ({ page }) => {
  await page.route("**/api/**", route => route.fulfill({ json: { success: true } }));
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=libraries");
  await page.getByLabel("Import cul-de-sac study into project").setInputFiles({ name: "study.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ ...defaultLayout(), roadWidth: 40 })) });
  await expect(page.getByRole("status").filter({ hasText: "Imported road and building" })).toBeVisible();
  await expect(page.getByTestId("project-cul-de-sac-render")).toHaveCount(1);
  await openDraw(page);
  await expect(page.getByTestId("object-manager-row").filter({ has: page.getByText("Imported study building", { exact: true }) })).toHaveCount(1);
  const road = page.getByTestId("object-manager-row").filter({ has: page.getByText("Imported cul-de-sac", { exact: true }) });
  await road.getByRole("button", { name: "Select", exact: true }).click();
  await expect(page.getByRole("slider", { name: "Project cul-de-sac road width" })).toHaveValue("40");
});
