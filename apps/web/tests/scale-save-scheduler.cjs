// Actual scheduler with deterministic timers and owned snapshots; no network.
(async () => {
  const { default: assert } = await import("node:assert/strict");
  const { default: fs } = await import("node:fs");
  const { default: ts } = await import("typescript");
  const { default: vm } = await import("node:vm");
  const { default: path } = await import("node:path");
  const modules = new Map();
  function loadUtility(filename) {
    filename = path.resolve(filename);
    if (filename.endsWith(".json")) return JSON.parse(fs.readFileSync(filename,"utf8"));
    if (!path.extname(filename)) filename += ".ts";
    if (modules.has(filename)) return modules.get(filename);
    const exports = {}; modules.set(filename,exports);
    const code=ts.transpileModule(fs.readFileSync(filename,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText;
    // Pure utility modules share the ordinary JS realm, as in the browser;
    // cross-realm Object prototypes would falsely fail strict JSON validation.
    vm.runInThisContext(`(function(exports,require){${code}\n})`,{filename})(exports,name=>{
      if(!name.startsWith("."))throw Error(`Unexpected utility import ${name}`);
      return loadUtility(path.resolve(path.dirname(filename),name));
    });
    return exports;
  }
  const canonical=loadUtility(`${__dirname}/../app/utils/canonicalCanvasProject.ts`);
  function fixture({ fail = false, savedScale, savedLocked = false, feet = "", pixels = "" } = {}) {
    const timers = new Map(), calls = []; let sequence = 0;
    const exports = {};
    const code = ts.transpileModule(fs.readFileSync(`${__dirname}/../app/hooks/useDashboardScaleSaveScheduler.ts`, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    vm.runInNewContext(code, { exports, Number, window: {
      setTimeout: callback => { timers.set(++sequence, callback); return sequence; },
      clearTimeout: id => timers.delete(id),
    }, require(name) {
      if (name === "react") return { useCallback: value => value };
      if (name.endsWith("formatting")) return { parsePositiveNumber: value => Number(value) > 0 ? Number(value) : null };
      if (name.endsWith("canonicalCanvasProject")) return canonical;
      throw Error(`Unexpected import ${name}`);
    } });
    const ref = current => ({ current });
    const input = { manual_fields: { units: "ft", site_objects: [{ id: "building", x: 125 }] },
      meta: { site_inputs: { detection_scale: savedScale, site_alignment_locked: savedLocked, source_note: "preserve" } } };
    const project = ref({ project_id: "owned", project_input: structuredClone(input) });
    const payload = ref(structuredClone(input));
    const generation = ref(1), identity = ref("owned"), locked = ref(false);
    const save = ref(async request => { calls.push(structuredClone(request));
      if (fail) return null;
      project.current = { ...project.current, project_input: structuredClone(request.projectInputOverride) };
      return project.current;
    });
    const schedule = exports.useDashboardScaleSaveScheduler({ currentProjectRef: project,
      payloadPreviewRef: payload, projectLoadRequestRef: generation, resolvedProjectIdRef: identity,
      saveProjectRef: save, scaleSaveTimeoutRef: ref(null), siteScaleLockedRef: locked,
      detectionScaleFeet: feet, detectionScalePixels: pixels });
    const tick = async () => { for (const [id, callback] of [...timers]) { timers.delete(id); callback(); } await Promise.resolve(); };
    return { schedule, calls, tick, project, payload, generation, identity, locked, timers };
  }
  const scale = { scale_ft_per_px: 2.5, scale_source: "mapbox" };
  const cases = [
    ["unchanged persisted scale never schedules another project write", async () => {
      const f = fixture({ savedScale: scale }); f.schedule(2.5,"mapbox"); await f.tick(); assert.equal(f.calls.length,0);
    }],
    ["same map scale after acknowledgement does not create a save/render feedback loop", async () => {
      const f = fixture(); f.schedule(2.5,"mapbox"); await f.tick();
      for(let i=0;i<5;i++){ f.schedule(2.5,"mapbox"); await f.tick(); }
      assert.equal(f.calls.length,1);
    }],
    ["pending scale save preserves newer live geometry and unrelated source provenance", async () => {
      const f = fixture(); f.schedule(2.5,"mapbox"); f.payload.current.manual_fields.site_objects[0].x=225; await f.tick();
      assert.equal(f.calls[0].projectInputOverride.manual_fields.site_objects[0].x,225);
      assert.equal(f.calls[0].projectInputOverride.meta.site_inputs.source_note,"preserve");
    }],
    ["failed save remains retryable", async () => {
      const f = fixture({fail:true}); f.schedule(2.5,"mapbox"); await f.tick(); f.schedule(2.5,"mapbox"); await f.tick(); assert.equal(f.calls.length,2);
    }],
    ["canonical saved scale wins over an optimistic stale compatibility projection",async()=>{
      const f=fixture({savedScale:scale});
      const input=structuredClone(f.project.current.project_input);
      input.manual_fields.site_objects=[];
      const snap=canonical.withCanonicalCanvasSnapshot(input);
      snap.canonical_project_v1.site.site_inputs_v1=input.meta.site_inputs;
      snap.canonical_project_v1.extensions.project_record_v1={version:1,input_controls:{},input_meta:{}};
      f.project.current.project_input={...input,meta:{site_inputs:{}},canonical_project_v1:snap.canonical_project_v1};
      f.schedule(2.5,"mapbox");await f.tick();assert.equal(f.calls.length,0);
    }],
    ["live geometry projection preserves unmodeled saved fields and source receipts", async () => {
      const f=fixture(); f.project.current.project_input.legacy_control={keep:"root"};
      f.project.current.project_input.meta.custom_source_receipt={hash:"synthetic-original"};
      f.project.current.project_input.manual_fields.custom_field={keep:true};
      f.schedule(2.5,"mapbox");await f.tick();
      const saved=f.calls[0].projectInputOverride;
      assert.equal(saved.legacy_control?.keep,"root");
      assert.equal(saved.meta.custom_source_receipt?.hash,"synthetic-original");
      assert.equal(saved.manual_fields.custom_field?.keep,true);
    }],
    ["actual scale or calibration change still persists", async () => {
      const f = fixture({savedScale:scale,feet:"100",pixels:"40"}); f.schedule(2.5,"mapbox"); await f.tick();
      assert.equal(f.calls.length,1); assert.equal(f.calls[0].projectInputOverride.meta.site_inputs.detection_scale.distance_ft,100);
    }],
    ["lock-state change still persists", async () => {
      const f = fixture({savedScale:scale,savedLocked:true}); f.schedule(2.5,"mapbox"); await f.tick(); assert.equal(f.calls.length,1);
    }],
    ...["generation","identity"].map(kind=>[`${kind} change rejects delayed scale write`,async()=>{
      const f=fixture(); f.schedule(2.5,"mapbox"); if(kind==="generation")f.generation.current++;else f.identity.current="different";
      await f.tick();assert.equal(f.calls.length,0);
    }]),
    ["unpersisted live scale must not be mistaken for an acknowledged save",async()=>{
      const f=fixture(); f.payload.current.meta.site_inputs.detection_scale=scale;
      f.schedule(2.5,"mapbox");await f.tick();assert.equal(f.calls.length,1);
    }],
    ...[NaN,Infinity,0,-1].map(value=>[`invalid scale ${String(value)} cannot reach persistence`,async()=>{
      const f=fixture();f.schedule(value,"mapbox");await f.tick();assert.equal(f.calls.length,0);
    }]),
  ];
  let failures=0;
  for(const [name,run] of cases){try{await run();console.log(`PASS ${name}`);}catch(error){failures++;console.error(`FAIL ${name}: ${error.message}`);}}
  process.exitCode=failures?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
