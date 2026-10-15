import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { WORKSPACE_STAGE_KEYS,WORKSPACE_STAGES,emptyStageMemory,parseStageMemory,rememberStagePanel,rememberedStagePanel,stageForPanel,stageStorageKey } from "../../app/utils/workspaceStages";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import AxeBuilder from "@axe-core/playwright";

test("stage memory validates panels and keeps global tools out of remembered destinations",()=>{
  let memory=rememberStagePanel(emptyStageMemory(),"drainage");
  memory=rememberStagePanel(memory,"generate");
  expect(rememberedStagePanel(memory,"analyze")).toBe("drainage");
  expect(rememberedStagePanel(memory,"explore")).toBe("generate");
  for(const panel of ["chat","projects","trust","settings"] as const)expect(rememberStagePanel(memory,panel)).toBe(memory);
  expect(parseStageMemory('{"version":1,"active":"explore","panels":{"explore":"settings","analyze":"objects","brief":"import_survey"}}').panels).toEqual({brief:"import_survey"});
  expect(parseStageMemory("broken")).toEqual(emptyStageMemory());
  expect(parseStageMemory('{"version":2,"active":"explore"}')).toEqual(emptyStageMemory());
  expect(stageStorageKey("owner-a","project-a",1)).not.toBe(stageStorageKey("owner-b","project-a",1));
  const panels=WORKSPACE_STAGE_KEYS.flatMap(stage=>WORKSPACE_STAGES[stage].panels);
  expect(new Set(panels).size).toBe(panels.length);
  for(const stage of WORKSPACE_STAGE_KEYS)expect(stageForPanel(WORKSPACE_STAGES[stage].defaultPanel)).toBe(stage);
});

for(const [width,height]of [[320,568],[844,390],[1280,720]])test(`five free stages remember panels and stay contained at ${width}x${height}`,async({page},info)=>{
  await page.setViewportSize({width,height});
  await page.goto("/demo/workspace?debugPreview=1");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const nav=page.getByTestId("primary-workflow-sidebar");
  await expect(nav.getByRole("button")).toHaveCount(5);
  expect(await nav.getByRole("button").allTextContents()).toEqual(["Brief","Explore","Analyze","Review","Deliver"]);
  const select=page.getByTestId("workspace-stage-panel");
  await page.getByTestId("workspace-stage-analyze").click();await select.selectOption("drainage");
  await expect(page.getByTestId("workspace-stage-analyze")).toHaveAttribute("aria-current","page");
  await page.getByTestId("workspace-stage-explore").click();await select.selectOption("generate");
  await page.getByTestId("header-help-button").click();await expect(page.getByTestId("workspace-stage-explore")).toHaveAttribute("aria-current","page");
  await page.getByTestId("workspace-stage-analyze").click();await expect(select).toHaveValue("drainage");
  await page.getByTestId("workspace-stage-explore").click();await expect(select).toHaveValue("generate");
  await page.getByRole("button",{name:"Minimize",exact:true}).click();await expect(page.getByTestId("workspace-right-panel")).toBeHidden();
  await page.getByTestId("workspace-stage-explore").click();await expect(select).toHaveValue("generate");
  await page.reload();await expect(page.getByTestId("workspace-stage-explore")).toHaveAttribute("aria-current","page");await expect(select).toHaveValue("generate");
  for(const stage of WORKSPACE_STAGE_KEYS){await page.getByTestId(`workspace-stage-${stage}`).click();await expect(select).toHaveValue(stage==="explore"?"generate":stage==="analyze"?"drainage":WORKSPACE_STAGES[stage].defaultPanel);}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  const box=(await nav.boundingBox())!;expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width+1);
  const drawer=page.getByTestId("workspace-right-panel");expect(await drawer.evaluate(el=>el.scrollWidth-el.clientWidth)).toBeLessThanOrEqual(1);
  const violations=(await new AxeBuilder({page}).include('[data-testid="left-sidebar"]').analyze()).violations;
  expect(violations.filter(item=>item.impact==="serious"||item.impact==="critical")).toEqual([]);
  await page.screenshot({path:info.outputPath(`stages-${width}.png`)});
});

test("storage denial still permits switching and remembered panels in this session",async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(window,"sessionStorage",{get:()=>({getItem:()=>{throw new Error("Denied");},setItem:()=>{throw new Error("Denied");}})}));
  await page.goto("/demo/workspace?debugPreview=1");await page.getByTestId("workspace-stage-analyze").click();await page.getByTestId("workspace-stage-panel").selectOption("drainage");
  await page.getByTestId("workspace-stage-brief").click();await page.getByTestId("workspace-stage-analyze").click();await expect(page.getByTestId("workspace-stage-panel")).toHaveValue("drainage");
});

