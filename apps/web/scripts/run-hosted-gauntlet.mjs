#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const appUrl = process.env.PLAYWRIGHT_BASE_URL || "https://civoraai.com";
const hasHostedCredentials = Boolean(process.env.CIVORA_EMAIL && process.env.CIVORA_PASSWORD);

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

if (hasHostedCredentials) {
  authStatus = run("authenticated hosted smoke", [
    "playwright",
    "test",
    "--config=playwright.config.ts",
    "tests/live/hosted-auth-smoke.spec.ts",
    "--project=chromium",
    "--workers=1",
  ]);
  authSummary = authStatus === 0 ? "passed" : "failed";
}

console.log("\n[hosted-gauntlet] summary");
console.log(`- target: ${appUrl}`);
console.log(`- public smoke: ${publicStatus === 0 ? "passed" : "failed"}`);
console.log(`- authenticated smoke: ${authSummary}`);

if (publicStatus !== 0 || authStatus !== 0) {
  process.exit(1);
}
