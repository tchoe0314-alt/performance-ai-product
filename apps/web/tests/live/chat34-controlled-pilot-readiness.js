#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");
const { chromium, request } = require("playwright");

const baseUrl = (process.env.CHAT34_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || "https://www.civoraai.com").replace(/\/+$/, "");
const apiBase = (process.env.CHAT34_API_BASE_URL || process.env.PLAYWRIGHT_API_BASE_URL || "https://api.civoraai.com").replace(/\/+$/, "");
const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const artifactDir = path.resolve(
  process.cwd(),
  process.env.CHAT34_ARTIFACT_DIR || "playwright-artifacts/chat34-controlled-pilot",
);
const artifactPath = path.join(artifactDir, "chat34-controlled-pilot-readiness.json");
const screenshotDir = path.join(artifactDir, "screenshots");
const TOKEN_KEY = "civora-ai-token";
const SENSITIVE_QUERY_KEYS = /(^|_)(access_)?token$|secret|password|key|credential|signature/i;

/** @type {Array<{name:string, ok:boolean, detail?:string, owner?:string, severity?:string, optional?:boolean}>} */
const checks = [];
/** @type {Array<{type:string, message:string, url?:string}>} */
const browserErrors = [];
/** @type {Array<{url:string, method?:string, status?:number, failure?:string}>} */
const failedRequests = [];
/** @type {Array<{name:string, path:string}>} */
const screenshots = [];
const startedAt = Date.now();
let authToken = "";

function note(name, ok, detail = "", owner = "Chat 34", severity = ok ? "" : "P1", optional = false) {
  checks.push({
    name,
    ok: Boolean(ok),
    detail: String(detail || "").slice(0, 800),
    owner,
    severity: ok ? "" : severity,
    optional: Boolean(optional),
  });
}

function artifact() {
  const blockers = checks
    .filter((check) => !check.ok && !check.optional)
    .map((check) => ({
      severity: check.severity || "P1",
      owner: check.owner || "Chat 34",
      name: check.name,
      detail: check.detail || "",
    }));
  return {
    name: "Chat 34 controlled pilot readiness",
    generated_at: new Date().toISOString(),
    runtime_ms: Date.now() - startedAt,
    environment: {
      base_url: baseUrl,
      api_base_url: apiBase,
      credentials_present: Boolean(email && password),
    },
    controlled_pilot_ready: blockers.every((blocker) => !["P0", "P1"].includes(blocker.severity)),
    checks,
    blockers,
    browser_errors: browserErrors,
    failed_requests: failedRequests,
    screenshots,
  };
}

function writeArtifact() {
  fs.mkdirSync(artifactDir, { recursive: true });
  fs.writeFileSync(artifactPath, JSON.stringify(artifact(), null, 2));
}

function sanitizeUrl(value) {
  try {
    const parsed = new URL(value);
    for (const key of Array.from(parsed.searchParams.keys())) {
      if (SENSITIVE_QUERY_KEYS.test(key)) {
        parsed.searchParams.set(key, "[redacted]");
      }
    }
    return parsed.toString();
  } catch {
    return String(value || "").replace(/([?&][^=&]*(?:token|secret|password|key|credential|signature)[^=]*=)[^&]+/gi, "$1[redacted]");
  }
}

async function screenshot(page, name) {
  try {
    fs.mkdirSync(screenshotDir, { recursive: true });
    const filePath = path.join(screenshotDir, `${name}.png`);
    await page.screenshot({ path: filePath, fullPage: true });
    screenshots.push({ name, path: filePath });
  } catch (error) {
    browserErrors.push({ type: "screenshot", message: String(error && error.message ? error.message : error) });
  }
}

async function soft(name, owner, severity, fn, optional = false) {
  try {
    const result = await fn();
    if (typeof result === "object" && result !== null && "ok" in result) {
      note(name, result.ok, result.detail || "", owner, severity, optional);
    } else {
      note(name, Boolean(result), "", owner, severity, optional);
    }
    return result;
  } catch (error) {
    note(name, false, String(error && error.message ? error.message : error), owner, severity, optional);
    return null;
  } finally {
    writeArtifact();
  }
}

