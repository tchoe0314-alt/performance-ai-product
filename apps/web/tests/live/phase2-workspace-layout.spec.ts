import {test,expect} from "@playwright/test";
import {randomUUID} from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import {DEFAULT_WORKSPACE_LAYOUT,parseWorkspaceLayout} from "../../app/utils/workspaceLayout";

test("layout validation rejects invalid sizes and flags",()=>{
  expect(parseWorkspaceLayout({...DEFAULT_WORKSPACE_LAYOUT,leftWidth:Infinity})).toEqual(DEFAULT_WORKSPACE_LAYOUT);
  expect(parseWorkspaceLayout({...DEFAULT_WORKSPACE_LAYOUT,leftVisible:"true"})).toEqual(DEFAULT_WORKSPACE_LAYOUT);
});
test("professional layout controls have no serious accessibility violations",async({page})=>{
  await page.setViewportSize({width:1280,height:900});await page.goto("/demo/workspace");await page.getByTestId("workspace-layout-controls").locator("summary").click();await page.getByLabel("Workspace mode",{exact:true}).selectOption("professional");
  const report=await new AxeBuilder({page}).include('[data-testid="workspace-layout-root"]').analyze();expect(report.violations.filter(item=>["serious","critical"].includes(item.impact??""))).toEqual([]);
});
for(const viewport of [{width:320,height:568},{width:844,height:390}])test(`mobile panels can switch and exit without clipping at ${viewport.width}`,async({page})=>{
  await page.setViewportSize(viewport);await page.goto("/demo/workspace");const controls=page.getByTestId("workspace-layout-controls");await controls.locator("summary").click();await page.getByLabel("Workspace mode",{exact:true}).selectOption("professional");
  await expect(page.getByTestId("workspace-brief-chat")).toBeVisible();await page.getByLabel("Mobile supporting panel").selectOption("inspector");await expect(page.getByTestId("workspace-inspector-health")).toBeVisible();await expect(page.getByTestId("workspace-brief-chat")).not.toBeVisible();
  const menu=await controls.locator("div").first().boundingBox();expect(menu!.y+menu!.height).toBeLessThanOrEqual(viewport.height);
  await page.getByLabel("Mobile supporting panel").selectOption("delta");await expect(page.getByTestId("workspace-live-delta")).toBeVisible();await page.getByRole("button",{name:"Full canvas",exact:true}).click();await expect(page.getByTestId("workspace-layout-root")).toHaveAttribute("data-layout-focus","true");await page.getByRole("button",{name:"Reset layout",exact:true}).click();await expect(page.getByTestId("floating-command-bar")).toBeVisible();
});
for(const width of [1024,1280,1920])test(`two supporting panels keep usable canvas at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:900});await page.goto("/demo/workspace");
  const controls=page.getByTestId("workspace-layout-controls");await controls.locator("summary").click();await page.getByLabel("Workspace mode",{exact:true}).selectOption("professional");
  await expect(page.getByTestId("workspace-brief-chat")).toBeVisible();await expect(page.getByTestId("workspace-inspector-health")).toBeVisible();await expect(page.getByTestId("workspace-live-delta")).toBeVisible();
  const resize=page.getByRole("separator",{name:"Resize brief and chat",exact:true});await resize.focus();await page.keyboard.press("ArrowRight");await expect(resize).toHaveAttribute("aria-valuenow","270");
  if(width===1280){const handle=await resize.boundingBox();await page.mouse.move(handle!.x+handle!.width/2,handle!.y+20);await page.mouse.down();await page.mouse.move(handle!.x+handle!.width/2+40,handle!.y+20);await page.mouse.up();await expect(resize).toHaveAttribute("aria-valuenow","310");}
  const canvas=await page.getByTestId("workspace-canvas-frame").boundingBox();expect(canvas!.width).toBeGreaterThan(350);
  await controls.locator("summary").click();await page.screenshot({path:test.info().outputPath(`professional-${width}.png`)});await controls.locator("summary").click();
  await page.reload();await controls.locator("summary").click();await expect(page.getByLabel("Workspace mode",{exact:true})).toHaveValue("professional");await expect(page.getByLabel("Brief width",{exact:true})).toHaveValue(width===1280?"310":"270");
  await page.getByRole("button",{name:"Full canvas",exact:true}).click();await expect(page.getByTestId("workspace-layout-root")).toHaveAttribute("data-layout-focus","true");await expect(page.getByTestId("left-sidebar")).not.toBeVisible();
  await page.getByRole("button",{name:"Exit focus",exact:true}).click();await expect(page.getByTestId("workspace-brief-chat")).toBeVisible();
  await page.getByRole("button",{name:"Reset layout",exact:true}).click();await expect(page.getByLabel("Workspace mode",{exact:true})).toHaveValue("simple");await expect(page.getByTestId("workspace-brief-chat")).toHaveCount(0);await page.reload();await controls.locator("summary").click();await expect(page.getByLabel("Workspace mode",{exact:true})).toHaveValue("simple");
});

test("denied layout cache does not prevent resizing or reset",async({page})=>{
  await page.addInitScript(()=>{const get=Storage.prototype.getItem,set=Storage.prototype.setItem;Storage.prototype.getItem=function(key){if(key.startsWith("civora-layout-v1:"))throw new Error("Denied");return get.call(this,key);};Storage.prototype.setItem=function(key,value){if(key.startsWith("civora-layout-v1:"))throw new Error("Denied");return set.call(this,key,value);};});
  await page.goto("/demo/workspace");await page.getByTestId("workspace-layout-controls").locator("summary").click();await page.getByLabel("Workspace mode",{exact:true}).selectOption("professional");await expect(page.getByTestId("workspace-brief-chat")).toBeVisible();await page.getByRole("button",{name:"Reset layout",exact:true}).click();await expect(page.getByLabel("Workspace mode",{exact:true})).toHaveValue("simple");
});

test("account layout survives another device context and never changes project revisions",async({page,context,request,browser})=>{
  const api=process.env.PLAYWRIGHT_API_BASE_URL??"";test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS!=="1"||!/^http:\/\/(127\.0\.0\.1|localhost):/.test(api),"Disposable local accounts only.");
  const registered=await request.post(`${api}/api/auth/register`,{data:{email:`layout-${randomUUID()}@example.test`,password:"Disposable-123",name:"Layout user"}});expect(registered.status()).toBe(200);const {token}=await registered.json(),headers={Authorization:`Bearer ${token}`};
  const created=await request.post(`${api}/api/projects`,{headers,data:{name:"Layout identity",project_input:{}}});expect(created.status()).toBe(200);const project=(await created.json()).project;
  await context.addInitScript(value=>{localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);
  await page.goto("/");const controls=page.getByTestId("workspace-layout-controls");await controls.locator("summary").click();await page.getByLabel("Workspace mode",{exact:true}).selectOption("professional");
  await expect.poll(async()=>((await(await request.get(`${api}/api/account/workspace-layout`,{headers})).json()).layout.mode)).toBe("professional");
  const isolated=await browser.newContext();await isolated.addInitScript(value=>{localStorage.setItem("civora-ai-token",value);sessionStorage.setItem("civora-ai-session-auth-restore","1");},token);const other=await isolated.newPage();await other.goto(new URL("/",page.url()).toString());await other.getByTestId("workspace-layout-controls").locator("summary").click();await expect(other.getByLabel("Workspace mode",{exact:true})).toHaveValue("professional");
  await other.getByRole("button",{name:"Reset layout",exact:true}).click();await expect.poll(async()=>((await(await request.get(`${api}/api/account/workspace-layout`,{headers})).json()).layout.mode)).toBe("simple");
  const after=(await(await request.get(`${api}/api/projects/${project.project_id}`,{headers})).json()).project;expect(after.revision_token).toBe(project.revision_token);expect(after.project_input).toEqual(project.project_input);await isolated.close();
});
