import { readdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");
const buildCheckDir = resolve(process.cwd(), ".next-build-check");
const releaseRegressionDir = resolve(process.cwd(), ".next-release-regression");

await rm(nextDir, { force: true, recursive: true });
await rm(buildCheckDir, { force: true, recursive: true });
await rm(releaseRegressionDir, { force: true, recursive: true });

const entries = await readdir(process.cwd(), { withFileTypes: true });
await Promise.all(
  entries
    .filter((entry) => entry.isDirectory() && (entry.name === ".next-dev" || entry.name.startsWith(".next-release-regression-")))
    .map((entry) => rm(resolve(process.cwd(), entry.name), { force: true, recursive: true })),
);
