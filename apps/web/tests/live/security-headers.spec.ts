import { expect, test } from "@playwright/test";

const publicRoutes = ["/", "/pilot", "/support", "/upgrades", "/validation/terrain", "/demo/workspace"];

test("public pages send baseline browser security headers", async ({ request }) => {
  for (const route of publicRoutes) {
    const response = await request.get(route);
    expect(response.ok(), `${route} should load`).toBeTruthy();
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
    expect(response.headers()["x-frame-options"]).toBe("DENY");
    expect(response.headers()["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(response.headers()["permissions-policy"]).toBe("camera=(), microphone=(), geolocation=()");
  }
});