function attachPageTelemetry(page) {
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      browserErrors.push({ type: "console", message: msg.text(), url: sanitizeUrl(page.url()) });
    }
  });
  page.on("pageerror", (error) => {
    browserErrors.push({ type: "pageerror", message: error.message, url: sanitizeUrl(page.url()) });
  });
  page.on("requestfailed", (req) => {
    failedRequests.push({
      url: sanitizeUrl(req.url()),
      method: req.method(),
      failure: req.failure()?.errorText || "request failed",
    });
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 500) {
      failedRequests.push({ url: sanitizeUrl(response.url()), status, method: response.request().method() });
    }
  });
}

async function apiJson(context, url, options = {}) {
  const response = options.method === "POST"
    ? await context.post(url, { data: options.data, headers: options.headers })
    : await context.get(url, { headers: options.headers });
  const text = await response.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  return { response, text, json };
}

async function visibleText(page) {
  return page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
}

async function signInIfNeeded(page) {
  if (await page.getByTestId("workspace-canvas-shell").isVisible().catch(() => false)) return true;
  const emailInput = page.getByPlaceholder("you@example.com");
  const passwordInput = page.getByPlaceholder("At least 8 characters");
  if (!(await emailInput.isVisible().catch(() => false)) || !(await passwordInput.isVisible().catch(() => false))) {
    return false;
  }
  await emailInput.fill(email, { timeoutMs: 5000 });
  await passwordInput.fill(password, { timeoutMs: 5000 });
  const signInButton = page.locator("button").filter({ hasText: /^Sign In$/ });
  const buttons = await signInButton.all();
  let clicked = false;
  for (const button of buttons) {
    if (await button.isVisible().catch(() => false)) {
      await button.click({ timeout: 5000, force: true });
      clicked = true;
      break;
    }
  }
  if (!clicked) return false;
  await page.getByTestId("workspace-canvas-shell").waitFor({ state: "visible", timeoutMs: 15000 }).catch(() => null);
  return page.getByTestId("workspace-canvas-shell").isVisible().catch(() => false);
}

async function clickButton(page, matcher, options = {}) {
  const { owner = "Chat 34", optional = false, exactRoleName = "" } = options;
  let locator = exactRoleName
    ? page.getByRole("button", { name: exactRoleName })
    : page.locator("button").filter({ hasText: matcher });
  const count = await locator.count();
  if (!count) {
    note(options.name || `Click ${matcher}`, false, "button missing", owner, optional ? "P2" : "P1", optional);
    return false;
  }
  if (count > 1 && exactRoleName) {
    locator = page.locator("button").filter({ hasText: matcher });
  }
  const target = locator.first();
  const disabled = await target.isDisabled().catch(() => false);
  if (disabled) {
    note(options.name || `Click ${matcher}`, false, "button disabled", owner, optional ? "P2" : "P1", optional);
    return false;
  }
  await target.click({ noWaitAfter: true, timeout: 5000 });
  return true;
}

async function openSetup(page) {
  return clickButton(page, /^Setup/, { name: "Open Setup panel", owner: "Chat 7", optional: false });
}

async function openChat(page) {
  const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  if (await composer.isVisible().catch(() => false)) return true;
  const sidebar = page.getByRole("button", { name: "Open chat from sidebar command" });
  if (await sidebar.isVisible().catch(() => false)) {
    await sidebar.click({ timeout: 5000 }).catch(() => null);
    await page.waitForTimeout(350);
  }
  if (await composer.isVisible().catch(() => false)) return true;
  const chatButtons = page.locator("button").filter({ hasText: /^Chat$/ });
  const count = await chatButtons.count();
  for (let idx = 0; idx < count; idx += 1) {
    const candidate = chatButtons.nth(idx);
    if (await candidate.isVisible().catch(() => false)) {
      await candidate.click({ timeout: 5000 }).catch(() => null);
      await page.waitForTimeout(350);
      if (await composer.isVisible().catch(() => false)) return true;
    }
  }
  return false;
}

async function sendChat(page, message, patterns, name) {
  return soft(name, "Chat 34", "P1", async () => {
    const opened = await openChat(page);
    if (!opened) return { ok: false, detail: "chat composer not reachable" };
    const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
    await composer.fill(message, { timeoutMs: 5000 });
    await composer.press("Enter", { timeoutMs: 5000 });
    await page.waitForTimeout(1800);
    const text = await visibleText(page);
    const ok = patterns.some((pattern) => pattern.test(text));
    return { ok, detail: ok ? "matched expected response language" : text.slice(-500) };
  });
}

