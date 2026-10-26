import { expect, test } from "@playwright/test";
import { openWorkspacePanelByName, workspaceToolButton } from "./helpers/workspaceNavigation";
import { sidePanelCopy } from "../../app/utils/workspaceShell";

// Navigation-only acceptance for K05. Provider/import/generation workflows remain
// separate; unavailable API responses here must never certify their completion.
for (const width of [320, 1440]) {
  test(`hosted workflow navigation reaches actual destination content at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/**", route => route.fulfill({ status: 503,
      json: { detail: "Offline navigation fixture: providers and persistence unavailable" } }));
    await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    await expect(workspaceToolButton(page, "Setup")).toBeVisible();
    await workspaceToolButton(page, "Setup").click({ trial: true });
    for (const [name, panel] of [[/^Setup$/, "site_existing"], [/^Generate$/, "generate"], [/^Deliver$/, "deliverables"]] as const) {
      await openWorkspacePanelByName(page, name);
      await expect(page.getByTestId("workspace-stage-panel")).toHaveValue(panel);
      const drawer = page.getByTestId("workspace-right-panel");
      await expect(drawer).toBeVisible();
      await expect(drawer.getByText(sidePanelCopy[panel].title, { exact: true }).first()).toBeVisible();
      if (panel === "site_existing") await expect(drawer.getByTestId("setup-address-truth")).toBeVisible();
      if (panel === "generate") await expect(drawer.getByTestId("generate-main-action")).toBeVisible();
      if (panel === "deliverables") await expect(drawer.getByRole("button", { name: /Make Review Package/i })).toBeVisible();
    }
  });
}