const api=process.env.PLAYWRIGHT_API_BASE_URL??"";
const local=process.env.CIVORA_PHASE0_LOCAL_TESTS==="1"&&/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);
test("project and tab stage memories are independent and switching never writes design inputs",async({page,context,request})=>{
  test.skip(!local,"Disposable local projects only.");
  const registered=await request.post(`${api}/api/auth/register`,{data:{email:`stages-${randomUUID()}@example.test`,password:"Disposable-123",name:"Stages"}});expect(registered.status()).toBe(200);
  const {token}=await registered.json(),headers={Authorization:`Bearer ${token}`};
  const projects=[];
  for(const name of ["Stage project A","Stage project B"]){
    const source=withCanonicalCanvasSnapshot({manual_fields:{project_name:name,units:"ft",lot:{x:0,y:0,w:900,h:700},site_objects:[{id:"office",label:"Office",type:"office_building",x:125,y:120,w:160,d:90}]}});
    const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:source}});expect(created.status()).toBe(200);projects.push((await created.json()).project);
  }
  await context.addInitScript(value=>{if(!location.href.startsWith("http"))return;localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  const open=async(tab:typeof page,name:string)=>{await tab.getByTestId("header-projects-button").click();await tab.getByRole("button",{name:`Open project ${name}`,exact:true}).click();await expect(tab.getByTestId("project-status-summary")).toContainText("Project opened");await expect(tab.getByTestId("projects-drawer")).toBeVisible();await tab.getByTestId("primary-workflow-sidebar").locator('[aria-current="page"]').click();};
  await page.goto("/");await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();await open(page,projects[0].name);
  await page.getByTestId("workspace-stage-analyze").click();await page.getByTestId("workspace-stage-panel").selectOption("drainage");
  await open(page,projects[1].name);await page.getByTestId("workspace-stage-deliver").click();await page.getByTestId("workspace-stage-panel").selectOption("reports");
  await open(page,projects[0].name);await expect(page.getByTestId("workspace-stage-panel")).toHaveValue("drainage");
  const second=await context.newPage();await second.goto("/");await expect(second.getByTestId("workspace-canvas-shell")).toBeVisible();await open(second,projects[0].name);
  await second.getByTestId("workspace-stage-review").click();await page.getByTestId("workspace-stage-explore").click();
  await expect(second.getByTestId("workspace-stage-review")).toHaveAttribute("aria-current","page");
  for(const project of projects){const stored=(await(await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project;expect(stored.revision_token).toBe(project.revision_token);expect(stored.project_input).toEqual(project.project_input);}
  await second.close();await page.reload();await expect(page.getByTestId("workspace-stage-explore")).toHaveAttribute("aria-current","page");
  await open(page,projects[1].name);await expect(page.getByTestId("workspace-stage-panel")).toHaveValue("reports");
  // A failed save must not lose the live edit when changing presets.
  await page.getByTestId("workspace-stage-explore").click();await page.getByTestId("workspace-stage-panel").selectOption("objects");
  const manager=page.getByTestId("object-manager-panel");
  if(!(await manager.evaluate(el=>el.hasAttribute("open"))))await manager.locator(":scope > summary").click();
  const row=page.getByTestId("object-manager-row").filter({hasText:"Office"}).first();
  await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
  let failures=0;
  await page.route(`${api}/api/projects`,async route=>{if(route.request().method()==="POST"){failures++;await route.fulfill({status:503,json:{detail:"Synthetic save interruption"}});}else await route.continue();});
  await page.getByTestId("selected-object-x-input").fill("175");await expect.poll(()=>failures).toBeGreaterThan(0);
  for(const stage of WORKSPACE_STAGE_KEYS)await page.getByTestId(`workspace-stage-${stage}`).click();
  await page.getByTestId("workspace-stage-explore").click();await page.getByTestId("workspace-stage-panel").selectOption("objects");
  if(!(await manager.evaluate(el=>el.hasAttribute("open"))))await manager.locator(":scope > summary").click();
  await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("175");
  await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await page.getByRole("button",{name:"Redo draft change",exact:true}).click();await expect(page.getByTestId("selected-object-x-input")).toHaveValue("175");
  const stored=(await(await request.get(`${api}/api/projects/${projects[1].project_id}`,{headers})).json()).project;
  expect(stored.project_input).toEqual(projects[1].project_input);
});