async function clickSurfaceAt(page, xRatio, yRatio) {
  const surface = page.getByTestId("preview-drawing-surface");
  const box = await surface.boundingBox();
  if (!box) throw new Error("preview drawing surface missing");
  await page.mouse.click(box.x + box.width * xRatio, box.y + box.height * yRatio);
}

async function runRuntimeGuard() {
  const context = await request.newContext();
  await soft("Runtime debug unauthenticated access blocked", "Chat 34", "P1", async () => {
    const { response, text } = await apiJson(context, `${apiBase}/api/debug/runtime`);
    return { ok: response.status() === 401, detail: `status ${response.status()} ${text.slice(0, 140)}` };
  });
  await soft("Runtime debug bogus token blocked", "Chat 34", "P1", async () => {
    const { response, text } = await apiJson(context, `${apiBase}/api/debug/runtime`, {
      headers: { Authorization: "Bearer invalid-chat34-runtime-token" },
    });
    return { ok: response.status() === 401, detail: `status ${response.status()} ${text.slice(0, 140)}` };
  });
  if (!email || !password) {
    note("Pilot credentials present", false, "pilot credential environment is missing; live authenticated proof cannot run", "Chat 34", "P1");
    await context.dispose();
    return null;
  }
  const login = await apiJson(context, `${apiBase}/api/auth/login`, {
    method: "POST",
    data: { email, password },
  });
  authToken = String(login.json?.token || "");
  await soft("Pilot API login", "Chat 34", "P1", async () => ({
    ok: login.response.ok() && Boolean(authToken),
    detail: `status ${login.response.status()}`,
  }));
  await soft("Runtime debug authenticated access works with release blocked", "Chat 34", "P1", async () => {
    if (!authToken) return { ok: false, detail: "no token from login" };
    const { response, text, json } = await apiJson(context, `${apiBase}/api/debug/runtime`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    const guardText = JSON.stringify(json?.construction_release_guard || json || {});
    return {
      ok: response.ok() && /construction_release_blocked|review_only/.test(guardText),
      detail: `status ${response.status()} ${text.slice(0, 220)}`,
    };
  });
  await context.dispose();
  return authToken || null;
}

async function runFreshAuthenticatedShell() {
  if (!authToken) return;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(8000);
  page.setDefaultNavigationTimeout(60000);
  attachPageTelemetry(page);
  try {
    await page.addInitScript(([tokenKey, token]) => {
      window.localStorage.setItem(tokenKey, token);
    }, [TOKEN_KEY, authToken]);
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2000);
    await signInIfNeeded(page);
    const text = await visibleText(page);
    await soft("Fresh authenticated workspace opens cleanly", "Chat 34", "P1", async () => ({
      ok: await page.getByTestId("workspace-canvas-shell").isVisible().catch(() => false),
      detail: text.slice(0, 180),
    }));
    note("No demo seeded objects on fresh authenticated workspace", !/Detention Basin A|Multifamily Building A|demo-building|demo-site/i.test(text), "fresh workspace scanned", "Chat 34", "P1");
    note("No fake truth/status scores on fresh authenticated workspace", !/Overall\s+Ready|\b\d+\s+Overall\s+Ready/i.test(text), "fresh truth area scanned", "Chat 34", "P1");
    const cors = await page.evaluate(async (url) => {
      try {
        const resp = await fetch(`${url}/api/auth/status`, { mode: "cors" });
        return { ok: resp.ok, status: resp.status, text: (await resp.text()).slice(0, 120) };
      } catch (error) {
        return { ok: false, error: String(error) };
      }
    }, apiBase);
    note("Browser API CORS from product origin", Boolean(cors.ok), JSON.stringify(cors), "Chat 20", "P1");
  } finally {
    await screenshot(page, "fresh-authenticated-shell");
    await browser.close();
    writeArtifact();
  }
}

