import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  const shell = page.getByTestId("workspace-canvas-shell");
  await expect(shell).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function openWorkspacePanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const navName = name === "Object Manager" || name === "Open canvas from sidebar" ? /^Draw$/ : name;
  const directButton = page.getByRole("button", { name: navName }).first();
  await directButton.click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

async function openDrawTools(page: Page) {
  await openWorkspacePanel(page, /^Draw$/, /Draw & Object Manager|CAD Tools/);
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
}

async function clickCadTool(page: Page, tool: string, expected: RegExp) {
  await openDrawTools(page);
  const cadTools = page.getByTestId("draw-cad-tools-section");
  let toolButton = cadTools.getByTestId(`cad-tool-${tool}`).filter({ visible: true }).first();
  if (!(await toolButton.isVisible().catch(() => false))) {
    const summaries = cadTools.locator("details summary");
    const count = await summaries.count();
    for (let index = 0; index < count; index += 1) {
      const summary = summaries.nth(index);
      const parentDetails = summary.locator("xpath=ancestor::details[1]");
      const isOpen = await parentDetails.evaluate((element) => (element as HTMLDetailsElement).open).catch(() => true);
      if (!isOpen) await summary.click();
      toolButton = cadTools.getByTestId(`cad-tool-${tool}`).filter({ visible: true }).first();
      if (await toolButton.isVisible().catch(() => false)) break;
    }
  }
  await toolButton.scrollIntoViewIfNeeded();
  await expect(toolButton).toBeEnabled();
  await toolButton.click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(expected, { timeout: 5_000 });
}

test.describe("button functionality audit", () => {
  test("CAD palette buttons each trigger a distinct action or truthful blocked state", async ({ page }) => {
    await openDemoWorkspace(page);

    const toolExpectations: Array<[string, RegExp]> = [
      ["select", /SELECT tool active/i],
      ["line", /LINE tool active/i],
      ["polyline", /PLINE tool active/i],
      ["area", /AREA tool active/i],
      ["box", /RECTANGLE tool active/i],
      ["point", /POINT tool active/i],
      ["circle", /CIRCLE command loaded/i],
      ["arc", /ARC command loaded/i],
      ["text", /TEXT command loaded/i],
      ["move", /MOVE (applied|blocked)/i],
      ["copy", /COPY command loaded/i],
      ["rotate", /ROTATE (applied|blocked)/i],
      ["scale", /SCALE (applied|blocked)/i],
      ["offset", /OFFSET (created|blocked)/i],
      ["trim", /TRIM (applied|blocked)/i],
      ["extend", /EXTEND (applied|blocked)/i],
      ["fillet", /FILLET (applied|blocked)/i],
      ["join", /JOIN (created|blocked)/i],
      ["split", /SPLIT (restored|blocked)/i],
      ["close", /CLOSE (converted|blocked|skipped)/i],
      ["open", /OPEN (converted|blocked|skipped)/i],
      ["reverse", /REVERSE (flipped|blocked)/i],
      ["delete", /DELETE (removed|blocked)/i],
      ["dimension", /DIM (added|blocked)/i],
      ["hatch", /HATCH (applied|blocked)/i],
      ["symbol", /SYMBOL inserted/i],
      ["layer", /LAYER (applied|blocked)/i],
      ["properties", /PROPERTIES (applied|blocked)/i],
      ["snap", /SNAP (on|off)/i],
      ["ortho", /ORTHO (on|off)/i],
      ["undo", /UNDO (restored|blocked)/i],
      ["redo", /REDO (restored|blocked)/i],
      ["command", /Command line focused/i],
    ];

    for (const [tool, expected] of toolExpectations) {
      await clickCadTool(page, tool, expected);
    }

    await expect(page.getByLabel("CAD command input")).toHaveValue(/LINE|CIRCLE|ARC|TEXT|COPY/);
  });

  test("primary visible buttons open panels or expose truthful disabled states without browser errors", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await openDemoWorkspace(page);

    await expect(page.getByRole("button", { name: "Search unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Undo unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Redo unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Notifications unavailable" })).toHaveCount(0);

    const panels: Array<[RegExp | string, RegExp | string]> = [
      [/^Setup$/, /Project Setup/],
      [/^Draw$/, /Draw & Object Manager|CAD Tools/],
      ["Generate", /Generate Systems/],
      [/^Deliver$/, /Deliver|Plan Sheets|Files/],
    ];

    for (const [button, expected] of panels) {
      await openWorkspacePanel(page, button, expected);
    }

    await page.getByRole("button", { name: "Open chat from header" }).click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();

    await page.getByRole("button", { name: /^Setup$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Project Setup");
    await expect(page.getByTestId("setup-address-truth")).toBeVisible();

    await page.getByRole("button", { name: "Hide left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible();
    await page.getByRole("button", { name: "Show left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Hide left sidebar" })).toBeVisible();

    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
