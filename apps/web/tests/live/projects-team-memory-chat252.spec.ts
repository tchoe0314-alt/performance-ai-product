import { expect, test, type Page, type Route } from "@playwright/test";

type Project = {
  project_id: string;
  name: string;
  description: string;
  updated_at: number;
  archived_at?: number | null;
  deleted_at?: number | null;
  project_input: Record<string, unknown>;
  latest_result: Record<string, unknown>;
};

async function installApi(page: Page) {
  const projects = new Map<string, Project>([
    [
      "alpha-site",
      {
        project_id: "alpha-site",
        name: "Alpha Site",
        description: "Commercial review",
        updated_at: 1_800_000_000,
        project_input: { input_mode: "user", manual_fields: {}, meta: { site_inputs: {} } },
        latest_result: {},
      },
    ],
  ]);
  const comments: Array<Record<string, unknown>> = [];
  const reviews: Array<Record<string, unknown>> = [];
  const memories: Array<Record<string, unknown>> = [];
  const members = [
    { user_id: "owner", email: "owner@example.com", name: "Owner", role: "owner" },
  ];
  let consent = {
    personal_enabled: false,
    company_enabled: false,
    global_learning_enabled: false,
    default: "off",
  };

  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (path === "/api/auth/status") return json({ success: true, registration_allowed: true });
    if (path === "/api/auth/me") return json({ user: { user_id: "owner", email: "owner@example.com", name: "Owner" } });
    if (path.startsWith("/api/jobs")) return json({ success: true, jobs: [] });
    if (path === "/api/customer-templates") return json({ success: true, registry: { templates: [] } });
    if (path === "/api/utility-catalogs") return json({ success: true, catalog: { records: [] } });

    if (path === "/api/projects" && method === "GET") {
      return json({ success: true, projects: Array.from(projects.values()).filter((item) => !item.deleted_at) });
    }
    if (path === "/api/projects-deleted" && method === "GET") {
      return json({ success: true, projects: Array.from(projects.values()).filter((item) => item.deleted_at) });
    }
    if (path === "/api/projects" && method === "POST") {
      const payload = request.postDataJSON() as Partial<Project>;
      const existing = payload.project_id ? projects.get(payload.project_id) : undefined;
      const project: Project = {
        project_id: payload.project_id || `saved-${projects.size + 1}`,
        name: payload.name || existing?.name || "Untitled Project",
        description: payload.description || existing?.description || "",
        updated_at: Date.now() / 1000,
        project_input: payload.project_input || existing?.project_input || {},
        latest_result: payload.latest_result || existing?.latest_result || {},
      };
      projects.set(project.project_id, project);
      return json({ success: true, project });
    }

    const duplicate = path.match(/^\/api\/projects\/([^/]+)\/duplicate$/);
    if (duplicate && method === "POST") {
      const source = projects.get(duplicate[1])!;
      const project = { ...source, project_id: `${duplicate[1]}-copy`, name: `${source.name} Copy`, updated_at: Date.now() / 1000 };
      projects.set(project.project_id, project);
      return json({ success: true, project });
    }
    const archive = path.match(/^\/api\/projects\/([^/]+)\/archive$/);
    if (archive && method === "PATCH") {
      const project = projects.get(archive[1])!;
      const payload = request.postDataJSON() as { archived: boolean };
      project.archived_at = payload.archived ? Date.now() / 1000 : null;
      return json({ success: true, project });
    }
    const restore = path.match(/^\/api\/projects\/([^/]+)\/restore$/);
    if (restore && method === "POST") {
      const project = projects.get(restore[1])!;
      project.deleted_at = null;
      project.archived_at = null;
      return json({ success: true, project });
    }
    const result = path.match(/^\/api\/projects\/([^/]+)\/result$/);
    if (result && method === "GET") return json({ success: true, project_id: result[1], latest_result: projects.get(result[1])?.latest_result || {} });
    const detail = path.match(/^\/api\/projects\/([^/]+)$/);
    if (detail && method === "GET") return json({ success: true, project: projects.get(detail[1]) });
    if (detail && method === "DELETE") {
      const project = projects.get(detail[1])!;
      project.deleted_at = Date.now() / 1000;
      return json({ success: true, project_id: detail[1], recoverable: true });
    }

    if (/\/presence$/.test(path) && method === "POST") return json({ success: true, presence: { user_id: "owner" } });
    if (/\/admin$/.test(path) && method === "GET") {
      return json({
        success: true,
        current_user_role: "owner",
        permissions: { can_manage_access: true },
        members,
        invites: [],
      });
    }
    if (/\/admin\/invites$/.test(path) && method === "POST") {
      const payload = request.postDataJSON() as { email: string; role: string };
      members.push({ user_id: "reviewer", email: payload.email, name: "Reviewer", role: payload.role });
      return json({ success: true, invite: { status: "accepted" } });
    }
    const member = path.match(/\/admin\/members\/([^/]+)$/);
    if (member && method === "PATCH") {
      const payload = request.postDataJSON() as { role: string };
      const target = members.find((item) => item.user_id === member[1]);
      if (target) target.role = payload.role;
      return json({ success: true, member: target });
    }
    if (member && method === "DELETE") {
      const index = members.findIndex((item) => item.user_id === member[1]);
      if (index >= 0) members.splice(index, 1);
      return json({ success: true });
    }
    if (/\/collaboration$/.test(path) && method === "GET") {
      return json({
        success: true,
        project_id: "alpha-site",
        current_user_role: "owner",
        permissions: { can_comment: true, can_request_review: true, can_manage_access: true },
        presence: [{ user_id: "owner", name: "Owner", email: "owner@example.com", last_seen_at: Date.now() / 1000 }],
        comments,
        review_requests: reviews,
      });
    }
    if (/\/comments$/.test(path) && method === "POST") {
      const payload = request.postDataJSON() as { body: string; mentions: string[] };
      comments.unshift({ comment_id: "comment-1", project_id: "alpha-site", user_id: "owner", author_name: "Owner", ...payload, status: "open", created_at: Date.now() / 1000, updated_at: Date.now() / 1000 });
      return json({ success: true, comment: comments[0] });
    }
    if (/\/review-requests$/.test(path) && method === "POST") {
      const payload = request.postDataJSON() as { assigned_email: string; message: string };
      reviews.unshift({ request_id: "review-1", project_id: "alpha-site", requested_by_user_id: "owner", ...payload, status: "open", created_at: Date.now() / 1000, updated_at: Date.now() / 1000 });
      return json({ success: true, review_request: reviews[0] });
    }
    const reviewRequest = path.match(/\/review-requests\/([^/]+)$/);
    if (reviewRequest && method === "PATCH") {
      const payload = request.postDataJSON() as { status: string };
      const target = reviews.find((item) => item.request_id === reviewRequest[1]);
      if (target) target.status = payload.status;
      return json({ success: true, review_request: target });
    }
    if (path === "/api/memory" && method === "GET") return json({ success: true, consent, items: memories });
    if (path === "/api/memory" && method === "POST") {
      const payload = request.postDataJSON() as { scope: string; category: string; label: string; value: unknown };
      memories.unshift({ memory_id: "memory-1", ...payload, source: "user_explicit", status: "active", suggestion_only: true, engineering_authority: false, created_at: Date.now() / 1000, updated_at: Date.now() / 1000 });
      return json({ success: true, memory: memories[0] });
    }
    if (path === "/api/memory/consent" && method === "PATCH") {
      consent = request.postDataJSON() as typeof consent;
      return json({ success: true, consent });
    }
    if (/^\/api\/memory\/[^/]+$/.test(path) && method === "DELETE") {
      memories.splice(0, memories.length);
      return json({ success: true });
    }
    return json({ success: true });
  });

  await page.addInitScript(() => {
    window.localStorage.setItem("civora-ai-token", "project-team-token");
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
}

async function openProjects(page: Page) {
  const drawer = page.getByTestId("projects-drawer");
  if (!(await drawer.isVisible())) {
    await page.getByTestId("header-projects-button").click();
  }
  await expect(drawer).toBeVisible();
}

test("project lifecycle is reversible and independent", async ({ page }) => {
  await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await openProjects(page);
  await page.getByRole("button", { name: "Open project Alpha Site" }).click();
  await openProjects(page);

  await page.getByRole("button", { name: "Duplicate project Alpha Site" }).click();
  await openProjects(page);
  await expect(page.getByRole("button", { name: "Open project Alpha Site Copy" })).toBeVisible();

  await page.getByRole("button", { name: "Archive project Alpha Site Copy" }).click();
  await page.getByRole("button", { name: "Archived", exact: true }).click();
  await expect(page.getByRole("button", { name: "Unarchive project Alpha Site Copy" })).toBeVisible();
  await page.getByRole("button", { name: "Unarchive project Alpha Site Copy" }).click();

  await page.getByRole("button", { name: "Active", exact: true }).click();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Delete project Alpha Site Copy" }).click();
  await page.getByRole("button", { name: "Recently deleted" }).click();
  await expect(page.getByRole("button", { name: "Restore project Alpha Site Copy" })).toBeVisible();
  await page.getByRole("button", { name: "Restore project Alpha Site Copy" }).click();
  await openProjects(page);
  await expect(page.getByRole("button", { name: "Open project Alpha Site Copy" })).toBeVisible();
});

test("team, comments, review requests, and controlled memory stay contextual", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  await installApi(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await openProjects(page);
  await page.getByRole("button", { name: "Open project Alpha Site" }).click();
  await openProjects(page);
  await page.getByText("Team & memory", { exact: true }).click();

  const teamRegion = page.getByRole("region", { name: "Team" });
  await expect(teamRegion.getByText("Owner", { exact: true })).toBeVisible();
  await expect(teamRegion.getByLabel("Role for Owner")).toHaveText("owner");
  await page.getByLabel("Invite email").fill("reviewer@example.com");
  await page.getByRole("button", { name: "Invite project member" }).click();
  await expect(page.getByRole("status")).toContainText("invitation");
  await expect(page.getByLabel("Role for Reviewer")).toHaveValue("reviewer");
  await page.getByLabel("Role for Reviewer").selectOption("editor");
  await expect(page.getByRole("status")).toContainText("role updated");

  await page.getByRole("textbox", { name: "Project comment", exact: true }).fill("@reviewer@example.com Check the west entrance.");
  await page.getByRole("button", { name: "Add project comment" }).click();
  await expect(page.getByText("Check the west entrance.", { exact: false })).toBeVisible();

  await page.getByLabel("Review assignee email").fill("");
  await page.getByLabel("Review request message").fill("Review drainage and access.");
  await page.getByRole("button", { name: "Request project review" }).click();
  await expect(page.getByText("1 open", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start review" }).click();
  await expect(page.getByRole("status")).toContainText("Review started");
  await page.getByRole("button", { name: "Complete" }).click();
  await expect(page.getByRole("status")).toContainText("Review marked complete");
  await expect(page.getByText("0 open", { exact: true })).toBeVisible();

  await page.getByLabel("Personal").check();
  await page.getByLabel("Memory label").fill("Preserve west entrance");
  await page.getByLabel("Memory note").fill("Keep the entrance available during alternatives.");
  await page.getByRole("button", { name: "Save controlled memory" }).click();
  await expect(page.getByText("Preserve west entrance", { exact: true })).toBeVisible();
  await expect(page.getByText("project · suggestion only", { exact: true })).toBeVisible();
  expect(browserErrors).toEqual([]);
});
