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
  await openWorkspacePanel(page, /^Draw$/, /Draw & Objects|Tools/);
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
  test("Draft palette buttons each trigger a distinct action or truthful blocked state", async ({ page }) => {
    await openDemoWorkspace(page);

    const blockedOrNeedsInput = "blocked|needs input";
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
      ["move", new RegExp(`MOVE (applied|${blockedOrNeedsInput})`, "i")],
      ["copy", /COPY command loaded/i],
      ["rotate", new RegExp(`ROTATE (applied|${blockedOrNeedsInput})`, "i")],
      ["scale", new RegExp(`SCALE (applied|${blockedOrNeedsInput})`, "i")],
      ["offset", new RegExp(`OFFSET (created|${blockedOrNeedsInput})`, "i")],
      ["trim", new RegExp(`TRIM (applied|${blockedOrNeedsInput})`, "i")],
      ["extend", new RegExp(`EXTEND (applied|${blockedOrNeedsInput})`, "i")],
      ["fillet", new RegExp(`FILLET (applied|${blockedOrNeedsInput})`, "i")],
      ["join", new RegExp(`JOIN (created|${blockedOrNeedsInput})`, "i")],
      ["split", new RegExp(`SPLIT (restored|${blockedOrNeedsInput})`, "i")],
      ["close", new RegExp(`CLOSE (converted|${blockedOrNeedsInput}|skipped)`, "i")],
      ["open", new RegExp(`OPEN (converted|${blockedOrNeedsInput}|skipped)`, "i")],
      ["reverse", new RegExp(`REVERSE (flipped|${blockedOrNeedsInput})`, "i")],
      ["delete", new RegExp(`DELETE (removed|${blockedOrNeedsInput})`, "i")],
      ["dimension", new RegExp(`DIM (added|${blockedOrNeedsInput})`, "i")],
      ["hatch", new RegExp(`HATCH (applied|${blockedOrNeedsInput})`, "i")],
      ["symbol", /SYMBOL inserted/i],
      ["layer", new RegExp(`LAYER (applied|${blockedOrNeedsInput})`, "i")],
      ["properties", new RegExp(`PROPERTIES (applied|${blockedOrNeedsInput})`, "i")],
      ["snap", /SNAP (on|off)/i],
      ["ortho", /ORTHO (on|off)/i],
      ["undo", new RegExp(`UNDO (restored|${blockedOrNeedsInput})`, "i")],
      ["redo", new RegExp(`REDO (restored|${blockedOrNeedsInput})`, "i")],
      ["command", /Command line focused/i],
    ];

    for (const [tool, expected] of toolExpectations) {
      await clickCadTool(page, tool, expected);
    }

    await expect(page.getByLabel("Draft command input")).toHaveValue(/LINE|CIRCLE|ARC|TEXT|COPY/);

    const powerTools = page.getByTestId("cad-power-tools");
    await expect(powerTools).toBeVisible();
    const powerExpectations: Array<[string, RegExp]> = [
      ["join", /JOIN (created|needs input|blocked)/i],
      ["split", /SPLIT (restored|needs input|blocked)/i],
      ["copy", /COPY (created|needs input|blocked)/i],
      ["rotate", /ROTATE (applied|needs input|blocked)/i],
      ["mirror", /MIRROR (H applied|needs input|blocked)/i],
      ["array", /ARRAY (created|needs input|blocked)/i],
      ["hatch", /HATCH (applied|needs input|blocked)/i],
      ["align", /ALIGN( LEFT)? (aligned|needs input|blocked)/i],
    ];
    for (const [tool, expected] of powerExpectations) {
      await powerTools.getByTestId(`cad-power-${tool}`).click();
      await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(expected, { timeout: 5_000 });
    }
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
      [/^Setup$/, /Setup|Address \/ Location|Site Boundary/],
      [/^Draw$/, /Draw & Objects|Tools/],
      ["Generate", /Generate Systems/],
      [/^Deliver$/, /Deliver|Plan Sheets|Files/],
    ];

    for (const [button, expected] of panels) {
      await openWorkspacePanel(page, button, expected);
    }

    await page.getByTestId("header-chat-button").click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();

    await page.getByRole("button", { name: /^Setup$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Setup|Address \/ Location|Site Boundary/);
    await expect(page.getByTestId("setup-address-truth")).toBeVisible();

    await page.getByRole("button", { name: "Hide left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible();
    await page.getByRole("button", { name: "Show left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Hide left sidebar" })).toBeVisible();

    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
