// Offline tests of actual release modules; no server, filesystem stores or providers.
(async () => {
  const assert = require('node:assert/strict');
  const fs = require('node:fs');
  const path = require('node:path');
  const vm = require('node:vm');
  const ts = require('typescript');
  const {createRequire} = require('node:module');
  const cache = new Map();
  let response, transportError, saveResult, calls, state;
  function load(filename) {
    filename = path.resolve(filename);
    if (!path.extname(filename)) filename = ['.ts','.tsx','.json'].map(e=>filename+e).find(fs.existsSync);
    if (filename.endsWith('.json')) return JSON.parse(fs.readFileSync(filename,'utf8'));
    if (cache.has(filename)) return cache.get(filename);
    const exports={}; cache.set(filename,exports);
    const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
    vm.runInThisContext(`(function(exports,require){${code}\n})`,{filename})(exports,name=>{
      if ((filename.endsWith('useDashboardExistingConditionsUpload.ts') || filename.endsWith('usePreviewCadPropertyCommands.ts')) && name==='react') return {useCallback:f=>f};
      if (filename.endsWith('useDashboardExistingConditionsUpload.ts') && name==='../../lib/api') return {postForm:async()=>{calls.push('upload');if(transportError)throw transportError;return response;}};
      return name.startsWith('.')?load(path.resolve(path.dirname(filename),name)):createRequire(filename)(name);
    }); return exports;
  }
  const root=path.join(__dirname,'../app');
  const interference=load(`${root}/utils/siteInterference`);
  const hook=load(`${root}/hooks/useDashboardExistingConditionsUpload`).useDashboardExistingConditionsUpload;
  const dimension=load(`${root}/utils/cadDimensionBinding`);
  const trace=load(`${root}/utils/dashboardObjectManagerTrace`);
  const dimensionCommands=load(`${root}/components/usePreviewCadPropertyCommands`).usePreviewCadPropertyCommands;
  const dimensionLine={id:'dimension-line',type:'custom',x:0,y:0,w:40,d:5,placed:true,geometryType:'polyline',geometry:[[0,0],[40,0]],meta:{cad_dimension_label:'40.0 ft',cad_dimension_mode:'linear',cad_dimension_auto:true}};
  const originalPoints=[[0,0,102],[220,0,101.4],[0,160,100.8],[220,160,100]];
  const valid={success:true,file_type:'csv',stored_filename:'new.csv',canonical_existing_conditions:{survey:{points:originalPoints.map(([x,y,z])=>({x,y,z})),point_count:4}},existing_conditions_package:{status:'review_required'},warnings:['Coordinate metadata incomplete']};
  const originalInput={meta:{site_inputs:{survey_file:{stored_filename:'original.csv'},survey_points:originalPoints,survey_point_count:4}}};
  function uploader(token='test-token') {
    state={filename:'original.csv',points:originalPoints,diagnostics:{pointCount:4},preview:[{x:0,y:0}],effects:['Original source warning'],message:''}; calls=[];saveResult={id:'project'};transportError=null;
    const setters={};for(const [key,prop] of Object.entries({setSurveyFileName:'filename',setSurveyPoints:'points',setSurveyDiagnostics:'diagnostics',setSurveyPreviewPoints:'preview',setSourceEffectRows:'effects',setSurveyUploadMessage:'message'})) setters[key]=v=>{calls.push(key);state[prop]=v;};
    return hook({...setters,currentProject:{id:'project',project_input:originalInput},payloadPreview:originalInput,lotWidthValue:300,lotHeightValue:200,token,useSurveyForGrading:true,setStatusMessage:m=>{state.status=m;},appendChatMessage:()=>{},saveProject:async args=>{calls.push('save');state.saved=args;return saveResult;}}).uploadExistingConditions;
  }
  const originalUnchanged=()=>{assert.equal(state.filename,'original.csv');assert.deepEqual(state.points,originalPoints);assert.deepEqual(state.diagnostics,{pointCount:4});assert.deepEqual(state.effects,['Original source warning']);};
  const square=[[20,20],[60,20],[60,60],[20,60]];
  const owner={id:'owner',label:'Grouped building',type:'building',x:20,y:20,w:40,d:40,geometryType:'polygon',geometry:square,placed:true,meta:{combined_from_object_ids:['e0','e1','e2','e3']}};
  const edges=square.map((p,i)=>({id:`e${i}`,label:`Edge${i}`,type:'custom',x:Math.min(p[0],square[(i+1)%4][0]),y:Math.min(p[1],square[(i+1)%4][1]),w:5,d:5,geometryType:'polyline',geometry:[p,square[(i+1)%4]],placed:true,meta:{ui_hidden:true,combined_into_object_id:'owner'}}));
  const cases=[
    ['new DIM default explicitly binds to source geometry',()=>{let updates;const commands=dimensionCommands({buildingPlacements:[dimensionLine],selectedCadIds:[dimensionLine.id],selectedCadObject:dimensionLine,selectedCadMetrics:{firstLength:40,firstAngle:0},cadDimensionMode:'linear',cadDimensionLabelDraft:'',cadPropertyDraft:{},cadCoordinateDraft:{},pushCadCommandFeedback:()=>{},updateCadObject:(_item,value)=>{updates=value;}});commands.applySelectedCadDimension();assert.equal(updates.meta.cad_dimension_auto,true);assert.equal(updates.meta.cad_dimension_label,'40.0 ft');}],
    ['dimension follows40→60 scale in stored model and renderer',()=>{const next=trace.cloneBuildingPlacementWithUpdatesForUndo(dimensionLine,trace.createObjectManagerScaleUpdateEntries([dimensionLine],1.5)[0].updates);assert.equal(next.meta.cad_dimension_label,'60.0 ft');assert.equal(dimension.displayedCadDimensionLabel(JSON.parse(JSON.stringify(next))),'60.0 ft');assert.equal(dimensionLine.meta.cad_dimension_label,'40.0 ft');}],
    ['inverse edit restores dimension and aligned angle follows geometry',()=>{const next=trace.cloneBuildingPlacementWithUpdatesForUndo(dimensionLine,{geometry:[[0,0],[0,60]],meta:{cad_dimension_mode:'aligned'}});assert.equal(next.meta.cad_dimension_label,'60.0 ft @ 90.0 deg');assert.equal(dimension.automaticCadDimensionLabel({...dimensionLine,meta:{...dimensionLine.meta,coordinate_units:'m'}}),'40.0 m');}],
    ['custom and legacy captions are preserved and flagged after geometry edits',()=>{for(const auto of [false,undefined]){const manual={...dimensionLine,meta:{...dimensionLine.meta,cad_dimension_label:'FIELD CHECK',cad_dimension_auto:auto}};const next=trace.cloneBuildingPlacementWithUpdatesForUndo(manual,{geometry:[[0,0],[60,0]]});assert.equal(next.meta.cad_dimension_label,'FIELD CHECK');assert.equal(next.meta.cad_dimension_review_required,true);assert.match(dimension.displayedCadDimensionLabel(next),/review/);}}],
    ['invalid automatic dimension cannot display a numeric success',()=>{const next={...dimensionLine,geometry:[[0,0],[NaN,0]]};assert.match(dimension.displayedCadDimensionLabel(next),/unavailable.*review/i);}],
    ['same verified outline has no internal contact warnings',()=>assert.equal(interference.assessSiteInterference([owner,...edges]).length,0)],
    ['independent building still contacts hidden outline',()=>assert.ok(interference.assessSiteInterference([owner,...edges,{...owner,id:'other',label:'Other',meta:{}}]).some(r=>r.objectIds.includes('other')))],
    ['dangling or one-sided contributor IDs do not suppress checks',()=>assert.ok(interference.assessSiteInterference([{...owner,meta:{combined_from_object_ids:['e0']}},...edges]).length>0)],
    ['interior crossing is not treated as an outline edge',()=>{const altered=edges.map((e,i)=>i===1?{...e,geometry:[[20,20],[60,60]]}:e);assert.ok(interference.assessSiteInterference([owner,...altered]).length>0);}],
    ['outline edges with extra engineering envelopes retain review checks',()=>{const altered=edges.map((e,i)=>i===1?{...e,meta:{...e.meta,coordination_envelope_v1:{}}}:e);assert.ok(interference.assessSiteInterference([owner,...altered]).some(r=>r.objectIds.includes('e1')));}],
    ['linework building includes its interior as occupied footprint',()=>{const physical={...owner,meta:{...owner.meta,semantic_source_mode:'linework'}};const inside={...owner,id:'inside',label:'Inside building',x:35,y:35,w:5,d:5,geometryType:'rect',geometry:undefined,meta:{}};const hits=interference.assessSiteInterference([physical,...edges,inside]);assert.ok(hits.some(r=>r.objectIds.includes('owner')&&r.objectIds.includes('inside')));assert.equal(interference.assessSiteInterference([physical,...edges]).length,0);}],
    ['invalid upload preserves active source and does not save',async()=>{const run=uploader();response={success:false,file_type:'csv',message:'No supported data',canonical_existing_conditions:{survey:{points:[],point_count:0}}};await run(new File(['invalid'],'invalid.csv'));originalUnchanged();assert.equal(calls.includes('save'),false);assert.match(state.message,/failed|not applied/i);assert.doesNotMatch(state.message,/imported/i);}],
    ['CSV with zero finite points cannot become active even with success flag',async()=>{const run=uploader();response={...valid,canonical_existing_conditions:{survey:{points:[{x:null,y:0,z:100}],point_count:4}}};await run(new File(['invalid'],'invalid.csv'));originalUnchanged();assert.equal(calls.includes('save'),false);}],
    ['unsupported extension leaves active source unchanged',async()=>{const run=uploader();await run(new File(['x'],'bad.exe'));originalUnchanged();assert.equal(calls.includes('upload'),false);}],
    ['unauthenticated upload leaves active source unchanged',async()=>{const run=uploader(null);await run(new File(['x'],'test.csv'));originalUnchanged();assert.equal(calls.includes('upload'),false);}],
    ['transport failure leaves active source unchanged',async()=>{const run=uploader();transportError=new Error('offline');await run(new File(['x'],'test.csv'));originalUnchanged();}],
    ['failed save cannot activate replacement or claim imported',async()=>{const run=uploader();response=valid;saveResult=null;await run(new File(['x'],'test.csv'));originalUnchanged();assert.match(state.message,/failed|not applied/i);}],
    ['valid review-required survey saves before activation and retains warning',async()=>{const run=uploader();response=valid;await run(new File(['x'],'test.csv'));assert.equal(state.filename,'new.csv');assert.equal(state.points.length,4);assert.ok(calls.indexOf('save')<calls.indexOf('setSurveyFileName'));assert.ok(state.effects.some(s=>s.includes('Does not replace survey')));assert.match(state.message,/review/i);}],
    ['generation badge reflects missing system inputs, not just site existence',()=>{const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');const Panel=load(`${root}/components/GeneratePanel`).GeneratePanel;const props={missingSite:false,busy:false,activeJobStatus:'',approvalState:'idle',approvalCheckpointLabel:null,approvalError:null,statusMessage:'',assistedEnabled:false,pendingPlacementCount:0,pendingPlacementLabels:[],currentUserLayoutContext:null,autoSiteContextFlowSummary:{candidateCount:0,candidateLabels:[],missingLabels:[],reviewRequired:true},systemReadinessRows:[{key:'grading',label:'Grading',runTarget:'grading',status:'missing',blockers:['missing standards']}],issues:[],generateFlowSummary:null,reactiveValidation:{status:'idle',changedSystems:[],changedTargets:[],requiresConfirmation:false,message:''},onGenerateSystem:()=>{},onAssistedEnabledChange:()=>{},onStatusMessageChange:()=>{},onGenerateFlowSummaryChange:()=>{},formatStageLabel:x=>x,drainageIssueApplyLabel:()=>null};const html=renderToStaticMarkup(React.createElement(Panel,props));assert.match(html,/data-testid="generate-readiness"[^>]*>Needs input</);const ready=renderToStaticMarkup(React.createElement(Panel,{...props,systemReadinessRows:[{...props.systemReadinessRows[0],blockers:[]}]}));assert.match(ready,/data-testid="generate-readiness"[^>]*>Ready</);}],
  ];
  let failed=0;for(const[name,run]of cases){try{await run();console.log(`PASS ${name}`);}catch(e){failed++;console.error(`FAIL ${name}: ${e.message.slice(0,240)}`);}}
  console.log(`${cases.length-failed} PASS / ${failed} FAIL`);process.exitCode=failed?1:0;
})().catch(e=>{console.error(e);process.exitCode=1;});
