import config from "./playwright.config";
import { defineConfig } from "@playwright/test";

for (const name of ["PLAYWRIGHT_BASE_URL", "PLAYWRIGHT_API_BASE_URL"] as const) {
  const url = new URL(process.env[name] ?? "http://invalid");
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname) || !url.port) {
    throw new Error("The full audit is restricted to explicit disposable localhost services.");
  }
}

// Keep the complete desktop suite, but avoid multi-gigabyte credential/video
// artifacts on this disk-constrained workstation. Failures retain screenshots.
export default defineConfig({
  ...config,
  reporter: [["list"], ["junit", { outputFile: "/tmp/civora-full-browser-20261014.xml" }]],
  use: { ...config.use, video: "off", trace: "off" },
  projects: config.projects?.filter(project => project.name === "chromium"),
});
