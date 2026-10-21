// Offline regression of actual drawing utilities; no servers, providers or stores.
(async () => {
  const {default:assert}=await import("node:assert/strict");
  const {default:fs}=await import("node:fs");
  const {default:path}=await import("node:path");
  const {default:vm}=await import("node:vm");
  const {createRequire}=await import("node:module");
  const {default:ts}=await import("typescript");
  const cache=new Map();
  function load(filename) {
    filename=path.resolve(filename);
    if(!path.extname(filename))filename=[".ts",".tsx",".json"].map(ext=>filename+ext).find(file=>fs.existsSync(file));
    if(!filename)throw Error("Missing utility");
    if(filename.endsWith(".json"))return JSON.parse(fs.readFileSync(filename,"utf8"));
    if(cache.has(filename))return cache.get(filename);
    const exports={};cache.set(filename,exports);
    const code=ts.transpileModule(fs.readFileSync(filename,"utf8"),{fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
    vm.runInThisContext(`(function(exports,require){${code}\n})`,{filename})(exports,name=>name.startsWith(".")?load(path.resolve(path.dirname(filename),name)):createRequire(filename)(name));
    return exports;
  }
  const trace=load(`${__dirname}/../app/utils/dashboardObjectManagerTrace`);
  const geo=load(`${__dirname}/../app/utils/objectGeometry`);
  const preview=load(`${__dirname}/../app/utils/dashboardPreview3DItems`);
  const catalog=load(`${__dirname}/../app/utils/siteObjectCatalog`).SITE_OBJECT_CATALOG;
  const interference=load(`${__dirname}/../app/utils/siteInterference`);
  const line={id:"line",label:"Line",type:"custom",x:10,y:20,w:100,d:5,geometryType:"polyline",geometry:[[10,20],[110,20]],placed:true};
  const triangle={id:"triangle",label:"Triangle",type:"building",x:10,y:20,w:50,d:50,geometryType:"polygon",geometry:[[10,20],[60,20],[60,70]],placed:true};
  const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
  const cases=[
    ["100-ft line scaled1.5 measures150ft",()=>{const next={...line,...trace.createObjectManagerScaleUpdateEntries([line],1.5)[0].updates};near(geo.getGeometryLength(next.geometry),150);near(next.w,150);assert.deepEqual(next.geometry[0],[10,20]);}],
    ["move translates true geometry and bounds without mutation",()=>{const before=JSON.stringify(triangle);const next={...triangle,...trace.createObjectManagerMoveUpdateEntries([triangle],-5,12)[0].updates};assert.deepEqual(next.geometry,[[5,32],[55,32],[55,82]]);near(geo.getObjectManagerBounds?.(next)?.minX??trace.getObjectManagerBounds(next).minX,5);assert.equal(JSON.stringify(triangle),before);near(geo.getPolygonArea(next.geometry),1250);}],
    ["moving a semantic object moves its retained source exactly once",()=>{const source={...triangle,id:"source",meta:{ui_hidden:true}};const owner={...triangle,meta:{combined_from_object_ids:["source"]}};const result=trace.createTraceAwareBulkUpdate({entries:trace.createObjectManagerMoveUpdateEntries([owner],-5,12),label:"move",buildingPlacements:[owner,source]});assert.deepEqual(result.afterById.get("triangle").geometry,[[5,32],[55,32],[55,82]]);assert.deepEqual(result.afterById.get("source").geometry,[[5,32],[55,32],[55,82]]);assert.deepEqual(result.undo.before[0].geometry,triangle.geometry);}],
    ["1250-sf triangle scaled2 measures5000sf",()=>{const next={...triangle,...trace.createObjectManagerScaleUpdateEntries([triangle],2)[0].updates};near(geo.getPolygonArea(next.geometry),5000);near(next.w,100);near(next.d,100);}],
    ["scale is immutable and survives JSON roundtrip",()=>{const original=JSON.stringify(triangle);const next=JSON.parse(JSON.stringify({...triangle,...trace.createObjectManagerScaleUpdateEntries([triangle],2)[0].updates}));assert.equal(JSON.stringify(triangle),original);near(geo.getDraftObjectMeasurement(next).areaSf,5000);}],
    ["scale and inverse restore true geometry",()=>{const next={...triangle,...trace.createObjectManagerScaleUpdateEntries([triangle],2)[0].updates};const back={...next,...trace.createObjectManagerScaleUpdateEntries([next],.5)[0].updates};assert.deepEqual(back.geometry,triangle.geometry);}],
    ["vertical line preserves zero span and scales length",()=>{const vertical={...line,w:5,d:100,geometry:[[10,20],[10,120]]};const next={...vertical,...trace.createObjectManagerScaleUpdateEntries([vertical],1.5)[0].updates};near(geo.getGeometryLength(next.geometry),150);near(next.geometry[0][0],next.geometry[1][0]);}],
    ["diagonal scale preserves angle and expected length",()=>{const diagonal={...line,w:60,d:80,geometry:[[10,20],[70,100]]};const next={...diagonal,...trace.createObjectManagerScaleUpdateEntries([diagonal],.5)[0].updates};near(geo.getGeometryLength(next.geometry),50);near((next.geometry[1][1]-20)/(next.geometry[1][0]-10),80/60);}],
    ["true footprint bounds repair legacy mismatched sizing on scale",()=>{const legacy={...triangle,w:100,d:100};const next={...legacy,...trace.createObjectManagerScaleUpdateEntries([legacy],2)[0].updates};near(next.w,100);near(next.d,100);near(geo.getPolygonArea(next.geometry),5000);}],
    ["small rectangle retains the existing minimum-dimension policy",()=>{const small={...triangle,w:1,d:1,geometry:[[10,20],[11,20],[11,21],[10,21]]};const next={...small,...trace.createObjectManagerScaleUpdateEntries([small],.5)[0].updates};near(next.w,1);near(next.d,1);near(geo.getPolygonArea(next.geometry),1);}],
    ["geometry-free rectangle preserves sizing behavior",()=>{const rect={...triangle,geometry:undefined,geometryType:"rect",h:30};const next={...rect,...trace.createObjectManagerScaleUpdateEntries([rect],2)[0].updates};near(next.w,100);near(next.d,100);near(next.h,60);assert.equal(next.geometry,undefined);}],
    ["trace and undo snapshots share accepted scaled geometry",()=>{const source={...triangle,id:"source",meta:{ui_hidden:true}};const target={...triangle,meta:{combined_from_object_ids:["source"]}};const entries=trace.createObjectManagerScaleUpdateEntries([target],2);const result=trace.createTraceAwareBulkUpdate({entries,label:"scale",buildingPlacements:[target,source]});near(geo.getPolygonArea(result.afterById.get("triangle").geometry),5000);near(geo.getPolygonArea(result.afterById.get("source").geometry),5000);assert.deepEqual(result.undo.before[0].geometry,triangle.geometry);}],
    ...["building","retail_building","office_building"].map(type=>[`${type} missing height matches editor catalog default`,()=>{const objects=preview.buildPlacementPreview3DItems({lot:{w:300,h:200},buildingPlacements:[{...triangle,type}],cadEntityPreviewItems3D:[],sourceConfidenceByObjectId:new Map()});near(objects.find(item=>item.id==="triangle").height,catalog[type].defaultH);}]),
    ["explicit building height remains authoritative",()=>{const objects=preview.buildPlacementPreview3DItems({lot:{w:300,h:200},buildingPlacements:[{...triangle,h:72}],cadEntityPreviewItems3D:[],sourceConfidenceByObjectId:new Map()});near(objects.find(item=>item.id==="triangle").height,72);}],
    ["hidden retained source is omitted from 3D without CAD resurrection",()=>{const hidden={...triangle,id:"hidden",type:"custom",meta:{ui_hidden:true}};const objects=preview.buildPlacementPreview3DItems({lot:{w:300,h:200},buildingPlacements:[triangle,hidden],cadEntityPreviewItems3D:[{id:"hidden",linkedObjectId:"hidden",x:10,y:20,w:50,h:50,height:1,label:"Hidden CAD source",layer:"CUSTOM"}],sourceConfidenceByObjectId:new Map()});assert.ok(objects.some(item=>item.id==="triangle"));assert.equal(objects.some(item=>item.id==="hidden"),false);}],
    ["interference identifies semantic owner and retained physical source",()=>{const source={...triangle,type:"custom",id:"source",label:"Hidden source",meta:{ui_hidden:true,combined_into_object_id:"semantic"}};const owner={...triangle,id:"semantic",label:"Named building",meta:{combined_from_object_ids:["source"]}};const obstacle={...triangle,id:"obstacle",label:"Other building"};const results=interference.assessSiteInterference([obstacle,source,owner]);const hit=results.find(item=>item.objectIds.includes("source")&&item.objectIds.includes("obstacle"));assert.ok(hit);assert.ok(hit.message.includes("Named building (source: Hidden source)"),hit.message);assert.equal(hit.severity,"review");assert.equal(results.filter(item=>item.objectIds.includes("semantic")).length,0);}],
  ];
  let failed=0;for(const[name,run]of cases){try{run();console.log(`PASS ${name}`);}catch(error){failed++;console.error(`FAIL ${name}: ${error.message}`);}}
  console.log(`${cases.length-failed} PASS / ${failed} FAIL`);process.exitCode=failed?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
