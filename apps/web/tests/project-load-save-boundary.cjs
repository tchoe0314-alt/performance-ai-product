// Actual load hook, deterministic owned promises; no database/network/timers.
(async () => {
  const { default: assert } = await import("node:assert/strict");
  const { default: fs } = await import("node:fs");
  const { default: ts } = await import("typescript");
  const { default: vm } = await import("node:vm");
  const flush = () => new Promise(resolve => setImmediate(resolve));
  const gate = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
  function fixture({ token = "synthetic-only", wait } = {}) {
    const pending = gate(), requests = [], applied = [], statuses = [];
    const refs = { current: 0 };
    let revision = "before-save";
    const exports = {};
    const code = ts.transpileModule(fs.readFileSync(`${__dirname}/../app/hooks/useDashboardProjectLoad.ts`, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    vm.runInNewContext(code, { exports, Error, window: { clearTimeout() {}, localStorage: { setItem() {} }, sessionStorage: { setItem() {} } },
      require(name) {
        if (name === "react") return { useCallback: value => value, useEffect() {} };
        if (name === "../../lib/api") return { getJson: async path => { requests.push(path); return { project: { project_id: path.split("/").at(-1), revision_token: revision, project_input: {} } }; } };
        if (name.endsWith("performanceProbes")) return { markCivoraInteraction() {}, measureCivoraInteractionAfterPaint() {} };
        if (name.endsWith("workflowConstants")) return { ACTIVE_PROJECT_STORAGE_KEY: "fixture-active" };
        if (name.endsWith("canonicalCanvasProject")) return { resolveCanonicalCanvasInput: value => value };
        if (name.endsWith("editTransactions")) return { validateLedger() {} };
        throw Error(`Unexpected import ${name}`);
      },
    });
    const ref = value => ({ current: value });
    const noop = () => {};
    const action = exports.useDashboardProjectLoad({ token, projectId: "original", currentProject: null,
      effectiveDemoWorkspaceEnabled: false, activeJobId: "", cancelPendingRun: noop,
      waitForPendingProjectSaves: wait ?? (id => id === "original" ? pending.promise : Promise.resolve()),
      autosaveSuspendRef: ref(false), chatAutosaveTimeoutRef: ref(null), controlAutosaveTimeoutRef: ref(null),
      projectLoadRequestRef: refs, restoredActiveProjectRef: ref(false), resolvedProjectIdRef: ref("original"),
      loadJobRef: ref(null), loadProjectResultInBackgroundRef: ref(null), resetWorkspaceStateRef: ref(noop),
      suppressProjectAutoLoadRef: ref(false), applyProjectInput: noop, setCurrentProject: value => applied.push(value),
      setProjectId: noop, setSiteName: noop, setBackendResult: noop, setIssues: noop, setPlanPreviewUrl: noop,
      setPlanPreviewSummary: noop, setProjectDrawerNotice: noop, setWorkspaceRestoreState: noop,
      updateProjectStatus: value => statuses.push(value),
    });
    return { ...action, pending, requests, applied, statuses, commit: () => { revision = "after-save"; pending.resolve(); } };
  }
  const cases = [
    ["reopening waits for an in-flight save, then reads its accepted revision", async () => {
      const f = fixture(); const opened = f.loadProject("original"); await flush();
      assert.equal(f.requests.length, 0, "Must not fetch a soon-stale project before the pending save commits");
      f.commit(); await opened; assert.deepEqual(f.requests, ["/api/projects/original"]);
      assert.equal(f.applied[0].revision_token, "after-save");
    }],
    ["superseded waiting load cannot fetch or publish the previous project", async () => {
      const f = fixture(); const first = f.loadProject("original"); await flush();
      await f.loadProject("other"); f.commit(); await first;
      assert.deepEqual(f.requests, ["/api/projects/other"]);
      assert.deepEqual(f.applied.map(item => item.project_id), ["other"]);
    }],
    ["failed save boundary does not fetch or publish a false restored state", async () => {
      const f = fixture({ wait: async () => { throw Error("Synthetic save boundary failure"); } });
      await f.loadProject("original"); assert.deepEqual(f.requests, []); assert.deepEqual(f.applied, []);
      assert.equal(f.statuses.at(-1).state, "blocked");
    }],
    ["signed-out load cannot wait on or read another identity's project", async () => {
      let waits = 0; const f = fixture({ token: null, wait: async () => { waits++; } });
      await f.loadProject("original"); assert.equal(waits, 0); assert.deepEqual(f.requests, []);
    }],
  ];
  let failures = 0;
  for (const [name, run] of cases) { try { await run(); console.log(`PASS ${name}`); } catch (error) { failures++; console.error(`FAIL ${name}: ${error.message}`); } }
  process.exitCode = failures ? 1 : 0;
})().catch(error => { console.error(error); process.exitCode = 1; });
