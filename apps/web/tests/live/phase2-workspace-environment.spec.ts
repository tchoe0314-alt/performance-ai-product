import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { defaultEnvironment, displayLength, environmentLayerForObject, environmentObjectVisible, environmentStorageKey, parseEnvironment } from "../../app/utils/workspaceEnvironment";
import { resolveCadSnap } from "../../app/utils/cadGeometryKernel";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { revealPreviewCanvas } from "./testUiHelpers";
import { openMapAnchoredFixture } from "./mapAnchoredFixture";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("environment memory validates untrusted storage, separates identities, and converts display only",()=>{
  expect(parseEnvironment("broken")).toEqual(defaultEnvironment());
  expect(parseEnvironment('{"version":2,"units":"m"}')).toEqual(defaultEnvironment());
  const settings=parseEnvironment('{"version":1,"units":"m","gridFt":-1,"grid":true,"snap":false,"layers":{"utilities":false},"semantic":{"roads":false,"unknown":false}}');
  expect(settings.gridFt).toBe(5);expect(settings.units).toBe("m");expect(settings.snap).toBe(false);expect(settings.semantic).toEqual({roads:false});
  expect(settings.layers.utilities).toBe(false);expect(settings.layers.survey).toBe(true);
  expect(parseEnvironment(JSON.stringify({...settings,gridFt:Infinity})).gridFt).toBe(5);
  expect(parseEnvironment(JSON.stringify({...settings,gridFt:25})).gridFt).toBe(25);
  expect(parseEnvironment('{"version":1,"hiddenCadLayers":["C-WATR","C-WATR",42,""]}').hiddenCadLayers).toEqual(["C-WATR"]);
  expect(displayLength(30,"m",3)).toBe("9.144 m");expect(displayLength(30,"ft")).toBe("30 ft");
  const scope={account:"a",project:"p",generation:1};
  expect(environmentStorageKey(scope)).toBe(environmentStorageKey({...scope,generation:2}));
  expect(environmentStorageKey(scope)).not.toBe(environmentStorageKey({...scope,account:"b"}));
  expect(environmentStorageKey({...scope,project:""})).not.toBe(environmentStorageKey({...scope,project:"",generation:2}));
});

test("context layers use actual source classification; hidden data remains unchanged",()=>{
  const samples=[{type:"custom",meta:{source_type:"zoning"}},{type:"lot_block"},{type:"utility_corridor"},{type:"custom",meta:{cad_layer:"EG_CONTOURS"}},{type:"custom",meta:{cad_layer:"C-SURV"}}];
  expect(samples.map(environmentLayerForObject)).toEqual(["zoning","parcels","utilities","topographic","survey"]);
  expect(environmentLayerForObject({type:"setback_zone"})).toBeUndefined();
  const before=JSON.stringify(samples), layers=defaultEnvironment().layers;
  for(const sample of samples){const layer=environmentLayerForObject(sample)!;expect(environmentObjectVisible(sample,{...layers,[layer]:false})).toBe(false);expect(environmentObjectVisible(sample,layers)).toBe(true);}
  expect(JSON.stringify(samples)).toBe(before);
  const options={enabled:true,ortho:false,threshold:100};
  expect(resolveCadSnap({x:38,y:38},[],{...options,gridSize:5})).toMatchObject({x:40,y:40,kind:"grid"});
  expect(resolveCadSnap({x:38,y:38},[],{...options,gridSize:25})).toMatchObject({x:50,y:50,kind:"grid"});
  expect(resolveCadSnap({x:38,y:38},[],{...options,gridSize:25,enabled:false})).toMatchObject({x:38,y:38});
});

async function viewMenu(page:Page){
  await revealPreviewCanvas(page);
  const summary=page.getByLabel("Preview view options",{exact:true});
  if(!await summary.evaluate(el=>(el.closest("details") as HTMLDetailsElement).open))await summary.click();
  return page.getByTestId("environment-view-controls");
}
async function closeView(page:Page){const summary=page.getByLabel("Preview view options",{exact:true});if(await summary.evaluate(el=>(el.closest("details") as HTMLDetailsElement).open))await summary.click();}
async function layersMenu(page:Page){
  await revealPreviewCanvas(page);
  const menu=page.getByTestId("preview-layer-menu");
  if(!await menu.evaluate(el=>(el as HTMLDetailsElement).open))await menu.locator(":scope > summary").click();
  return menu;
}

