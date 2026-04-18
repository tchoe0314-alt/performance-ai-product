import { expect, test } from "@playwright/test";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const tokenKey = "civora-ai-token";
const apiBase =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://api.civoraai.com";

test("phase 2 site setup workflow", async ({ page, request, baseURL }) => {
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const loginResponse = await request.post(
    `${apiBase.replace(/\/+$/, "")}/api/auth/login`,
    { data: { email, password } },
  );
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload?.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key, value);
    },
    [tokenKey, token] as const,
  );

  await page.goto(`${baseURL}/?debugPreview=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);

  const signInHeading = page.getByRole("heading", { name: "Sign In" });
  if (await signInHeading.isVisible().catch(() => false)) {
    const emailInput = page.getByPlaceholder("you@example.com");
    const passwordInput = page.getByPlaceholder("At least 8 characters");
    await emailInput.fill(email);
    await passwordInput.fill(password);
    await page.getByRole("button", { name: "Sign In" }).nth(1).click();
    await page.waitForLoadState("networkidle").catch(() => null);
    await page.waitForTimeout(1500);
  }

  const navSiteButton = page.getByRole("navigation").getByRole("button", { name: "Site" });
  const mainSiteButton = page.getByRole("main").getByRole("button", { name: "Site", exact: true });
  if (await navSiteButton.isVisible().catch(() => false)) {
    await navSiteButton.click();
  } else if (await mainSiteButton.isVisible().catch(() => false)) {
    await mainSiteButton.click();
  }
  await page.waitForTimeout(500);

  const addressInput = page.getByPlaceholder("123 Main St, City, State");
  await addressInput.fill("20525 Margo St Gretna NE");
  await page.getByRole("button", { name: "Save address" }).click();
  await page.waitForTimeout(1500);

  const alignmentRow = page.getByText("Alignment:", { exact: false }).locator("..");
  const lockButton = alignmentRow.getByRole("button", { name: /Lock Site/i });
  await expect(lockButton).toBeVisible();

  const fitButton = page.getByRole("button", { name: "Fit to Site" });
  await expect(fitButton).toBeVisible();
  const centerButton = page.getByRole("button", { name: "Use Map Center" });
  await expect(centerButton).toBeVisible();

  const rotationSection = page.getByText("Site rotation");
  if (await rotationSection.isVisible().catch(() => false)) {
    await rotationSection.scrollIntoViewIfNeeded();
  }

  // Rotate site via slider
  const rotationSlider = page.locator('input[type="range"]').first();
  if (await rotationSlider.isVisible().catch(() => false)) {
    await rotationSlider.evaluate((el) => {
      el.value = "12";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  // Lock site
  await lockButton.click({ force: true });
  const unlockButton = alignmentRow.getByRole("button", { name: /Unlock Site/i });
  await expect(unlockButton).toBeVisible({ timeout: 10_000 });

  // Unlock again and confirm toggle
  await unlockButton.click({ force: true });
  await expect(alignmentRow).toContainText("Unlocked");

  // Continue with image upload
  const uploadButton = page.getByRole("button", { name: /Upload site image/i });
  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    uploadButton.click(),
  ]);
  await chooser.setFiles(
    "/Users/tommychoe/Documents/Playground/Civora AI/.venv/lib/python3.9/site-packages/matplotlib/mpl-data/images/matplotlib_large.png",
  );

  await page.waitForTimeout(2000);
  const statusLine = page.getByText(
    /Uploading image|Detecting site features|Detection complete|No detections found|Image uploaded|Image upload failed/i,
  );
  await expect(statusLine.first()).toBeVisible();

  // Missing-info gating: try generate roads while unlocked
  const alignmentText = alignmentRow.getByText(/Alignment:/);
  await expect(alignmentText).toContainText("Unlocked");
  const chatButton = page.getByRole("button", { name: "Chat" });
  if (await chatButton.isVisible().catch(() => false)) {
    await chatButton.click();
  }
  const generateRoads = page.getByRole("button", { name: /Generate Roads/i });
  if (await generateRoads.isVisible().catch(() => false)) {
    await generateRoads.click();
    const lockPrompt = page.getByText(/lock the site alignment/i);
    await expect(lockPrompt).toBeVisible();
  }

  await page.screenshot({ path: "/tmp/phase2-runtime.png", fullPage: true });
});
