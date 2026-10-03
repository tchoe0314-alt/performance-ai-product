// Freeze identity into the production artifact, not its later runtime environment.
export const dynamic = "force-static";

export function GET() {
  const candidate = (process.env.CIVORA_BUILD_REVISION || process.env.VERCEL_GIT_COMMIT_SHA || "").trim();
  const revision = /^[a-f0-9]{40}$/i.test(candidate) ? candidate.toLowerCase() : "";
  return Response.json({ service: "civora-web", revision, status: revision ? "known" : "unknown" });
}
