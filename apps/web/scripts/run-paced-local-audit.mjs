import { readFile, writeFile } from "node:fs/promises";
import { execFileSync, spawn } from "node:child_process";

for (const name of ["PLAYWRIGHT_BASE_URL", "PLAYWRIGHT_API_BASE_URL"]) {
  const url = new URL(process.env[name] ?? "http://invalid");
  if (url.protocol !== "http:" || !["localhost", "127.0.0.1"].includes(url.hostname) || !url.port) {
    throw new Error("Paced account regressions require disposable localhost services.");
  }
}
const artifactRoot = process.argv[2];
if (!artifactRoot?.startsWith("/tmp/civora-full-browser-")) throw new Error("Expected this audit's temporary artifacts.");
const files = execFileSync("rg", ["--files", artifactRoot], { encoding: "utf8" }).trim().split("\n");
const cases = [];
for (const file of files.filter(file => file.endsWith("/error-context.md"))) {
  const text = await readFile(file, "utf8");
  const title = text.match(/^- Name: (phase[12]-[^\n]+\.spec\.ts) >> (.+)$/m);
  const details = text.split("# Error details")[1]?.split("# Page snapshot")[0]?.split("# Test source")[0] ?? "";
  if (title && /Expected: 200\s+Received: (?:429|401)/.test(details)) cases.push({ file: title[1], title: title[2] });
}
cases.sort((a, b) => a.file.localeCompare(b.file) || a.title.localeCompare(b.title));
if (!cases.length) throw new Error("No throttled account regressions found; refusing an empty success.");
console.log(`Rechecking ${cases.length} account regressions without disabling or resetting rate limits.`);
const results = [];
const pause = () => new Promise(resolve => setTimeout(resolve, 35_000));
const waitPid = Number(process.env.CIVORA_AUDIT_WAIT_PID ?? 0);
if (waitPid) {
  if (!Number.isSafeInteger(waitPid) || waitPid <= 1) throw new Error("Invalid audit process id.");
  console.log("Waiting for the complete browser run to finish before sharing its authentication quota.");
  for (;;) {
    try { process.kill(waitPid, 0); } catch (error) { if (error.code === "ESRCH") break; throw error; }
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}
await pause();
for (const [index, entry] of cases.entries()) {
  console.log(`Paced ${index + 1}/${cases.length}: ${entry.file} — ${entry.title}`);
  const pattern = entry.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const code = await new Promise((resolve, reject) => {
    const child = spawn("npx", ["playwright", "test", `tests/live/${entry.file}`, "--config=playwright.full-audit.config.ts", "--grep", pattern, "--workers=1", "--reporter=list"], {
      stdio: "inherit", env: { ...process.env, PLAYWRIGHT_OUTPUT_DIR: `/tmp/civora-paced-account-audit-20261014/${index}` },
    });
    child.once("error", reject); child.once("exit", code => resolve(code ?? 1));
  });
  results.push({ ...entry, exitCode: code });
  await writeFile("/tmp/civora-paced-account-audit-20261014.json", JSON.stringify({ complete: results.length === cases.length, results }, null, 2));
  if (index < cases.length - 1) await pause();
}
process.exitCode = results.some(result => result.exitCode !== 0) ? 1 : 0;
