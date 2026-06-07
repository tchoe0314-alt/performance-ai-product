import { rm } from "node:fs/promises";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");

await rm(nextDir, { force: true, recursive: true });
