#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const appUrl = process.env.PLAYWRIGHT_BASE_URL || "https://civoraai.com";
const hasHostedCredentials = Boolean(process.env.CIVORA_EMAIL && process.env.CIVORA_PASSWORD);
const reportPath = resolve(process.env.HOSTED_GAUNTLET_REPORT || "playwright-artifacts/hosted-gauntlet-report.json");
const requestedAuthenticatedRepeats = Number.parseInt(process.env.CIVORA_HOSTED_AUTH_REPEAT_COUNT || "2", 10);
const authenticatedRepeatCount = Math.max(2, Math.min(Number.isFinite(requestedAuthenticatedRepeats) ? requestedAuthenticatedRepeats : 2, 5));

const run = (label, args, extraEnv = {}) => {
  console.log(`\n[hosted-gauntlet] ${label}`);
  const result = spawnSync("npx", args, {
    cwd: process.cwd(),
    env: {
      ...process.env,
      PLAYWRIGHT_SKIP_WEBSERVER: "1",
      PLAYWRIGHT_BASE_URL: appUrl,
      ...extraEnv,
    },
    stdio: "inherit",
  });
  return result.status ?? 1;
};

const publicStatus = run("public workspace smoke", [
  "playwright",
  "test",
  "--config=playwright.config.ts",
  "tests/live/hosted-public-workspace-smoke.spec.ts",
  "--project=chromium",
  "--workers=1",
]);

let authStatus = 0;
let authSummary = "skipped: CIVORA_EMAIL and CIVORA_PASSWORD are not set";
let authSkipped = true;

if (hasHostedCredentials) {
  authSkipped = false;
  authStatus = run("authenticated hosted smoke", [
    "playwright",
    "test",
    "--config=playwright.config.ts",
    "tests/live/hosted-auth-smoke.spec.ts",
    "--project=chromium",
    "--workers=1",
    `--repeat-each=${authenticatedRepeatCount}`,
  ]);
  authSummary = authStatus === 0 ? "passed" : "failed";
}

const report = {
  version: "hosted_gauntlet_report_v1",
  generated_at: new Date().toISOString(),
  target_url: appUrl,
  public_smoke: {
    status: publicStatus === 0 ? "passed" : "failed",
    command: "playwright test --config=playwright.config.ts tests/live/hosted-public-workspace-smoke.spec.ts --project=chromium --workers=1",
  },
  authenticated_smoke: {
    status: authSkipped ? "skipped" : authStatus === 0 ? "passed" : "failed",
    skipped_reason: authSkipped ? "CIVORA_EMAIL and CIVORA_PASSWORD are not set" : null,
    repeat_count: authenticatedRepeatCount,
    passed_runs: !authSkipped && authStatus === 0 ? authenticatedRepeatCount : 0,
    command: `playwright test --config=playwright.config.ts tests/live/hosted-auth-smoke.spec.ts --project=chromium --workers=1 --repeat-each=${authenticatedRepeatCount}`,
  },
  credentials_present: hasHostedCredentials,
  truth_label: "Hosted gauntlet reports public/authenticated website workflow health only. It does not prove construction readiness, professional approval, stamping, sealing, signing, certification, submission, or engineer-of-record status.",
};

mkdirSync(dirname(reportPath), { recursive: true });
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);

console.log("\n[hosted-gauntlet] summary");
console.log(`- target: ${appUrl}`);
console.log(`- public smoke: ${publicStatus === 0 ? "passed" : "failed"}`);
console.log(`- authenticated smoke: ${authSummary}`);
console.log(`- authenticated repeat target: ${authenticatedRepeatCount}`);
console.log(`- report: ${reportPath}`);

if (publicStatus !== 0 || authStatus !== 0) {
  process.exit(1);
}
