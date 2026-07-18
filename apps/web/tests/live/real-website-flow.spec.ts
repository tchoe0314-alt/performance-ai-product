import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
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

async function timedOpen(page: Page, buttonName: RegExp | string, expectedPanelTitle: RegExp | string) {
  const start = Date.now();
  await page.getByRole("button", { name: buttonName }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expectedPanelTitle, { timeout: 4_000 });
  return Date.now() - start;
}

async function expectSectionToggles(page: Page, testId: string, headerName: RegExp | string, visibleBodyText: RegExp | string) {
  const section = page.getByTestId(testId);
  const startsOpen = await section.evaluate((node) => node.hasAttribute("open"));
  if (!startsOpen) {
    await section.getByText(headerName).first().click();
    await expect(section).toHaveAttribute("open", "");
  }
  await expect(section).toContainText(visibleBodyText);
  await section.getByText(headerName).first().click();
  await expect(section).not.toHaveAttribute("open", "");
  await section.getByText(headerName).first().click();
  await expect(section).toHaveAttribute("open", "");
}

test.describe("real website workflow clarity", () => {
  test("uses one visible workflow home per major action and stays responsive", async ({ page }) => {
    await openDemoWorkspace(page);

    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Open workspace controls" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open projects from header" })).toBeVisible();
    await page.getByRole("button", { name: "Open projects from header" }).click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await expect(page.getByRole("button", { name: "Open chat from header" })).toBeVisible();
    await page.getByRole("button", { name: "Open workspace controls" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Project Setup");
    await expect(page.getByTestId("setup-address-truth")).toBeVisible();

    await expect(page.getByText("Quick actions")).toHaveCount(0);
    await expect(page.getByText("Generate Systems").first()).not.toBeVisible();
    await expect(page.getByText("Run engines with gates").first()).not.toBeVisible();
    await expect(page.getByRole("button", { name: /^Draw$/ })).toHaveCount(1);
    expect(await visibleButtonCount(page, "Generate")).toBe(1);

    await expectSectionToggles(page, "setup-address-truth", "Address / Location", /Type project address/);
    await expectSectionToggles(page, "setup-site-box-controls", "Site Boundary", /Width \(ft\)/);
    await page.getByTestId("setup-survey-terrain-card").getByText("Survey / Terrain").first().click();
    await expect(page.getByTestId("setup-survey-terrain-card")).toHaveAttribute("open", "");
    const siteContextDetails = page.getByTestId("setup-detect-inside-site");
    if (!(await siteContextDetails.evaluate((node) => node.hasAttribute("open")))) {
      await siteContextDetails.getByText("Auto Site Context").first().click();
    }
    await expect(page.getByTestId("setup-detect-inside-site")).toHaveAttribute("open", "");

    const objectOpenMs = await timedOpen(page, /^Draw$/, /Draw & Object Manager|CAD Tools/);
    await expect(page.getByTestId("draw-cad-tools-section")).toContainText(/Draw, modify, annotate, organize, command/);
    await expect(page.getByTestId("cad-tool-line")).toBeVisible();
    await page.getByTestId("cad-tool-line").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE tool active|LINE active/);
    await page.getByRole("button", { name: /^Draw$/ }).click();
    await page.getByTestId("cad-tool-snap").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/SNAP (on|off)/);
    await page.getByRole("button", { name: /^Draw$/ }).click();
    await page.getByTestId("cad-tool-offset").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/OFFSET/);
    await page.getByRole("button", { name: /^Draw$/ }).click();
    await page.getByTestId("cad-tool-dimension").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/DIM/);
    await page.getByRole("button", { name: /^Draw$/ }).click();
    await page.getByTestId("cad-tool-command").click();
    await expect(page.getByLabel("CAD command input")).toHaveValue(/LINE/);
    const generateOpenMs = await timedOpen(page, "Generate", /Generate Systems/);
    const deliverOpenMs = await timedOpen(page, /^Deliver$/, /Deliver|Plan Sheets|Files/);

    expect(objectOpenMs).toBeLessThan(1_500);
    expect(generateOpenMs).toBeLessThan(1_500);
    expect(deliverOpenMs).toBeLessThan(1_500);

    await expect(page.getByTestId("workspace-right-panel").getByRole("button", { name: /^Minimize$/ })).toBeVisible();
    await page.getByTestId("workspace-right-panel").getByRole("button", { name: /^Minimize$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await expect(page.getByTestId("reopen-civora-workspace")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Sections$/ })).toHaveCount(0);

    await page.getByRole("button", { name: "Hide left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible();
    expect(await visibleButtonCount(page, "Generate")).toBe(1);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
