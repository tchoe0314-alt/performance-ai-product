import { rm } from "node:fs/promises";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");
const releaseRegressionDir = resolve(process.cwd(), ".next-release-regression");

await rm(nextDir, { force: true, recursive: true });
await rm(releaseRegressionDir, { force: true, recursive: true });
