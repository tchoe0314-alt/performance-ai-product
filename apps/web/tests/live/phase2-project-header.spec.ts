import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { projectEditKey } from "../../app/hooks/useProjectTabBranch";
import { liveInputFingerprint } from "../../app/utils/liveCalculationFreshness";
import { buildDashboardPayloadPreview } from "../../app/utils/dashboardPayloads";

const api=process.env.PLAYWRIGHT_API_BASE_URL??"";
const local=process.env.CIVORA_PHASE0_LOCAL_TESTS==="1"&&/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);
const identity={client:"Client 14",siteId:"Site 81",address:"123 Concept Lane",parcel:"APN-42",stage:"Concept"};

test("identity affects saved-state tracking but never engineering geometry freshness",()=>{
  const before={manual_fields:{project_name:"Before",units:"ft" as const},meta:{site_inputs:{}}};
  const after={...before,manual_fields:{...before.manual_fields,project_name:"After"},meta:{...before.meta,project_identity_v1:identity}};
  expect(projectEditKey(before)).not.toBe(projectEditKey(after));
  expect(projectEditKey(after)).toBe(projectEditKey({...after,meta:{...after.meta,project_identity_v1:{stage:identity.stage,parcel:identity.parcel,address:identity.address,siteId:identity.siteId,client:identity.client}}}));
  expect(liveInputFingerprint(before)).toBe(liveInputFingerprint(after));
  const built=buildDashboardPayloadPreview({projectId:"project",assistedEnabled:false,prompt:"",imageName:"",chatMessages:[],currentProject:{project_id:"project",name:"After",project_input:after},systemStatuses:{} as never,reactiveEditPolicyPreference:{},manualFields:after.manual_fields});
  expect(built.meta?.project_identity_v1).toEqual(identity);
});

