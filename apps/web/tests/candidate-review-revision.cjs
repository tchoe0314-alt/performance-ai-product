// Offline behavioral test of the actual UI action; no browser/server or API calls.
(async () => {
const { default: assert } = await import("node:assert/strict");
const { default: fs } = await import("node:fs");
const { default: path } = await import("node:path");
const { default: ts } = await import("typescript");
const { default: vm } = await import("node:vm");
const filename = path.resolve(__dirname, "../app/utils/dashboardReviewWorkflowActions.ts");
const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const requests = [];
let fail = false;
const exportsObject = {};
const inboxExports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(__dirname,
  "../app/utils/reviewWorkflowData.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: inboxExports });
vm.runInNewContext(compiled, {
  exports: exportsObject,
  require(name) {
    if (name === "./reviewWorkflowData") return inboxExports;
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
    displayedInbox: { candidates: [{ candidate_id: "b1", source: "survey A", confidence: 0.9 }] },
    projectId: "p1", token: "offline-fake", setCurrentProject: () => updates++,
    setBackendResult: () => updates++, setStatusMessage: value => statuses.push(value) };
  for (const currentProject of [null, { project_id: "p1" },
    { project_id: "another", revision_token: "a".repeat(64) }]) {
    assert.equal(await exportsObject.runDashboardCandidateReviewDecision({ ...base, currentProject }), null);
  }
  assert.equal(requests.length, 0);
  const savedInbox = { candidates: [{ confidence: 0.9, source: "survey A", candidate_id: "b1" }] };
  const currentProject = { project_id: "p1", revision_token: "b".repeat(64),
    project_input: { meta: { site_inputs: { candidate_review_inbox_v1: savedInbox } } } };
  for (const displayedInbox of [
    { candidates: [] },
    { candidates: [{ candidate_id: "b1", source: "survey B", confidence: 0.9 }] },
    { candidates: [{ candidate_id: "b1", source: "survey A", confidence: 0.1 }] },
    { candidates: [...savedInbox.candidates, ...savedInbox.candidates] },
  ]) {
    assert.equal(await exportsObject.runDashboardCandidateReviewDecision({ ...base, currentProject, displayedInbox }), null);
  }
  assert.equal(requests.length, 0);
  fail = true;
  assert.equal(await exportsObject.runDashboardCandidateReviewDecision({ ...base, currentProject }), null);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].body.expected_revision, currentProject.revision_token);
  assert.equal(updates, 0);
  assert.match(statuses.at(-1), /Reload/);
  console.log("PASS: missing/mismatched projects and candidate evidence blocked; equivalent fields accepted; source token sent; conflict preserves state");
})().catch(error => { console.error(error); process.exitCode = 1; });
})().catch(error => { console.error(error); process.exitCode = 1; });
