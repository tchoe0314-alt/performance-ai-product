import { expect, test } from "@playwright/test";
import { GET } from "../../app/api/release-identity/route";

test("release identity exposes only a validated build revision", async () => {
  const before = { revision: process.env.CIVORA_BUILD_REVISION, vercel: process.env.VERCEL_GIT_COMMIT_SHA };
  try {
    delete process.env.CIVORA_BUILD_REVISION;
    delete process.env.VERCEL_GIT_COMMIT_SHA;
    expect(await GET().json()).toEqual({ service: "civora-web", revision: "", status: "unknown" });
    process.env.VERCEL_GIT_COMMIT_SHA = "a".repeat(40);
    expect((await GET().json()).revision).toBe("a".repeat(40));
    process.env.CIVORA_BUILD_REVISION = "B".repeat(40);
    expect((await GET().json()).revision).toBe("b".repeat(40));
    process.env.CIVORA_BUILD_REVISION = "not-a-revision-or-public-value";
    expect(await GET().json()).toEqual({ service: "civora-web", revision: "", status: "unknown" });
  } finally {
    if (before.revision === undefined) delete process.env.CIVORA_BUILD_REVISION;
    else process.env.CIVORA_BUILD_REVISION = before.revision;
    if (before.vercel === undefined) delete process.env.VERCEL_GIT_COMMIT_SHA;
    else process.env.VERCEL_GIT_COMMIT_SHA = before.vercel;
  }
});
