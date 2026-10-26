// Actual save hook + actual queue/merge helper; controlled API, React commit held.
(async()=>{
 const {default:assert}=await import('node:assert/strict');const {default:fs}=await import('node:fs');
 const {default:ts}=await import('typescript');const {default:vm}=await import('node:vm');
 const flush=()=>new Promise(resolve=>setImmediate(resolve));
 const load=(file,require,window)=>{const exports={};const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;vm.runInThisContext(`(function(exports,require,window){${code}\n})`)(exports,require,window);return exports;};
 const noImport=name=>{throw Error(`Unexpected utility dependency ${name}`);};
 const queue=load(`${__dirname}/../app/utils/dashboardProjectSaveQueue.ts`,noImport);
 const merge=load(`${__dirname}/../app/utils/siteInputAcknowledgement.ts`,noImport);
 let accept;const pending=new Promise(resolve=>{accept=resolve;});const requests=[],stateUpdates=[];
 const base={manual_fields:{project_name:'Synthetic',file_name:'synthetic',site_objects:[{id:'building',x:125}]},meta:{site_inputs:{address:'A'}}};
 const payload={current:structuredClone(base)},generation={current:1},identity={current:'owned'};
 const accepted=(input,revision)=>({project:{project_id:'owned',name:'Synthetic',revision_token:revision,project_input:structuredClone(input)}});
 const hook=load(process.env.CIVORA_SAVE_HOOK_BASELINE||`${__dirname}/../app/hooks/useDashboardProjectSave.ts`,name=>{
  if(name==='react')return{useCallback:value=>value,useRef:current=>({current}),useState:value=>[value,()=>{}]};
  if(name==='../../lib/api')return{postJson:async(_url,body)=>{requests.push(structuredClone(body));return requests.length===1?pending:accepted(body.project_input,'r2');}};
  if(name.endsWith('dashboardProjectSaveQueue'))return queue;
  if(name.endsWith('siteInputAcknowledgement'))return merge;
  if(name.endsWith('canonicalCanvasProject'))return{withCanonicalCanvasSnapshot:input=>input,resolveCanonicalCanvasInput:input=>input};
  if(name.endsWith('useProjectTabBranch'))return{useProjectTabBranch:()=>({hasEdits:()=>true,beforeSave:async()=>null,choose:async()=>{throw Error('Unexpected conflict');},markSaved(){}})};
  if(name.endsWith('workflowConstants'))return{ACTIVE_PROJECT_STORAGE_KEY:'fixture'};
  if(name.endsWith('dashboardStatus'))return{panelErrorMessage:error=>error.message};
  throw Error(`Unexpected hook dependency ${name}`);
 },{localStorage:{setItem(){}},sessionStorage:{setItem(){}}});
 const noop=()=>{};
 const actions=hook.useDashboardProjectSave({token:'synthetic-only',projectId:'owned',currentProject:{project_id:'owned',name:'Synthetic',revision_token:'r0',project_input:base},
  chatMessagesRef:{current:[]},fileName:'synthetic',siteName:'Synthetic',payloadPreviewRef:payload,projectLoadRequestRef:generation,resolvedProjectIdRef:identity,
  setupWizardStateRef:{current:{}},isSeededDemoProjectId:()=>false,setCurrentProject:update=>stateUpdates.push(update),
  setBusy:noop,setProjectDrawerNotice:noop,setProjectId:noop,setSiteName:noop,setWorkspaceRestoreState:noop,updateProjectStatus:noop,upsertProjectSummary:noop});
 const requested=structuredClone(base);requested.meta.site_inputs.detection_scale={scale_ft_per_px:2,scale_source:'mapbox'};
 const first=actions.saveProject({silent:true,projectInputOverride:requested});await flush();assert.equal(requests.length,1);
 payload.current.manual_fields.site_objects[0].x=225;payload.current.meta.site_inputs.address='C';
 const second=actions.saveProject({silent:true});
 accept(accepted(requested,'r1'));await first;await second;
 assert.equal(stateUpdates.length,2,'React updates must be queued, not required for source acknowledgement');
 assert.equal(requests[1].expected_revision,'r1');
 assert.equal(requests[1].project_input.meta.site_inputs.detection_scale?.scale_ft_per_px,2,'Queued save must retain the acknowledged source field');
 assert.equal(requests[1].project_input.meta.site_inputs.address,'C','Newer source edit must survive');
 assert.equal(requests[1].project_input.manual_fields.site_objects[0].x,225,'Newer live geometry must survive');
 console.log('PASS actual save acknowledgement reaches queued save before React commit, preserving newer source/geometry edits');
})().catch(error=>{console.error(`FAIL ${error.message}`);process.exitCode=1;});
