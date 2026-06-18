import { spawn } from "node:child_process";
import { access, readFile, rename, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const distDir = process.env.NEXT_DIST_DIR || ".next";
const nextDir = resolve(process.cwd(), distDir);
const defaultNextDir = resolve(process.cwd(), ".next");
const tsconfigPath = resolve(process.cwd(), "tsconfig.json");
const generatedArtifactPattern =
  /(?:^|\/)\.next(?:[^/]*)\/(?:dev\/)?(?:server\/)?(?:pages-manifest|routes-manifest|build-manifest|app-build-manifest|required-server-files|export-detail)\.json/;
const generatedNextJsonPattern = /(?:^|\/)\.next(?:[^/]*)\/.*\.json/;
const generatedPageModulePattern =
  /(?:PageNotFoundError|Cannot find module for page:|Failed to collect page data for|Could not find a production build|next-export-no-build-id)/;
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

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function normalizeDistDir() {
  if (nextDir === defaultNextDir || !(await exists(defaultNextDir)) || (await exists(nextDir))) {
    return;
  }
  await rm(nextDir, { force: true, recursive: true });
  await rename(defaultNextDir, nextDir);
}

async function readTsconfigSnapshot() {
  try {
    return await readFile(tsconfigPath, "utf8");
  } catch {
    return null;
  }
}

async function restoreTsconfigSnapshot(snapshot) {
  if (snapshot === null) {
    return;
  }
  try {
    const current = await readFile(tsconfigPath, "utf8");
    if (current !== snapshot) {
      await writeFile(tsconfigPath, snapshot);
    }
  } catch {
    await writeFile(tsconfigPath, snapshot);
  }
}

const tsconfigSnapshot = await readTsconfigSnapshot();

for (let attempt = 1; attempt <= 3; attempt += 1) {
  const result = await run("next", ["build", "--webpack"]);
  if (result.code === 0) {
    await normalizeDistDir();
    await restoreTsconfigSnapshot(tsconfigSnapshot);
    process.exit(0);
  }

  const canRetry =
    attempt < 3 &&
    ((result.output.includes("ENOENT") && generatedArtifactPattern.test(result.output)) ||
      (result.output.includes("ENOENT") && generatedNextJsonPattern.test(result.output)) ||
      generatedPageModulePattern.test(result.output));

  if (!canRetry) {
    await restoreTsconfigSnapshot(tsconfigSnapshot);
    process.exit(result.code);
  }

  if (attempt === 1) {
    console.warn("[build-next-stable] Generated Next artifact was missing during build; cleaning .next and retrying.");
    await rm(nextDir, { force: true, recursive: true });
  } else {
    console.warn("[build-next-stable] Generated Next artifact was missing again; retrying once with warmed artifacts.");
  }
}

await restoreTsconfigSnapshot(tsconfigSnapshot);
process.exit(1);