for(const [width,height]of [[320,568],[844,390],[1280,720]])test(`environment controls persist, stay compact, and show missing sources honestly at ${width}x${height}`,async({page},info)=>{
  await page.setViewportSize({width,height});await page.goto("/demo/workspace?debugPreview=1");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const view=await viewMenu(page);
  await expect(view.getByTestId("environment-coordinate-system")).toContainText("Local site");
  await view.getByLabel("Display units").selectOption("m");
  await view.getByLabel("Show drafting grid").check();
  await view.getByLabel("Grid and snap spacing").selectOption("25");
  await view.getByLabel("Enable snapping",{exact:true}).uncheck();
  await view.getByLabel("Enable orthogonal drawing").check();
  await expect(page.getByTestId("drafting-grid")).toHaveAttribute("data-grid-ft","25");
  await expect(page.getByTestId("canvas-coordinate-readout")).toContainText(" m");
  await expect(page.getByTestId("plan-scale-bar")).toContainText(" m");
  const menu=view.locator("..");
  const box=(await menu.boundingBox())!;expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width+1);expect(box.y+box.height).toBeLessThanOrEqual(height+1);
  expect(await menu.evaluate(el=>el.scrollWidth-el.clientWidth)).toBeLessThanOrEqual(1);
  const overlaps=await menu.evaluate(el=>{
    const box=el.getBoundingClientRect();
    return Array.from(document.querySelectorAll('.civora-command-dock,[data-testid="left-sidebar"]')).some(blocker=>{const rect=blocker.getBoundingClientRect();return rect.height>0&&rect.left<box.right&&rect.right>box.left&&rect.top<box.bottom&&rect.bottom>box.top;});
  });
  expect(overlaps).toBe(false);
  const violations=(await new AxeBuilder({page}).include('[data-testid="environment-view-controls"]').analyze()).violations;
  expect(violations.filter(v=>v.impact==="serious"||v.impact==="critical")).toEqual([]);
  await page.screenshot({path:info.outputPath(`environment-${width}.png`)});
  await closeView(page);await layersMenu(page);
  for(const layer of ["topographic","zoning","parcels","survey","utilities"]){const control=page.getByTestId(`environment-layer-${layer}`);await expect(control).toContainText("No data");await expect(control.getByRole("button")).toBeDisabled();}
  await page.reload();await viewMenu(page);
  await expect(page.getByLabel("Display units")).toHaveValue("m");await expect(page.getByLabel("Grid and snap spacing")).toHaveValue("25");
  await expect(page.getByLabel("Show drafting grid")).toBeChecked();await expect(page.getByLabel("Enable snapping",{exact:true})).not.toBeChecked();await expect(page.getByLabel("Enable orthogonal drawing")).toBeChecked();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
});

test("denied or corrupt session memory cannot block environment editing",async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(window,"sessionStorage",{get:()=>({getItem:()=>{throw new Error("Denied");},setItem:()=>{throw new Error("Denied");},removeItem:()=>{}})}));
  await page.goto("/demo/workspace?debugPreview=1");await viewMenu(page);await page.getByLabel("Show drafting grid").check();await page.getByLabel("Display units").selectOption("m");
  await expect(page.getByTestId("drafting-grid")).toBeVisible();await expect(page.getByTestId("canvas-coordinate-readout")).toContainText(" m");
});

