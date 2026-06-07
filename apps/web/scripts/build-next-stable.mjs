import { spawn } from "node:child_process";
import { rm } from "node:fs/promises";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");
const generatedArtifactPattern = /\.next\/(?:dev\/)?(?:server\/)?(?:pages-manifest|routes-manifest|build-manifest|app-build-manifest)\.json/;

async function run(command, args) {
  return new Promise((resolveRun) => {
    let combined = "";
    const child = spawn(command, args, {
      env: process.env,
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

for (let attempt = 1; attempt <= 2; attempt += 1) {
  const result = await run("next", ["build", "--webpack"]);
  if (result.code === 0) {
    process.exit(0);
  }

  const canRetry =
    attempt === 1 &&
    result.output.includes("ENOENT") &&
    generatedArtifactPattern.test(result.output);

  if (!canRetry) {
    process.exit(result.code);
  }

  console.warn("[build-next-stable] Generated Next artifact was missing during build; cleaning .next and retrying once.");
  await rm(nextDir, { force: true, recursive: true });
}

process.exit(1);
