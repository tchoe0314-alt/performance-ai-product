import { test, expect } from "@playwright/test";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const api = process.env.CIVORA_IDENTITY_FIXTURE_API || "";
const enabled = process.env.CIVORA_DISPOSABLE_IDENTITY_UI === "1" && /^http:\/\/127\.0\.0\.1:\d+$/.test(api);

test("saved candidate review persists and stale browser decisions conflict", async ({ page, request }) => {
  test.skip(!enabled, "New disposable local fixture required; never a hosted/customer target.");
  expect(test.info().project.use.baseURL).toBe("http://127.0.0.1:49321");
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    return ["http:", "https:"].includes(url.protocol) && ![api, "http://127.0.0.1:49321"].includes(url.origin)
      ? route.abort("blockedbyclient") : route.continue();
  });
  const login = await request.post(`${api}/api/auth/login`, { data: {
    email: "owner@example.test", password: "Synthetic-only-123",
  }});
  expect(login.status()).toBe(200);
  const token = (await login.json()).token;
  const headers = { Authorization: `Bearer ${token}` };
  const report = { feature_candidates: ["b1", "b2"].map(candidate_id => ({
    candidate_id, feature_type: "building_footprint", source_type: "official_gis",
    source_name: "Synthetic offline source", confidence: 0.9, acceptance_status: "pending",
  }))};
  const inputs = { manual_fields: { units: "ft" }, meta: { site_inputs: {
    site_alignment_locked: true, map_feature_detection_report_v1: report,
  }}};
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: "Disposable review test", project_input: inputs,
  }});
  expect(created.status()).toBe(200);
  let project = (await created.json()).project;
  const inboxResponse = await request.get(`${api}/api/projects/${project.project_id}/candidate-review-inbox`, { headers });
  expect(inboxResponse.status()).toBe(200);
  const inbox = (await inboxResponse.json()).candidate_review_inbox_v1;
  const seeded = await request.post(`${api}/api/projects`, { headers, data: {
    project_id: project.project_id, expected_revision: project.revision_token, name: project.name,
    project_input: { ...inputs, meta: { site_inputs: { ...inputs.meta.site_inputs, candidate_review_inbox_v1: inbox } } },
  }});
  expect(seeded.status()).toBe(200);
  project = (await seeded.json()).project;
  await page.addInitScript(({ token, projectId }) => {
    localStorage.setItem("civora-ai-token", token);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
    localStorage.setItem("civora.activeProjectId", projectId);
  }, { token, projectId: project.project_id });
  await page.goto("/");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Projects", exact: true })).toContainText("Disposable review test");
  await openWorkspaceTool(page, "Setup");
  if (!await page.getByTestId("auto-site-context-summary").isVisible()) {
    await page.locator("summary").filter({ hasText: /^Site Context/ }).click();
  }
  await page.getByTestId("review-found-context").click();
  const review = page.getByTestId("detected-items-review");
  await expect(review).toBeVisible();
  const first = review.locator('[data-candidate-id="b1"]');
  await expect(first).toBeVisible();
  const accepted = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/candidate-review"));
  await first.getByRole("button", { name: "Accept", exact: true }).click();
  expect((await accepted).status()).toBe(200);
  await review.getByRole("tab", { name: "Reviewed", exact: true }).click();
  await expect(first).toContainText(/accepted/i);
  await review.getByRole("tab", { name: "Pending", exact: true }).click();
  let beforeRevision = "";
  await page.route(`**/api/projects/${project.project_id}/candidate-review`, async route => {
    const currentResponse = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    const current = (await currentResponse.json()).project;
    const updated = await request.post(`${api}/api/projects`, { headers, data: {
      project_id: current.project_id, expected_revision: current.revision_token, name: "Concurrent synthetic edit",
    }});
    expect(updated.status()).toBe(200);
    beforeRevision = (await updated.json()).project.revision_token;
    await route.continue();
  }, { times: 1 });
  const conflicted = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/candidate-review"));
  await review.locator('[data-candidate-id="b2"]').getByRole("button", { name: "Reject", exact: true }).click();
  expect((await conflicted).status()).toBe(409);
  const afterResponse = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
  const after = (await afterResponse.json()).project;
  expect(beforeRevision).toMatch(/^[a-f0-9]{64}$/);
  expect(after.revision_token).toBe(beforeRevision);
  const savedInbox = after.project_input.meta.site_inputs.candidate_review_inbox_v1;
  expect(savedInbox.candidates.find((item: { candidate_id: string }) => item.candidate_id === "b1").status).toBe("accepted");
  expect(savedInbox.candidates.find((item: { candidate_id: string }) => item.candidate_id === "b2").status).toBe("pending");
  await page.reload();
  await expect(page.getByRole("button", { name: "Projects", exact: true })).toContainText("Concurrent synthetic edit");
  await openWorkspaceTool(page, "Setup");
  if (!await page.getByTestId("auto-site-context-summary").isVisible()) {
    await page.locator("summary").filter({ hasText: /^Site Context/ }).click();
  }
  await page.getByTestId("review-found-context").click();
  await expect(review.locator('[data-candidate-id="b2"]')).toContainText(/pending/i);
  await review.getByRole("tab", { name: "Reviewed", exact: true }).click();
  await expect(first).toContainText(/accepted/i);
  expect(errors).toEqual([]);
});
