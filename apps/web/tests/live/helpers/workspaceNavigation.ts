import { expect, type Page } from "@playwright/test";

const destinations = {
  Setup:{stage:"brief",panel:"site_existing"},
  Draw:{stage:"explore",panel:"objects"},
  Generate:{stage:"explore",panel:"generate"},
  Review:{stage:"review",panel:"analysis"},
  Deliver:{stage:"deliver",panel:"deliverables"},
} as const;

export function workspaceToolButton(page:Page,tool:keyof typeof destinations) {
  const labels={Setup:/^(Brief|Setup)$/,Draw:/^(Explore|Draw)$/,Generate:/^(Explore|Generate)$/,Review:/^Review$/,Deliver:/^Deliver$/};
  return page.getByTestId("left-sidebar").getByRole("button",{name:labels[tool]});
}

export function workspaceCommandButton(page: Page) {
  // Current pinned composer and the prior deployed interface. Anchored labels
  // must not match unrelated send-invitation or support actions.
  return page.getByRole("button", { name: /^(Run Civora command|Send)$/ }).filter({ visible: true }).first();
}

export async function openWorkspacePanelByName(page:Page,name:string|RegExp) {
  const tool=(Object.keys(destinations) as Array<keyof typeof destinations>).find(label=>typeof name==="string"?name===label:name.test(label));
  if(tool)return openWorkspaceTool(page,tool);
  const button=page.getByRole("button",{name}).filter({visible:true}).first();await button.click();return button;
}

/** Request a specific tool, not a stage's remembered destination. Existing
 * hosted checks also support the prior deployed navigation until promotion. */
export async function openWorkspaceTool(page:Page, tool:keyof typeof destinations) {
  // After reload, choose the navigation version only once the workspace has
  // mounted. An early count can wrongly select the old deployed navigation.
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const show=page.getByRole("button",{name:"Show left sidebar",exact:true});
  if(await show.isVisible())await show.click();
  const destination=destinations[tool];
  const stage=page.getByTestId(`workspace-stage-${destination.stage}`);
  if(await stage.count()) {
    await stage.click();
    await page.getByTestId("workspace-stage-panel").selectOption(destination.panel);
    return stage;
  }
  const legacy=page.getByRole("button",{name:tool,exact:true}).filter({visible:true}).first();
  await legacy.click();
  return legacy;
}
