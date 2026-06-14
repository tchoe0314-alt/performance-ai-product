import { rm } from "node:fs/promises";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");
const buildCheckDir = resolve(process.cwd(), ".next-build-check");
const releaseRegressionDir = resolve(process.cwd(), ".next-release-regression");

await rm(nextDir, { force: true, recursive: true });
await rm(buildCheckDir, { force: true, recursive: true });
await rm(releaseRegressionDir, { force: true, recursive: true });