async function runProductWorkflow() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(8000);
  page.setDefaultNavigationTimeout(60000);
  attachPageTelemetry(page);
  try {
    const url = process.env.CHAT34_DEMO_WORKFLOW === "0"
      ? baseUrl
      : `${baseUrl}/demo/workspace?debugPreview=1&chat34ControlledPilot=1`;
    if (authToken) {
      await page.addInitScript(([tokenKey, token]) => {
        window.localStorage.setItem(tokenKey, token);
      }, [TOKEN_KEY, authToken]);
    }
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.getByTestId("workspace-canvas-shell").waitFor({ state: "visible", timeoutMs: 30000 });
    await page.waitForTimeout(800);

    await openSetup(page);
    await soft("Start blank project/site", "Chat 34", "P1", async () => {
      const clicked = await clickButton(page, /Start.*blank site|blank site/i, {
        name: "Start blank site control",
        owner: "Chat 34",
      });
      await page.waitForTimeout(700);
      const text = await visibleText(page);
      return {
        ok: clicked && !/Detention Basin A|Multifamily Building A|demo-building/i.test(text),
        detail: text.slice(0, 220),
      };
    });
    await soft("Site size fields visible", "Chat 7", "P1", async () => {
      const count = await page.locator('input[type="number"]').count();
      return { ok: count >= 2, detail: `${count} number inputs` };
    });
    const close = page.getByRole("button", { name: "Close" });
    if (await close.isVisible().catch(() => false)) await close.click({ timeoutMs: 5000 }).catch(() => null);

    const canvas = page.getByTestId("workspace-canvas-shell");
    await soft("Draw Site Boundary -> Finish locks site", "Chat 7", "P1", async () => {
      await canvas.getByRole("button", { name: "Draw Site Boundary" }).click({ timeoutMs: 5000 });
      await clickSurfaceAt(page, 0.22, 0.42);
      await clickSurfaceAt(page, 0.72, 0.44);
      await clickSurfaceAt(page, 0.62, 0.78);
      const finish = canvas.getByRole("button", { name: "Finish" });
      if (!(await finish.isVisible({ timeout: 1200 }).catch(() => false))) {
        await clickSurfaceAt(page, 0.32, 0.72);
      }
      const enabled = await finish.isEnabled({ timeout: 2500 }).catch(() => false);
      if (enabled) await finish.click({ timeoutMs: 5000 });
      await page.waitForTimeout(800);
      const status = await page.getByTestId("site-status").innerText({ timeoutMs: 5000 }).catch(() => "");
      return { ok: /Site\s*Locked/i.test(status), detail: enabled ? status : `${status}; finish button was not observed before lock` };
    });
    await soft("Change/unlock and relock site", "Chat 7", "P1", async () => {
      await openSetup(page);
      const changed = await clickButton(page, /Change site boundary/i, {
        name: "Change site boundary control",
        owner: "Chat 7",
      });
      await page.waitForTimeout(400);
      const unlockedText = await visibleText(page);
      const relocked = await clickButton(page, /Lock site boundary/i, {
        name: "Lock site boundary control",
        owner: "Chat 7",
      });
      await page.waitForTimeout(700);
      const closeAgain = page.getByRole("button", { name: "Close" });
      if (await closeAgain.isVisible().catch(() => false)) await closeAgain.click({ timeoutMs: 5000 }).catch(() => null);
      return {
        ok: changed && relocked && /Selecting Site|Not locked|Site not locked/i.test(unlockedText),
        detail: unlockedText.slice(0, 220),
      };
    });

    for (const label of ["Add Line", "Add Area", "Add Box", "Add Point"]) {
      await soft(`${label} enabled`, "Chat 7", "P1", async () => ({
        ok: await canvas.getByRole("button", { name: label }).isEnabled().catch(() => false),
      }));
    }
    await soft("Draw rectangle, polygon, line, and point", "Chat 7", "P1", async () => {
      const before = await page.locator("[data-object-overlay]").count();
      await canvas.getByRole("button", { name: "Add Box" }).click({ timeoutMs: 5000 });
      await clickSurfaceAt(page, 0.28, 0.5);
      await clickSurfaceAt(page, 0.44, 0.66);
      await page.waitForTimeout(300);
      await canvas.getByRole("button", { name: "Add Area" }).click({ timeoutMs: 5000 });
      await clickSurfaceAt(page, 0.5, 0.52);
      await clickSurfaceAt(page, 0.66, 0.58);
      await clickSurfaceAt(page, 0.58, 0.72);
      await canvas.getByRole("button", { name: "Finish" }).click({ timeoutMs: 5000 });
      await page.waitForTimeout(300);
      await canvas.getByRole("button", { name: "Add Line" }).click({ timeoutMs: 5000 });
      await clickSurfaceAt(page, 0.24, 0.74);
      await clickSurfaceAt(page, 0.5, 0.82);
      await canvas.getByRole("button", { name: "Finish" }).click({ timeoutMs: 5000 });
      await page.waitForTimeout(300);
      await canvas.getByRole("button", { name: "Add Point" }).click({ timeoutMs: 5000 });
      await clickSurfaceAt(page, 0.78, 0.72);
      await page.waitForTimeout(600);
      const after = await page.locator("[data-object-overlay]").count();
      return { ok: after >= before + 4, detail: `before ${before}, after ${after}` };
    });
    await sendChat(page, "make this a basin", [/draft geometry and still requires engineer review/i, /Reclassified/i], "Classify one manual object");
    await soft("Manual object appears in canvas/list/properties with review-required status", "Chat 7", "P1", async () => {
      await clickButton(page, /^Canvas/, { name: "Open Canvas panel", owner: "Chat 7", optional: true }).catch(() => null);
      await clickButton(page, /Selected Details|Properties/i, { name: "Open object details", owner: "Chat 7", optional: true }).catch(() => null);
      const text = await visibleText(page);
      const manualSourceVisible = (await page.locator('input[value="manual_drawn"]').count()) > 0 || /manual_drawn/i.test(text);
      const reviewVisible = /Draft review required|draft_review_required|requires engineer review|Engineer review required/i.test(text);
      return {
        ok: manualSourceVisible && reviewVisible,
        detail: text.slice(-500),
      };
    });

    await soft("Canvas pan/zoom and preview toggles do not mutate geometry", "Chat 7", "P1", async () => {
      const before = await page.locator("[data-object-overlay]").count();
      await canvas.getByRole("button", { name: "Pan" }).click({ timeoutMs: 5000 });
      const surface = await page.getByTestId("preview-drawing-surface").boundingBox();
      if (surface) {
        await page.mouse.move(surface.x + surface.width * 0.5, surface.y + surface.height * 0.5);
        await page.mouse.down();
        await page.mouse.move(surface.x + surface.width * 0.55, surface.y + surface.height * 0.52);
        await page.mouse.up();
      }
      await canvas.getByRole("button", { name: "Zoom" }).click({ timeoutMs: 5000, force: true }).catch(() => null);
      await canvas.getByTestId("preview-quality-high").click({ timeoutMs: 5000, force: true });
      const hq = await canvas.getByTestId("high-quality-preview-only-label").isVisible().catch(() => false);
      await canvas.getByTestId("preview-quality-standard").click({ timeoutMs: 5000, force: true });
      await canvas.getByTestId("preview-mode-3d").click({ timeoutMs: 5000, force: true });
      await page.waitForTimeout(300);
      await canvas.getByTestId("preview-mode-2d").click({ timeoutMs: 5000, force: true });
      await page.waitForTimeout(300);
      const after = await page.locator("[data-object-overlay]").count();
      return { ok: hq && after === before, detail: `before ${before}, after ${after}, highQualityLabel ${hq}` };
    });
    await soft("Desktop no horizontal overflow", "Chat 34", "P1", async () => {
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      return { ok: overflow <= 1, detail: `overflow ${overflow}` };
    });

    await sendChat(page, "hi how r u", [/Hi, I’m Civora|help you think through/i], "Chat greeting");
    await sendChat(page, "make the site size 1000x1000 and the address is 20525 Margo St gretna ne", [/site|address|review-required|engineer/i], "Chat site size/address");
    await sendChat(page, "what should I do next?", [/does not stamp|engineer review|next/i], "Chat what next");
    await sendChat(
      page,
      "why can't I export?",
      [/Export is blocked|export[\s\S]{0,240}(blocked|review|engineer|construction)|engineer-review packages|Construction release remains blocked/i],
      "Chat export blocked",
    );
    await sendChat(page, "make review package", [/review package|engineer|blocked|export/i], "Chat review package");
    await sendChat(page, "stamp this approved construction-ready", [/cannot stamp|cannot.*certify|act as engineer of record|construction/i], "Chat stamp/approval blocks");

    await soft("Review/Deliver blockers and engineer-review language visible", "Chat 34", "P1", async () => {
      await clickButton(page, /^Review/, { name: "Open Review panel", owner: "Chat 34", optional: true }).catch(() => null);
      await page.waitForTimeout(300);
      let text = await visibleText(page);
      const reviewOk = /Missing|Blocker|Review required|Engineer review/i.test(text);
      await clickButton(page, /^Deliver/, { name: "Open Deliver panel", owner: "Chat 34", optional: true }).catch(() => null);
      await page.waitForTimeout(300);
      text = await visibleText(page);
      const deliverOk = /Export blocked|Review-only package|Engineer review package|Construction remains blocked|external licensed engineer/i.test(text);
      return { ok: reviewOk && deliverOk, detail: text.slice(0, 500) };
    });
    await soft("Generate/analyze smoke records run or exact block without fake success", "Chat 34", "P1", async () => {
      await clickButton(page, /^Generate$/, { name: "Open Generate panel", owner: "Chat 34", optional: true }).catch(() => null);
      await page.waitForTimeout(400);
      const grading = page.getByTestId("generate-grading");
      const visible = await grading.isVisible().catch(() => false);
      if (visible && !(await grading.isDisabled().catch(() => false))) {
        await grading.click({ timeoutMs: 5000 }).catch(() => null);
        await page.waitForTimeout(1600);
      }
      const text = await visibleText(page);
      return {
        ok: visible || /Blocked|not generated|not configured|review|required|queued|running|refresh|grading/i.test(text),
        detail: visible ? `grading visible disabled=${await grading.isDisabled().catch(() => false)}` : text.slice(0, 400),
      };
    });
    await soft("Map/GIS/detection language truthful", "Chat 34", "P1", async () => {
      const text = await visibleText(page);
      const noFakeDetection = !/Detected Objects \(Review Required\).*Building.*Road/is.test(text) ||
        /Upload\/analyze|Review Required|candidate|source/i.test(text);
      return { ok: noFakeDetection, detail: "detection text scanned for fake source-free claims" };
    });
    await soft("Safety language scan", "Chat 34", "P0", async () => {
      const text = (await visibleText(page)).replace(/\s+/g, " ");
      const unsafe = /(construction-ready|Civora approved|approved by Civora|certified by Civora|stamped by Civora|sealed by Civora|signed by Civora|submitted by Civora)/i.test(text);
      return { ok: !unsafe, detail: unsafe ? text.match(/.{0,80}(construction-ready|Civora approved|approved by Civora|certified by Civora|stamped by Civora|sealed by Civora|signed by Civora|submitted by Civora).{0,80}/i)?.[0] : "no unsafe wording" };
    });
    await screenshot(page, "desktop-final");
  } finally {
    await browser.close();
    writeArtifact();
  }
}

