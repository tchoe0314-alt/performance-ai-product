import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = process.env.CIVORA_DEMO_OUTPUT_DIR
  ? path.resolve(process.env.CIVORA_DEMO_OUTPUT_DIR)
  : path.join(root, "investor-kit", "workflow-demo");
const baseURL = new URL(process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000");
assert(["127.0.0.1", "localhost"].includes(baseURL.hostname) && baseURL.protocol === "http:", "Demo recording is restricted to localhost; never run this script against customer projects.");
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: { dir: outputDir, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const video = page.video();

const wait = (ms) => page.waitForTimeout(ms);

async function caption(title, detail, duration = 2600) {
  await page.evaluate(({ title, detail }) => {
    document.getElementById("civora-demo-caption")?.remove();
    const caption = document.createElement("div");
    caption.id = "civora-demo-caption";
    caption.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
    Object.assign(caption.style, {
      position: "fixed",
      left: "50%",
      bottom: "34px",
      transform: "translateX(-50%)",
      zIndex: "2147483647",
      width: "min(820px, calc(100vw - 80px))",
      padding: "16px 22px",
      borderRadius: "16px",
      background: "rgba(7, 19, 37, 0.94)",
      boxShadow: "0 18px 60px rgba(0,0,0,.32)",
      color: "white",
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      textAlign: "center",
      pointerEvents: "none",
    });
    const strong = caption.querySelector("strong");
    const span = caption.querySelector("span");
    Object.assign(strong.style, { display: "block", fontSize: "23px", letterSpacing: "-.02em" });
    Object.assign(span.style, { display: "block", marginTop: "5px", fontSize: "15px", color: "#cbd5e1" });
    document.body.appendChild(caption);
  }, { title, detail });
  await wait(duration);
}

async function clearCaption() {
  await page.evaluate(() => document.getElementById("civora-demo-caption")?.remove());
  await wait(400);
}

async function openPanel(name) {
  const destinations = { Draw: { stage: "explore", panel: "objects" }, Review: { stage: "review", panel: "analysis" } };
  const destination = destinations[name];
  assert(destination, `Unsupported demo panel: ${name}`);
  const show = page.getByRole("button", { name: "Show left sidebar", exact: true });
  if (await show.isVisible()) await show.click();
  const stage = page.getByTestId(`workspace-stage-${destination.stage}`);
  if (await stage.count()) {
    await stage.click();
    await page.getByTestId("workspace-stage-panel").selectOption(destination.panel);
  } else {
    await page.getByRole("button", { name, exact: true }).first().click();
  }
  const panel = page.getByTestId("workspace-right-panel");
  await panel.waitFor({ state: "visible" });
  await wait(700);
}

async function minimizePanel() {
  const minimize = page.getByRole("button", { name: "Minimize", exact: true });
  if (await minimize.isVisible().catch(() => false)) {
    await minimize.click();
    await page.getByTestId("workspace-right-panel").waitFor({ state: "hidden" });
    await wait(500);
  }
}

try {
  await page.goto(new URL("/demo/workspace?seedDemo=1", baseURL).href, { waitUntil: "domcontentloaded" });
  await page.getByTestId("workspace-canvas-shell").waitFor({ state: "visible", timeout: 30_000 });
  await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
  await wait(1800);
  const mapToggle = page.getByTestId("preview-inner-map-toggle");
  if ((await mapToggle.getAttribute("aria-pressed")) === "true") {
    await mapToggle.click();
    await wait(700);
  }

  await caption("Civora", "A faster, traceable way to develop preliminary civil site concepts.", 3200);
  await clearCaption();

  await openPanel("Draw");
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate((element) => element.open))) {
    await objectList.locator(":scope > summary").click();
  }
  const firstObject = page.getByTestId("object-manager-row").filter({ hasText: "Office Headquarters" }).first();
  await firstObject.waitFor({ state: "visible" });
  await firstObject.getByTestId("object-manager-select").click();
  await firstObject.getByTestId("object-manager-inspect").click();
  await wait(700);
  await caption("1. Every element stays editable", "Buildings, parking, roads, landscaping, access, and drainage remain structured objects—not a flattened image.");
  await clearCaption();

  const widthInput = page.getByTestId("selected-object-width-input");
  await widthInput.waitFor({ state: "visible" });
  await widthInput.fill("320");
  await widthInput.press("Enter");
  await wait(900);
  if (await page.getByTestId("dependency-proposal-card").isVisible()) {
    await page.screenshot({ path: path.join(outputDir, "qa-dependency-proposal.png") });
    await page.getByTestId("dependency-proposal-accept").click();
    await page.getByTestId("dependency-proposal-card").waitFor({ state: "hidden" });
  }
  assert.equal(await widthInput.inputValue(), "320", "Do not record a successful edit caption if the control did not apply.");
  await caption("2. Design changes stay connected", "Resize the headquarters and Civora keeps the edit tied to the project model and review workflow.");
  await clearCaption();

  await minimizePanel();
  await page.keyboard.press("Escape");
  await openPanel("Review");
  await caption("3. Uncertainty is visible", "Entry geometry and detention assumptions are surfaced for professional review instead of being hidden.");
  await page.screenshot({ path: path.join(outputDir, "qa-review.png") });
  await clearCaption();

  await minimizePanel();
  await page.keyboard.press("Escape");
  await wait(700);
  await caption("From first concept to focused engineer review", "Civora accelerates preliminary feasibility while keeping the engineer in control.", 3800);
  await page.screenshot({ path: path.join(outputDir, "qa-final.png") });
  await clearCaption();
} finally {
  await page.close();
  await context.close();
  await browser.close();
}

const recordedPath = await video.path();
const finalPath = path.join(outputDir, "civora-workflow-demo.webm");
await fs.copyFile(recordedPath, finalPath);
if (recordedPath !== finalPath) await fs.unlink(recordedPath).catch(() => {});
console.log(finalPath);
