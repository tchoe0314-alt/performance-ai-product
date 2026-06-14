import { spawn } from "node:child_process";
import { rm } from "node:fs/promises";
import { resolve } from "node:path";

const distDir = process.env.NEXT_DIST_DIR || ".next";
const nextDir = resolve(process.cwd(), distDir);
const generatedArtifactPattern =
  /(?:^|\/)\.next(?:[^/]*)\/(?:dev\/)?(?:server\/)?(?:pages-manifest|routes-manifest|build-manifest|app-build-manifest|required-server-files|export-detail)\.json/;
const generatedNextJsonPattern = /(?:^|\/)\.next(?:[^/]*)\/.*\.json/;
const generatedPageModulePattern =
  /(?:PageNotFoundError|Cannot find module for page:|Failed to collect page data for)/;
const buildEnv = {
  ...process.env,
  NEXT_PRODUCTION_BROWSER_SOURCE_MAPS: process.env.NEXT_PRODUCTION_BROWSER_SOURCE_MAPS ?? "0",
  NODE_OPTIONS: process.env.NODE_OPTIONS ?? "--max-old-space-size=8192",
};

async function run(command, args) {
  return new Promise((resolveRun) => {
    let combined = "";
    const child = spawn(command, args, {
      env: buildEnv,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });

    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      combined += text;
      process.stdout.write(text);
    });
    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      combined += text;
      process.stderr.write(text);
    });
    child.on("close", (code, signal) => resolveRun({ code: code ?? 1, signal, output: combined }));
  });
}

for (let attempt = 1; attempt <= 3; attempt += 1) {
  const result = await run("next", ["build", "--webpack"]);
  if (result.code === 0) {
    process.exit(0);
  }

  const canRetry =
    attempt < 3 &&
    ((result.output.includes("ENOENT") && generatedArtifactPattern.test(result.output)) ||
      (result.output.includes("ENOENT") && generatedNextJsonPattern.test(result.output)) ||
      generatedPageModulePattern.test(result.output));

  if (!canRetry) {
    process.exit(result.code);
  }

  if (attempt === 1) {
    console.warn("[build-next-stable] Generated Next artifact was missing during build; cleaning .next and retrying.");
    await rm(nextDir, { force: true, recursive: true });
  } else {
    console.warn("[build-next-stable] Generated Next artifact was missing again; retrying once with warmed artifacts.");
  }
}

process.exit(1);
