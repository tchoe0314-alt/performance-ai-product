import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const shouldUseManagedLocalServer =
  !process.env.PLAYWRIGHT_BASE_URL && process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const requestedBackendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT || 0);
const managedBackendPort =
  Number.isInteger(requestedBackendPort) && requestedBackendPort > 0
    ? requestedBackendPort
    : 18_000 + (process.pid % 10_000);
const managedBackendBaseURL = `http://127.0.0.1:${managedBackendPort}`;
if (shouldUseManagedLocalServer) {
  process.env.PLAYWRIGHT_BACKEND_PORT = String(managedBackendPort);
  process.env.PLAYWRIGHT_API_BASE_URL = managedBackendBaseURL;
  process.env.NEXT_PUBLIC_API_BASE_URL = managedBackendBaseURL;
}
const managedBackendStorage = path.join("/tmp", `civora-playwright-${process.pid}`);
const outputDir =
  process.env.PLAYWRIGHT_OUTPUT_DIR ||
  path.join("test-results", `run-${process.pid}`);

// Keep the default device smoke scope; explicitly opt into existing workflow
// suites when verifying Phase 0 across browser engines and touch viewports.
const deviceTestMatch = process.env.CIVORA_PRODUCTION_SAFE_TESTS === "1"
  ? /hosted-current-backend-safe\.spec\.ts/
  : process.env.CIVORA_PHASE0_CROSS_BROWSER === "1"
  ? /(?:rc1-accessibility-cross-browser|project-object-integration|canonical-edit-command-foundation|dense-commercial-concept-chat240|preview-realism-truth-chat234|phase0-concept-replacement|phase0-local-persistence|phase0-local-export-download|drawn-boundary-finish|undo-recovery-history-chat231b|video-website-regression)\.spec\.ts/
  : /rc1-accessibility-cross-browser\.spec\.ts/;

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
          command: `cd ../.. && python3 -m uvicorn backend.api.app:app --host 127.0.0.1 --port ${managedBackendPort}`,
          url: `${managedBackendBaseURL}/api/health`,
          env: {
            ...process.env,
            CIVORA_PRODUCT_MODE: "private_alpha",
            CIVORA_ALLOW_LOCAL_PILOT_CORS: "1",
            CIVORA_LOCAL_PILOT_CORS_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000",
            CORS_ALLOW_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000",
            CIVORA_PUBLIC_API_BASE_URL: managedBackendBaseURL,
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
          env: {
            ...process.env,
            NEXT_PUBLIC_API_BASE_URL: managedBackendBaseURL,
          },
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
    {
      name: "firefox",
      testMatch: deviceTestMatch,
      use: {
        ...devices["Desktop Firefox"],
      },
    },
    {
      name: "webkit",
      testMatch: deviceTestMatch,
      use: {
        ...devices["Desktop Safari"],
      },
    },
    {
      name: "mobile-chromium",
      testMatch: deviceTestMatch,
      use: {
        ...devices["Pixel 7"],
      },
    },
    {
      name: "mobile-webkit",
      testMatch: deviceTestMatch,
      use: {
        ...devices["iPhone 15"],
      },
    },
  ],
});
