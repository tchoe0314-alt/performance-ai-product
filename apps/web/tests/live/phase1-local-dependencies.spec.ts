import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import {expect,test,type Page,type APIRequestContext} from "@playwright/test";
import {randomUUID} from "node:crypto";
import type {BuildingPlacement} from "../../app/types";
import {withCanonicalCanvasSnapshot} from "../../app/utils/canonicalCanvasProject";
const api=process.env.PLAYWRIGHT_API_BASE_URL??"";
test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS!=="1"||!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api),"Disposable local backend only.");
const item=(id:string,type:BuildingPlacement["type"],x:number):BuildingPlacement=>({id,label:id,type,x,y:100,w:60,d:60,placed:true,source:"manual_drawn"});
async function fixture(page:Page,request:APIRequestContext,objects:BuildingPlacement[]){
  const authResponse=await request.post(`${api}/api/auth/register`,{data:{email:`links-${randomUUID()}@example.test`,password:"Disposable-links-123",name:"Links"}});expect(authResponse.status()).toBe(200);
  const auth=await authResponse.json(),headers={Authorization:`Bearer ${auth.token}`},name=`Links ${randomUUID()}`;
  const created=await request.post(`${api}/api/projects`,{headers,data:{name,project_input:withCanonicalCanvasSnapshot({input_mode:"user",manual_fields:{units:"ft",project_name:name,lot:{x:0,y:0,w:1200,h:900},site_objects:objects}})}});expect(created.status()).toBe(200);
  const {project}=await created.json();const snapshot=async()=>(await(await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project.project_input;
  const object=async(id:string)=>(await snapshot()).manual_fields.site_objects.find((value:{id:string})=>value.id===id);
  await page.addInitScript(token=>{sessionStorage.setItem("civora-ai-token",token);sessionStorage.setItem("civora-ai-session-auth-restore","1");},auth.token);
  await page.goto("/");await page.getByTestId("header-projects-button").click();await page.getByRole("button",{name:`Open project ${name}`,exact:true}).click();await expect(page.getByText(`Restored "${name}".`,{exact:true})).toBeVisible();
  return {snapshot,object};
}
async function inspect(page:Page,id:string){
  await openWorkspaceTool(page, "Draw");const panel=page.getByTestId("object-manager-panel");if(!await panel.evaluate(el=>el.hasAttribute("open")))await panel.locator("summary").click();
  const row=page.getByTestId("object-manager-row").filter({hasText:id}).first();await row.getByTestId("object-manager-select").click();await row.getByTestId("object-manager-inspect").click();
}
async function editor(page:Page){const details=page.getByTestId("object-dependency-editor");if(!await details.evaluate(el=>el.hasAttribute("open")))await details.locator("summary").click();}
test("website edits and persists all four road-parking policies with atomic saved Undo",async({page,request},testInfo)=>{
  const {object,snapshot}=await fixture(page,request,[item("Road source","road",100),item("Parking target","parking",400)]);
  await inspect(page,"Road source");await editor(page);const policy=page.getByTestId("dependency-policy-Parking target");
  await expect(policy).toHaveValue("unlinked");await policy.selectOption("ask");await expect.poll(async()=>(await object("Road source")).meta?.dependency_links_v1?.[0]?.policy).toBe("ask");
  await page.getByTestId("selected-object-x-input").fill("150");await expect(page.getByTestId("dependency-proposal-card")).toBeVisible();expect((await object("Road source")).x).toBe(100);expect((await object("Parking target")).x).toBe(400);
  const card=page.getByTestId("dependency-proposal-card");
  if(await card.getAttribute("data-presentation")==="canvas"){
    const bounds=(await card.boundingBox())!,toolbar=(await page.getByRole("button",{name:"2D",exact:true}).first().boundingBox())!;
    expect(bounds.y).toBeGreaterThan(toolbar.y+toolbar.height);
  }
  await page.getByTestId("dependency-proposal-reject").click({trial:true});await page.getByTestId("dependency-proposal-accept").click({trial:true});
  await page.screenshot({path:testInfo.outputPath("dependency-proposal.png"),fullPage:true});
  await page.getByTestId("dependency-proposal-reject").click();await page.getByTestId("selected-object-x-input").fill("180");await page.getByTestId("dependency-proposal-accept").click();await expect.poll(async()=>(await object("Parking target")).x).toBe(480);
  expect((await snapshot()).canonical_project_v1.dependencies).toEqual(expect.arrayContaining([expect.objectContaining({kind:"road_parking",policy:"ask"})]));
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(async()=>(await object("Road source")).x).toBe(100);expect((await object("Parking target")).x).toBe(400);
  await page.getByRole("button",{name:"Redo draft change",exact:true}).click();await expect.poll(async()=>(await object("Parking target")).x).toBe(480);
  await inspect(page,"Road source");await editor(page);await policy.selectOption("follow");await page.getByTestId("selected-object-x-input").fill("205");await expect.poll(async()=>(await object("Parking target")).x).toBe(505);
  await policy.selectOption("fixed");await expect.poll(async()=>(await object("Road source")).meta?.dependency_links_v1?.[0]?.policy).toBe("fixed");await inspect(page,"Parking target");await page.getByTestId("selected-object-x-input").fill("600");await expect(page.getByTestId("selected-object-x-input")).toHaveValue("505");expect((await object("Parking target")).x).toBe(505);
  await inspect(page,"Road source");await editor(page);await policy.selectOption("independent");await page.getByTestId("selected-object-x-input").fill("230");await expect.poll(async()=>(await object("Road source")).x).toBe(230);expect((await object("Parking target")).x).toBe(505);
});
test("stale proposal cannot overwrite an intervening object edit",async({page,request})=>{
  const road={...item("Road source","road",100),meta:{dependency_links_v1:[{id:"link",kind:"access_road",target_id:"Access target",policy:"ask"}]}},access=item("Access target","entrance",400);
  const {object}=await fixture(page,request,[road,access]);await inspect(page,"Road source");await page.getByTestId("selected-object-x-input").fill("150");await expect(page.getByTestId("dependency-proposal-card")).toBeVisible();
  await inspect(page,"Access target");await page.getByTestId("selected-object-x-input").fill("460");await expect.poll(async()=>(await object("Access target")).x).toBe(460);
  await page.getByTestId("dependency-proposal-accept").click();await expect(page.getByTestId("dependency-proposal-card")).not.toBeVisible();expect((await object("Road source")).x).toBe(100);expect((await object("Access target")).x).toBe(460);
});
test("quantity Ask previews the whole dimension edit; Follow recalculates after save and reload",async({page,request})=>{
  const {object}=await fixture(page,request,[item("Quantity building","building",100)]);await inspect(page,"Quantity building");await editor(page);
  await page.getByTestId("quantity-dependency-policy").selectOption("ask");await page.getByTestId("selected-object-width-input").fill("100");await expect(page.getByTestId("dependency-proposal-card")).toBeVisible();expect((await object("Quantity building")).w).toBe(60);
  await page.getByTestId("dependency-proposal-accept").click();await expect.poll(async()=>(await object("Quantity building")).w).toBe(100);
  expect((await object("Quantity building")).meta.geometry_quantity_v1.area).toBe(6000);
  await page.reload();await inspect(page,"Quantity building");await editor(page);await expect(page.getByTestId("dependency-quantity-value")).toContainText("6000.0");
  await page.getByTestId("quantity-dependency-policy").selectOption("follow");await page.getByTestId("selected-object-width-input").fill("120");await expect.poll(async()=>(await object("Quantity building")).meta.geometry_quantity_v1.area).toBe(7200);
});
test("bulk canvas transforms pass through the same Ask graph and accept one complete transaction",async({page,request})=>{
  const road={...item("Road source","road",100),meta:{dependency_links_v1:[{id:"link",kind:"access_road",target_id:"Access target",policy:"ask"}]}},access=item("Access target","entrance",400),other=item("Other building","building",700);
  const {object}=await fixture(page,request,[road,access,other]);
  await openWorkspaceTool(page, "Draw");const panel=page.getByTestId("object-manager-panel");if(!await panel.evaluate(el=>el.hasAttribute("open")))await panel.locator("summary").click();
  for(const name of ["Road source","Other building"])await page.getByTestId("object-manager-row").filter({hasText:name}).getByTestId("object-manager-bulk-select").check();
  await page.getByTestId("object-manager-bulk-move-x").fill("40");await page.getByTestId("object-manager-bulk-move-y").fill("0");await page.getByTestId("object-manager-bulk-move-action").click();await expect(page.getByTestId("dependency-proposal-card")).toBeVisible();expect((await object("Road source")).x).toBe(100);expect((await object("Other building")).x).toBe(700);
  await page.getByTestId("dependency-proposal-accept").click();await expect.poll(async()=>(await object("Access target")).x).toBe(440);expect((await object("Other building")).x).toBe(740);
  await page.reload();await page.getByRole("button",{name:"Undo last draft change",exact:true}).click();await expect.poll(async()=>(await object("Access target")).x).toBe(400);expect((await object("Other building")).x).toBe(700);
});
