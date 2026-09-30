import { expect, test } from "@playwright/test";

test("shows the rights-cleared terrain benchmark and its safety boundary", async ({ page }) => {
  await page.goto("/validation/terrain");

  await expect(page.getByRole("heading", { name: "Civora processed real, rights-cleared terrain." })).toBeVisible();
  await expect(page.getByText("8 of 8 checks passed")).toBeVisible();
  await expect(page.getByText("4,096", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Passed does not mean construction-ready" })).toBeVisible();
  await expect(page.getByText("Independent licensed-engineer review")).toBeVisible();
});
