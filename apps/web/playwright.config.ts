import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const shouldUseManagedLocalServer =
  !process.env.PLAYWRIGHT_BASE_URL && process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const managedBackendStorage = path.join("/tmp", `civora-playwright-${process.pid}`);
const outputDir =
  process.env.PLAYWRIGHT_OUTPUT_DIR ||
  path.join("test-results", `run-${process.pid}`);

export default defineConfig({
  testDir: "./tests/live",
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir,
  webServer: shouldUseManagedLocalServer
    ? [
        {
          command: "cd ../.. && python3 -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8002",
          url: "http://127.0.0.1:8002/api/health",
          env: {
            ...process.env,
            CIVORA_PRODUCT_MODE: "private_alpha",
            CIVORA_ALLOW_LOCAL_PILOT_CORS: "1",
            CIVORA_LOCAL_PILOT_CORS_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000",
            CORS_ALLOW_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000",
            PERFORMANCE_AI_STORAGE_DIR: managedBackendStorage,
          },
          timeout: 120_000,
          reuseExistingServer: false,
          stdout: "pipe",
          stderr: "pipe",
        },
        {
          command: "npm run serve:test",
          url: baseURL,
          timeout: 240_000,
          reuseExistingServer: false,
          stdout: "pipe",
          stderr: "pipe",
        },
      ]
    : undefined,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1440, height: 1100 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
