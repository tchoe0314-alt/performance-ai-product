// Offline behavioral test of the actual UI action; no browser/server or API calls.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const vm = require("node:vm");
const filename = path.resolve(__dirname, "../app/utils/dashboardReviewWorkflowActions.ts");
const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const requests = [];
let fail = false;
const exportsObject = {};
vm.runInNewContext(compiled, {
  exports: exportsObject,
  require(name) {
    assert.equal(name, "../../lib/api");
    return { postJson: async (url, body) => {
      requests.push({ url, body });
      if (fail) throw new Error("Project changed. Reload before reviewing.");
      return { success: true };
    }};
  },
  Error,
});
(async () => {
  const statuses = [];
  let updates = 0;
  const base = { action: "accept", candidateIds: "b1", siteScaleLocked: false,
    projectId: "p1", token: "offline-fake", setCurrentProject: () => updates++,
    setBackendResult: () => updates++, setStatusMessage: value => statuses.push(value) };
  for (const currentProject of [null, { project_id: "p1" },
    { project_id: "another", revision_token: "a".repeat(64) }]) {
    assert.equal(await exportsObject.runDashboardCandidateReviewDecision({ ...base, currentProject }), null);
  }
  assert.equal(requests.length, 0);
  const currentProject = { project_id: "p1", revision_token: "b".repeat(64) };
  fail = true;
  assert.equal(await exportsObject.runDashboardCandidateReviewDecision({ ...base, currentProject }), null);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].body.expected_revision, currentProject.revision_token);
  assert.equal(updates, 0);
  assert.match(statuses.at(-1), /Reload/);
  console.log("PASS: missing/mismatched snapshots blocked; source token sent; conflict preserves state");
})().catch(error => { console.error(error); process.exitCode = 1; });