test("changing grid spacing instantly changes the actual pointer snap coordinates",async({page})=>{
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1");await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await layersMenu(page);await page.getByTestId("preview-source-layer-existing").click();await page.getByTestId("preview-source-layer-proposed").click();await page.getByTestId("preview-layer-menu").locator(":scope > summary").click();
  await viewMenu(page);await page.getByLabel("Show drafting grid").check();await page.getByLabel("Grid and snap spacing").selectOption("25");await closeView(page);
  await openWorkspaceTool(page,"Draw");await page.getByTestId("cad-tool-line").filter({visible:true}).click();
  const minimize=page.getByRole("button",{name:"Minimize",exact:true});if(await minimize.isVisible())await minimize.click();await revealPreviewCanvas(page);
  const surface=page.getByTestId("preview-drawing-surface");await expect(surface).toHaveAttribute("data-draw-mode","polyline");
  const box=(await surface.boundingBox())!;const point={x:box.x+box.width*.64,y:box.y+box.height*.36};
  const readout=page.getByTestId("draft-precision-readout");
  const current=async()=>{const text=await readout.innerText();const match=text.match(/X ([\d.-]+) ft \/ Y ([\d.-]+) ft/);expect(match).not.toBeNull();return [Number(match![1]),Number(match![2])];};
  await page.mouse.move(point.x,point.y);await expect(readout).toContainText(/SNAP grid/i);const before=await current();expect(before.every(value=>value%25===0)).toBe(true);
  await viewMenu(page);await page.getByLabel("Grid and snap spacing").selectOption("10");await closeView(page);await page.mouse.move(point.x+1,point.y);await expect(readout).toContainText(/SNAP grid/i);const after=await current();expect(after.every(value=>value%10===0)).toBe(true);expect(after).not.toEqual(before);
  await viewMenu(page);await page.getByLabel("Enable snapping",{exact:true}).uncheck();await closeView(page);await page.mouse.move(point.x+2,point.y);const unsnapped=await current();expect(unsnapped.some(value=>value%10!==0)).toBe(true);
  await page.keyboard.press("Escape");await expect(surface).toHaveAttribute("data-draft-point-count","0");
});