for(const [width,height] of [[320,568],[390,844],[844,390],[1280,720]])test(`project details stay contained and keyboard-accessible at ${width}x${height}`,async({page},info)=>{
  await page.setViewportSize({width,height});
  await page.goto("/demo/workspace?debugPreview=1");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByRole("button",{name:"Project details",exact:true}).click();
  const details=page.getByTestId("project-header-details");
  await expect(details).toBeVisible();
  await expect(details).toContainText("Local only");
  await expect(details).toContainText("Last calculation");
  await expect(details.getByRole("button",{name:"Save details"})).toBeDisabled();
  const box=(await details.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width+1);expect(box.y+box.height).toBeLessThanOrEqual(height+1);
  expect(await details.evaluate(el=>el.scrollWidth-el.clientWidth)).toBeLessThanOrEqual(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({path:info.outputPath(`project-header-${width}.png`)});
  await expect(details.getByRole("button",{name:"Close project details"})).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(details).toBeHidden();
  await expect(page.getByRole("button",{name:"Project details",exact:true})).toBeFocused();
});

test("open project-details menu has no serious accessibility violations",async({page})=>{
  await page.goto("/demo/workspace?debugPreview=1");
  await page.getByRole("button",{name:"Project details",exact:true}).click();
  const results=await new AxeBuilder({page}).include("#project-header-details").analyze();
  expect(results.violations.filter(item=>item.impact==="serious"||item.impact==="critical")).toEqual([]);
});

async function openProject(page:import("@playwright/test").Page,name:string){
  await page.goto("/");await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button",{name:`Open project ${name}`,exact:true}).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
}

test("real project details persist, survive geometry autosave, and failures remain honest",async({page,context,request})=>{
  test.skip(!local,"Disposable local accounts only.");
  const registered=await request.post(`${api}/api/auth/register`,{data:{email:`header-${randomUUID()}@example.test`,password:"Disposable-123",name:"Header"}});
  expect(registered.status()).toBe(200);const {token}=await registered.json();const headers={Authorization:`Bearer ${token}`};
  const name=`Header ${randomUUID()}`;
  const source=withCanonicalCanvasSnapshot({input_mode:"user",allow_ai_fill_for_blanks:false,manual_fields:{project_name:name,units:"ft",project_type:"commercial",lot:{x:0,y:0,w:900,h:700},site_objects:[{id:"office",label:"Office",type:"office_building",x:125,y:120,w:160,d:90,source:"manual_drawn"}]}});
  const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:source}});expect(created.status()).toBe(200);const {project}=await created.json();
  await context.addInitScript(value=>{if(!location.href.startsWith("http"))return;localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  await openProject(page,name);
  const details=page.getByTestId("project-header-details");
  await page.getByRole("button",{name:"Project details",exact:true}).click();
  await expect(details).toContainText("Online");
  await expect(details).toContainText("Active revision");
  await details.getByLabel("Project name",{exact:true}).fill("Pilot Header");
  for(const [label,key]of [["Client / ID","client"],["Site ID","siteId"],["Address","address"],["APN / parcel","parcel"],["Project stage","stage"]] as const)await details.getByLabel(label,{exact:true}).fill(identity[key]);
  await details.getByRole("button",{name:"Save details"}).click();await expect(details).toBeHidden();
  const saved=async()=> (await (await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project;
  await expect.poll(async()=> (await saved()).name).toBe("Pilot Header");
  expect((await saved()).project_input.meta.project_identity_v1).toEqual(identity);
  expect((await saved()).project_input.manual_fields.site_objects[0].x).toBe(125);
  await expect(page.getByTestId("header-save-status")).toHaveText("Saved");
  await openWorkspaceTool(page, "Draw");const list=page.getByTestId("object-manager-panel");
  if(!(await list.evaluate(el=>el.hasAttribute("open"))))await list.locator("summary").click();
  const row=page.getByTestId("object-manager-row").filter({hasText:"Office"}).first();await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
  await page.getByTestId("selected-object-x-input").fill("175");await expect.poll(async()=> (await saved()).project_input.manual_fields.site_objects[0].x).toBe(175);
  expect((await saved()).project_input.meta.project_identity_v1).toEqual(identity);
  await page.reload();await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByRole("button",{name:"Project details",exact:true}).click();await expect(details.getByLabel("Client / ID")).toHaveValue(identity.client);await expect(details.getByLabel("Project name",{exact:true})).toHaveValue("Pilot Header");
  await details.getByRole("button",{name:"Cancel",exact:true}).click();
  // The header must use successful history, not a newer failed attempt.
  await page.route("**/calculations",route=>route.fulfill({json:{calculations:[{created_at:1900000000,successful:false},{created_at:1700000000,successful:true,disposition:"archived"}]}}));
  await page.reload();await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();await page.getByRole("button",{name:"Project details",exact:true}).click();
  await expect(details.locator("dt").filter({hasText:"Last calculation"}).locator("+ dd")).not.toHaveText("Not recorded");
  expect(await details.locator("dt").filter({hasText:"Last calculation"}).locator("+ dd").innerText()).toContain("2023");
  await context.setOffline(true);await expect(details).toContainText("Offline");await context.setOffline(false);await expect(details).toContainText("Online");
  await page.route("**/api/health",route=>route.fulfill({status:503,json:{detail:"Test unavailable API"}}));
  await page.evaluate(()=>window.dispatchEvent(new Event("online")));await expect(details).toContainText("API unavailable");
  await page.unroute("**/api/health");await page.evaluate(()=>window.dispatchEvent(new Event("online")));await expect(details).toContainText("Online");
  await page.route("**/api/projects",async route=>{if(route.request().method()==="POST")await route.fulfill({status:503,contentType:"application/json",body:'{"detail":"Test save failure"}'});else await route.continue();});
  await details.getByLabel("Client / ID").fill("Unsaved client");await details.getByRole("button",{name:"Save details"}).click();await expect(details.getByRole("alert")).toContainText("Not saved");await expect(page.getByTestId("header-save-status")).toHaveText("Save failed");
  await expect(details.getByLabel("Client / ID")).toHaveValue("Unsaved client");expect((await saved()).project_input.meta.project_identity_v1.client).toBe(identity.client);
  await page.unroute("**/api/projects");await details.getByRole("button",{name:"Save details"}).click();await expect(details).toBeHidden();await expect.poll(async()=> (await saved()).project_input.meta.project_identity_v1.client).toBe("Unsaved client");
});

test("first identity edit in a second tab forks only after the user's choice",async({page,context,request})=>{
  test.skip(!local,"Disposable local accounts only.");
  const registered=await request.post(`${api}/api/auth/register`,{data:{email:`header-tabs-${randomUUID()}@example.test`,password:"Disposable-123",name:"Header tabs"}});
  expect(registered.status()).toBe(200);const {token}=await registered.json();const headers={Authorization:`Bearer ${token}`};
  const name=`Header tabs ${randomUUID()}`;
  const source=withCanonicalCanvasSnapshot({manual_fields:{project_name:name,units:"ft",lot:{x:0,y:0,w:900,h:700},site_objects:[{id:"office",label:"Office",type:"office_building",x:125,y:120,w:160,d:90}]}});
  const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:source}});expect(created.status()).toBe(200);const {project}=await created.json();
  await context.addInitScript(value=>{if(!location.href.startsWith("http"))return;localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  await openProject(page,name);const second=await context.newPage();await openProject(second,name);
  await second.getByRole("button",{name:"Project details",exact:true}).click();const details=second.getByTestId("project-header-details");
  await details.getByLabel("Client / ID").fill("Separate client");await expect(details).toContainText("Unsaved details");await details.getByRole("button",{name:"Save details"}).click();
  const branch=second.getByTestId("project-tab-branch-dialog");await expect(branch).toBeVisible();
  const original=async()=> (await (await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project;
  expect((await original()).project_input.meta.project_identity_v1).toBeUndefined();
  await branch.getByRole("button",{name:"Save as a copy",exact:true}).click();await expect(branch).toBeHidden();await expect(details).toBeHidden();
  await expect.poll(async()=>{
    const projects=(await (await request.get(`${api}/api/projects`,{headers})).json()).projects;
    const copy=projects.find((item:{project_id:string})=>item.project_id!==project.project_id);
    if(!copy)return null;
    return (await (await request.get(`${api}/api/projects/${copy.project_id}`,{headers})).json()).project.project_input.meta.project_identity_v1?.client;
  }).toBe("Separate client");
  expect((await original()).project_input.meta.project_identity_v1).toBeUndefined();await second.close();
});
