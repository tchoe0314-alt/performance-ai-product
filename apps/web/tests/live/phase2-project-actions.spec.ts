import {test,expect} from "@playwright/test";
import {randomUUID} from "node:crypto";
import {withCanonicalCanvasSnapshot} from "../../app/utils/canonicalCanvasProject";

for(const viewport of [{width:320,height:568},{width:844,height:390},{width:1280,height:720}]){
  test(`project actions and saved-history dialog fit ${viewport.width}x${viewport.height}`,async({page})=>{
    await page.setViewportSize(viewport);await page.goto("/demo/workspace");
    const actions=page.getByTestId("workspace-project-actions");await actions.locator("summary").click();
    await expect(actions.getByRole("button",{name:"Share",exact:true})).toBeDisabled();
    const menu=await actions.locator("div").first().boundingBox();expect(menu).not.toBeNull();expect(menu!.x).toBeGreaterThanOrEqual(0);expect(menu!.x+menu!.width).toBeLessThanOrEqual(viewport.width);
    await actions.getByRole("button",{name:"Edit history",exact:true}).click();
    const dialog=page.getByRole("dialog",{name:"Edit history"});await expect(dialog).toBeVisible();await expect(dialog).toContainText("Save and sign in");
    await page.keyboard.press("Escape");await expect(dialog).toHaveCount(0);
    await actions.locator("summary").click();await actions.getByRole("button",{name:"Project settings",exact:true}).click();await expect(page.getByTestId("project-header-details")).toBeVisible();
  });
}

test("saved project actions open sharing with viewer default and named saved history",async({page,context,request})=>{
  const api=process.env.PLAYWRIGHT_API_BASE_URL??"";test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS!=="1"||!/^http:\/\/(127\.0\.0\.1|localhost):/.test(api),"Disposable local account only.");
  const register=async(name:string)=>{const response=await request.post(`${api}/api/auth/register`,{data:{name,email:`actions-${name}-${randomUUID()}@example.test`,password:"Disposable-123"}});expect(response.status()).toBe(200);return response.json();};
  const owner=await register("Creator"),editor=await register("Editor"),headers={Authorization:`Bearer ${owner.token}`};
  const input=withCanonicalCanvasSnapshot({manual_fields:{units:"ft",lot:{x:0,y:0,w:900,h:700},site_objects:[{id:"a",type:"office_building",label:"Office",x:100,y:100,w:100,d:80}]}});
  const created=await request.post(`${api}/api/projects`,{headers,data:{name:"Action project",project_input:input}});expect(created.status()).toBe(200);const project=(await created.json()).project;
  const invite=await request.post(`${api}/api/projects/${project.project_id}/admin/invites`,{headers,data:{email:editor.user.email,role:"editor"}});expect(invite.status()).toBe(200);
  const changed=withCanonicalCanvasSnapshot({...input,manual_fields:{...input.manual_fields,site_objects:[{id:"a",type:"office_building",label:"Office",x:150,y:100,w:100,d:80}]}});
  const saved=await request.post(`${api}/api/projects`,{headers:{Authorization:`Bearer ${editor.token}`},data:{project_id:project.project_id,name:"Action project",project_input:changed,expected_revision:project.revision_token}});expect(saved.status()).toBe(200);
  await context.addInitScript(token=>{localStorage.setItem("civora-ai-token",token);sessionStorage.setItem("civora-ai-session-auth-restore","1");},owner.token);
  await page.goto("/");await page.getByTestId("header-projects-button").click();await page.getByRole("button",{name:"Open project Action project",exact:true}).click();
  const actions=page.getByTestId("workspace-project-actions");await actions.locator("summary").click();await actions.getByRole("button",{name:"Share",exact:true}).click();
  await expect(page.getByLabel("Invite role")).toBeVisible();await expect(page.getByLabel("Invite role")).toHaveValue("viewer");
  await actions.locator("summary").click();await actions.getByRole("button",{name:"Edit history",exact:true}).click();
  await expect(page.getByTestId("project-edit-history")).toContainText("Creator: Creator");await expect(page.getByTestId("project-edit-history")).toContainText("Editor");
});