const api=process.env.PLAYWRIGHT_API_BASE_URL??"";
const local=process.env.CIVORA_PHASE0_LOCAL_TESTS==="1"&&/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);
test("real project layers and two-tab memory change neither geometry, revisions, nor calculation inputs",async({page,context,request})=>{
  test.skip(!local,"Disposable local projects only.");
  const registered=await request.post(`${api}/api/auth/register`,{data:{email:`environment-${randomUUID()}@example.test`,password:"Disposable-123",name:"Environment"}});expect(registered.status()).toBe(200);
  const {token}=await registered.json(),headers={Authorization:`Bearer ${token}`};
  const projects:import("../../app/types").ProjectRecord[]=[];
  for(const name of ["Environment A","Environment B"]){
    const input=withCanonicalCanvasSnapshot({manual_fields:{project_name:name,units:"ft",lot:{x:0,y:0,w:900,h:700},site_objects:[
      {id:"office",label:"Office",type:"office_building",x:125,y:120,w:160,d:90},
      {id:"pipe",label:"Water main",type:"utility_corridor",x:400,y:100,w:20,d:300},
      {id:"parcel",label:"Parcel",type:"lot_block",x:600,y:100,w:200,d:200},
      {id:"zone",label:"Source zoning",type:"setback_zone",x:130,y:130,w:100,d:100,meta:{source_type:"zoning",setback_rule_v1:{version:1,mode:"excluded_area",appliesTo:["office_building"],source:"Synthetic test rule",reviewed:true}}},
      {id:"contour",label:"Source contour",type:"custom",x:300,y:400,w:100,d:100,meta:{cad_layer:"EG_CONTOURS"}},
      {id:"survey",label:"Survey control",type:"custom",x:500,y:400,w:100,d:100,meta:{cad_layer:"C-SURV"}},
    ]},meta:{site_inputs:{survey_points:[[50,50,100],[100,100,102],[150,150,105]],survey_parse_success:true,survey_point_count:3}}});
    const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:input}});expect(created.status()).toBe(200);projects.push((await created.json()).project);
  }
  await context.addInitScript(value=>{if(!location.href.startsWith("http"))return;localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  const open=async(tab:Page,name:string)=>{await tab.getByTestId("header-projects-button").click();await tab.getByRole("button",{name:`Open project ${name}`,exact:true}).click();await expect(tab.getByTestId("project-status-summary")).toContainText("Project opened");await tab.getByTestId("primary-workflow-sidebar").locator('[aria-current="page"]').click();await revealPreviewCanvas(tab);};
  let writes=0;page.on("request",r=>{if(r.method()==="POST"&&(/\/api\/projects$|\/api\/plan$|\/api\/jobs$/.test(new URL(r.url()).pathname)))writes++;});
  await page.goto("/");await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();await open(page,projects[0].name);
  await viewMenu(page);await page.getByLabel("Display units").selectOption("m");await page.getByLabel("Show drafting grid").check();await page.getByLabel("Grid and snap spacing").selectOption("25");await closeView(page);
  await page.locator('[data-cad-object-id="office"]').click({position:{x:1,y:1}});await revealPreviewCanvas(page);
  await expect(page.getByTestId("live-constraint-card")).toContainText("Source zoning");
  await layersMenu(page);
  await page.getByTestId("environment-layer-zoning").getByRole("button").click();await expect(page.locator('[data-cad-object-id="zone"]')).toHaveCount(0);await expect(page.getByTestId("live-constraint-card")).toContainText("Source zoning");await page.getByTestId("environment-layer-zoning").getByRole("button").click();
  await expect(page.getByTestId("source-survey-point")).toHaveCount(3);await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(3);
  await page.getByTestId("environment-layer-survey").getByRole("button").click();await expect(page.getByTestId("source-survey-point")).toHaveCount(0);await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(3);
  await page.getByTestId("environment-layer-topographic").getByRole("button").click();await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(0);
  await page.getByTestId("environment-layer-survey").getByRole("button").click();await expect(page.getByTestId("source-survey-point")).toHaveCount(3);await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(0);
  await page.getByTestId("environment-layer-topographic").getByRole("button").click();
  for(const [layer,id]of [["utilities","pipe"],["parcels","parcel"],["zoning","zone"],["topographic","contour"],["survey","survey"]]){
    const hit=page.locator(`[data-cad-object-id="${id}"]`);await expect(hit).toBeVisible();
    const button=page.getByTestId(`environment-layer-${layer}`).getByRole("button");await expect(button).toBeEnabled();await button.click();await expect(hit).toHaveCount(0);await button.click();await expect(hit).toBeVisible();
  }
  await page.getByTestId("environment-layer-utilities").getByRole("button").click();await page.getByTestId("preview-layer-menu").locator(":scope > summary").click();
  await page.getByTestId("preview-mode-3d").click();await expect(page.getByTestId("civil-3d-viewer")).toBeVisible();
  await expect(page.locator('[data-canonical-object-id="office"]')).toBeVisible();await expect(page.locator('[data-canonical-object-id="pipe"]')).toHaveCount(0);
  await layersMenu(page);await page.getByTestId("environment-layer-utilities").getByRole("button").click();await expect(page.locator('[data-canonical-object-id="pipe"]')).toBeVisible();await page.getByTestId("environment-layer-utilities").getByRole("button").click();
  await page.getByTestId("preview-layer-menu").locator(":scope > summary").click();
  await viewMenu(page);await page.getByTestId("preview-quality-high").click();await closeView(page);
  await expect.poll(()=>page.evaluate(projectId=>Object.entries(sessionStorage).filter(([key])=>key.startsWith("civora-environment-v1:")&&key.includes(projectId)).map(([,raw])=>JSON.parse(raw).mode),projects[0].project_id)).toEqual(["3d"]);
  await page.reload();
  await expect(page.getByTestId("preview-mode-3d")).toHaveAttribute("aria-pressed","true");
  await expect(page.getByTestId("preview-quality-high")).toHaveAttribute("aria-pressed","true");
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible();await revealPreviewCanvas(page);await page.getByTestId("preview-mode-2d").click();
  await open(page,projects[1].name);await viewMenu(page);await expect(page.getByLabel("Display units")).toHaveValue("ft");await expect(page.getByLabel("Show drafting grid")).not.toBeChecked();await closeView(page);
  await open(page,projects[0].name);await viewMenu(page);await expect(page.getByLabel("Display units")).toHaveValue("m");await expect(page.getByLabel("Grid and snap spacing")).toHaveValue("25");await closeView(page);await expect(page.locator('[data-cad-object-id="pipe"]')).toHaveCount(0);
  const second=await context.newPage();await second.goto("/");await expect(second.getByTestId("workspace-canvas-shell")).toBeVisible();await open(second,projects[0].name);await viewMenu(second);await expect(second.getByLabel("Display units")).toHaveValue("ft");await second.getByLabel("Display units").selectOption("m");await second.getByLabel("Grid and snap spacing").selectOption("10");
  await viewMenu(page);await expect(page.getByLabel("Grid and snap spacing")).toHaveValue("25");
  await page.reload();await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();await viewMenu(page);await expect(page.getByLabel("Grid and snap spacing")).toHaveValue("25");await closeView(page);
  await expect(page.locator('[data-cad-object-id="pipe"]')).toHaveCount(0);
  expect(writes).toBe(0);
  for(const project of projects){const stored=(await(await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project;expect(stored.revision_token).toBe(project.revision_token);expect(stored.project_input).toEqual(project.project_input);}
  // The view-only checks above must not branch. A later actual edit can create
  // an explicitly chosen copy, which inherits this tab's view preferences.
  await closeView(second);await openWorkspaceTool(second,"Draw");
  const manager=second.getByTestId("object-manager-panel");if(!await manager.evaluate(el=>(el as HTMLDetailsElement).open))await manager.locator(":scope > summary").click();
  const row=second.getByTestId("object-manager-row").filter({hasText:"Office"}).first();await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
  await second.getByTestId("selected-object-x-input").fill("175");const branch=second.getByTestId("project-tab-branch-dialog");await expect(branch).toBeVisible();await branch.getByRole("button",{name:"Save as a copy",exact:true}).click();
  await expect.poll(async()=>((await(await request.get(`${api}/api/projects`,{headers})).json()).projects as import("../../app/types").ProjectRecord[]).filter(p=>!projects.some(original=>original.project_id===p.project_id)).length).toBe(1);
  await viewMenu(second);await expect(second.getByLabel("Display units")).toHaveValue("m");await expect(second.getByLabel("Grid and snap spacing")).toHaveValue("10");
  await second.reload();await expect(second.getByTestId("workspace-canvas-shell")).toBeVisible();await viewMenu(second);await expect(second.getByLabel("Grid and snap spacing")).toHaveValue("10");
  const original=(await(await request.get(`${api}/api/projects/${projects[0].project_id}`,{headers})).json()).project;expect(original.project_input).toEqual(projects[0].project_input);
  await second.close();
});

test("offline Mapbox satellite switching preserves camera, overlays, and a remembered map-off choice",async({page},info)=>{
  test.skip(info.project.name!=="chromium","Real WebGL rendering verified in desktop Chromium; map resources are entirely mocked.");
  const styleRequests:string[]=[];
  await page.route(/https:\/\/(?:[^/]+\.)?mapbox\.com\//,async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.includes("/styles/")){
      const name=path.includes("satellite-streets")?"Offline satellite":"Offline streets";styleRequests.push(name);
      await route.fulfill({json:{version:8,name,glyphs:"https://api.mapbox.com/fonts/v1/mapbox/{fontstack}/{range}.pbf",sources:{},layers:[{id:"offline-background",type:"background",paint:{"background-color":"#e2e8f0"}}]}});
    }else if(path.includes("mapbox.terrain-rgb"))await route.fulfill({json:{tilejson:"2.2.0",tiles:[],minzoom:0,maxzoom:14}});
    else await route.fulfill({status:204,body:""});
  });
  await openMapAnchoredFixture(page);
  const summary=()=>page.evaluate(()=>(window as unknown as {__civoraMapLayerSummary?:{styleName:string;layersReady:{buildings:boolean};featureCounts:{buildings:number}}}).__civoraMapLayerSummary);
  await expect.poll(async()=>(await summary())?.styleName).toBe("Offline satellite");
  const camera=await page.evaluate(()=>(window as unknown as {__civoraMapViewport:unknown}).__civoraMapViewport);
  await layersMenu(page);const satellite=page.getByTestId("environment-context-layers").getByRole("button",{name:"Satellite",exact:false});
  await satellite.click();await expect(satellite).toHaveAttribute("aria-pressed","false");await expect.poll(async()=>(await summary())?.styleName).toBe("Offline streets");
  await expect.poll(async()=>(await summary())?.layersReady.buildings).toBe(true);expect((await summary())?.featureCounts.buildings).toBe(1);
  expect(await page.evaluate(()=>(window as unknown as {__civoraMapViewport:unknown}).__civoraMapViewport)).toEqual(camera);
  await satellite.click();await expect.poll(async()=>(await summary())?.styleName).toBe("Offline satellite");
  await page.getByTestId("preview-layer-menu").locator(":scope > summary").click();
  const map=page.getByTestId("preview-inner-map-toggle");await map.click();await expect(map).toHaveAttribute("aria-pressed","false");
  const requestsBeforeReload=styleRequests.length;await page.reload();await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();await expect(map).toHaveAttribute("aria-pressed","false");await expect(page.locator("canvas.mapboxgl-canvas")).toHaveCount(0);
  expect(styleRequests.length).toBe(requestsBeforeReload);
});
