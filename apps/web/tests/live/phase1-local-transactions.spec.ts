import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import {expect,test,type Page,type APIRequestContext} from "@playwright/test";
import {randomUUID} from "node:crypto";
import {withCanonicalCanvasSnapshot} from "../../app/utils/canonicalCanvasProject";
const api=process.env.PLAYWRIGHT_API_BASE_URL??"";
test.beforeEach(()=>test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS!=="1"||!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api),"Disposable local accounts only."));
async function fixture(page:Page,request:APIRequestContext,name:string,concept=false){
  const response=await request.post(`${api}/api/auth/register`,{data:{email:`transactions-${randomUUID()}@example.test`,password:"Disposable-history-123",name:"History fixture"}});expect(response.status()).toBe(200);
  const auth=await response.json();const headers={Authorization:`Bearer ${auth.token}`};
  const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:withCanonicalCanvasSnapshot({input_mode:"user",manual_fields:{units:"ft",project_name:name,lot:{x:0,y:0,w:900,h:700},site_objects:[{id:"a",label:"History building",type:"building",x:100,y:100,w:100,d:100,placed:true,source:"manual_drawn",...(concept?{meta:{dense_concept_generated:true,requested_area_sf:10000,building_use:"office"}}:{})},{id:"b",label:"History neighbor",type:concept?"parking":"building",x:350,y:100,w:80,d:80,placed:true,source:"manual_drawn",...(concept?{stallCount:20,meta:{dense_concept_generated:true,requested_stalls:20}}:{})}]}})}});expect(created.status()).toBe(200);
  const {project}=await created.json();
  await page.addInitScript(token=>{sessionStorage.setItem("civora-ai-token",token);sessionStorage.setItem("civora-ai-session-auth-restore","1");},auth.token);
  await page.goto("/");await page.getByTestId("header-projects-button").click();await page.getByRole("button",{name:`Open project ${name}`,exact:true}).click();
  await expect(page.getByTestId("header-projects-button")).toContainText(name);
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const snapshot=async()=>(await (await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project.project_input;
  const x=async()=>(await snapshot()).manual_fields.site_objects.find((item:{id:string})=>item.id==="a").x;
  return {snapshot,x,token:auth.token};
}
async function inspect(page:Page,name="History building"){
  await openWorkspaceTool(page, "Draw");const panel=page.getByTestId("object-manager-panel");if(!(await panel.evaluate(element=>element.hasAttribute("open"))))await panel.locator("summary").click();
  const row=page.getByTestId("object-manager-row").filter({hasText:name}).first();await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
}
test("website persists undo redo and abandoned branches across repeated reloads",async({page,request})=>{
  const {snapshot,x}=await fixture(page,request,"Durable history fixture");await inspect(page);
  await page.getByTestId("selected-object-x-input").fill("140");await expect.poll(x).toBe(140);
  await page.getByTestId("selected-object-x-input").fill("180");await expect.poll(x).toBe(180);
  const old=(await snapshot()).meta.edit_history_v1.transactions.map((tx:{id:string})=>tx.id);
  await page.reload();await expect(page.getByRole("button",{name:"Undo last draft change",exact:true})).toBeEnabled();
  await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(x).toBe(140);
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(x).toBe(100);
  await page.reload();await page.getByRole("button",{name:"Redo draft change",exact:true}).click();await expect.poll(x).toBe(140);
  await inspect(page);await page.getByTestId("selected-object-x-input").fill("230");await expect.poll(x).toBe(230);
  const branch=(await snapshot()).meta.edit_history_v1;expect(branch.redo).toEqual([]);for(const id of old)expect(branch.transactions.map((tx:{id:string})=>tx.id)).toContain(id);
  await page.reload();await expect(page.getByRole("button",{name:"Redo draft change",exact:true})).toBeDisabled();
  await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(x).toBe(140);
});
test("failed save retains live edit and history until retry succeeds",async({page,request})=>{
  const {snapshot,x}=await fixture(page,request,"Save failure fixture");await inspect(page);let failures=0;
  await page.route(`${api}/api/projects`,async route=>{if(route.request().method()==="POST"){failures++;await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Synthetic temporary save failure"})});}else await route.continue();});
  await page.getByTestId("selected-object-x-input").fill("175");await expect.poll(()=>failures).toBeGreaterThan(0);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("175");expect(await x()).toBe(100);
  await page.unroute(`${api}/api/projects`);
  await page.getByTestId("selected-object-x-input").fill("190");await expect.poll(x).toBe(190);
  expect((await snapshot()).meta.edit_history_v1.transactions.some((tx:{after:{manual_fields:{site_objects:Array<{id:string;x:number}>}}})=>tx.after.manual_fields.site_objects.find(item=>item.id==="a")?.x===175)).toBe(true);
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(x).toBe(175);
});
test("one undo reverses a complete multi-object group after reopening",async({page,request})=>{
  const {snapshot}=await fixture(page,request,"Atomic group fixture");
  await openWorkspaceTool(page, "Draw");
  const panel=page.getByTestId("object-manager-panel");if(!(await panel.evaluate(element=>element.hasAttribute("open"))))await panel.locator("summary").click();
  for(const name of ["History building","History neighbor"])await page.getByTestId("object-manager-row").filter({hasText:name}).getByTestId("object-manager-bulk-select").check();
  await page.getByTestId("object-manager-combine-name").fill("Atomic group");await page.getByTestId("object-manager-group-action").click();
  await expect.poll(async()=>(await snapshot()).manual_fields.site_objects.filter((item:{type:string})=>item.type==="group").length).toBe(1);
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();
  await expect.poll(async()=>(await snapshot()).manual_fields.site_objects.filter((item:{type:string})=>item.type==="group").length).toBe(0);
  expect((await snapshot()).manual_fields.site_objects.filter((item:{meta?:{group_id?:string}})=>item.meta?.group_id)).toHaveLength(0);
  await page.reload();await page.getByRole("button",{name:"Redo draft change",exact:true}).click();
  await expect.poll(async()=>(await snapshot()).manual_fields.site_objects.filter((item:{type:string})=>item.type==="group").length).toBe(1);
});
test("one saved undo reverses a complete multi-object chat revision",async({page,request})=>{
  const {snapshot}=await fixture(page,request,"Chat transaction fixture",true);
  await page.keyboard.press(process.platform==="darwin"?"Meta+K":"Control+K");
  const command=page.getByTestId("civora-command-input");
  await command.fill("Revise the office building to 20,000 sf and increase parking to 30 spaces.");await command.press("Enter");
  await expect.poll(async()=>(await snapshot()).manual_fields.site_objects.find((item:{id:string})=>item.id==="a").meta.requested_area_sf).toBe(20000);
  const saved=await snapshot();expect(saved.manual_fields.site_objects.find((item:{id:string})=>item.id==="b").meta.requested_stalls).toBe(30);
  const head=saved.meta.edit_history_v1.transactions.find((tx:{id:string})=>tx.id===saved.meta.edit_history_v1.head);
  expect(head.affected_object_ids).toEqual(expect.arrayContaining(["a","b"]));
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();
  await expect.poll(async()=>(await snapshot()).manual_fields.site_objects.find((item:{id:string})=>item.id==="a").meta.requested_area_sf).toBe(10000);
  expect((await snapshot()).manual_fields.site_objects.find((item:{id:string})=>item.id==="b").meta.requested_stalls).toBe(20);
});
test("explicit two-tab replacement retains both branches and following edits still save",async({page,context,request})=>{
  const {snapshot,x,token}=await fixture(page,request,"Divergent tab fixture");await inspect(page);
  const second=await context.newPage();await second.addInitScript(value=>{sessionStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  await second.goto("/");await second.getByTestId("header-projects-button").click();await second.getByRole("button",{name:"Open project Divergent tab fixture",exact:true}).click();await inspect(second);
  await page.getByTestId("selected-object-x-input").fill("140");
  await page.getByTestId("project-tab-branch-dialog").getByRole("button",{name:"Replace original",exact:true}).click();await expect.poll(x).toBe(140);
  const original=(await snapshot()).meta.edit_history_v1.transactions.map((tx:{id:string})=>tx.id);
  await second.getByTestId("selected-object-x-input").fill("175");
  await second.getByTestId("project-tab-branch-dialog").getByRole("button",{name:"Replace original",exact:true}).click();await expect.poll(x).toBe(175);
  for(const id of original)expect((await snapshot()).meta.edit_history_v1.transactions.map((tx:{id:string})=>tx.id)).toContain(id);
  await second.getByTestId("selected-object-x-input").fill("200");await expect.poll(x).toBe(200);
  await second.close();
});