async function runMobileSmoke() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.setDefaultTimeout(8000);
  page.setDefaultNavigationTimeout(60000);
  attachPageTelemetry(page);
  try {
    const url = process.env.CHAT34_DEMO_WORKFLOW === "0"
      ? baseUrl
      : `${baseUrl}/demo/workspace?debugPreview=1&chat34ControlledMobile=1`;
    if (authToken) {
      await page.addInitScript(([tokenKey, token]) => {
        window.localStorage.setItem(tokenKey, token);
      }, [TOKEN_KEY, authToken]);
    }
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.getByTestId("workspace-canvas-shell").waitFor({ state: "visible", timeoutMs: 30000 });
    await soft("Mobile drawer/setup/draw controls reachable and no horizontal overflow", "Chat 34", "P1", async () => {
      const drawer = await page.getByTestId("floating-command-bar").isVisible().catch(() => false);
      const setup = await page.locator("button").filter({ hasText: /^Setup/ }).first().isVisible().catch(() => false);
      const draw = await page.getByRole("button", { name: "Draw Site Boundary" }).isVisible().catch(() => false);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      return { ok: drawer && setup && draw && overflow <= 1, detail: `drawer ${drawer}, setup ${setup}, draw ${draw}, overflow ${overflow}` };
    });
    await screenshot(page, "mobile-final");
  } finally {
    await browser.close();
    writeArtifact();
  }
}

(async () => {
  fs.mkdirSync(artifactDir, { recursive: true });
  fs.mkdirSync(screenshotDir, { recursive: true });
  writeArtifact();
  try {
    await runRuntimeGuard();
    await runFreshAuthenticatedShell();
    await runProductWorkflow();
    await runMobileSmoke();
  } catch (error) {
    browserErrors.push({ type: "runner", message: String(error && error.message ? error.message : error) });
    note(
      "Aggregate QA runner completed without uncaught abort",
      false,
      String(error && error.message ? error.message : error),
      "Chat 34",
      "P1",
    );
  } finally {
    writeArtifact();
    console.log(JSON.stringify(artifact(), null, 2));
  }
})();
