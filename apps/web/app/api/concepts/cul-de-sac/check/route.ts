import { validateTopology } from "../../../../utils/cadGeometryKernel";

// Stateless concept-only adapter. No project records or engineering approvals.
export async function POST(request: Request) {
  let state;
  try { state = await request.json(); } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const inRange = (value: unknown, min: number, max: number) =>
    typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
  if (!state || !inRange(state.bulbRadius, 35, 80) || !inRange(state.roadWidth, 20, 48) ||
      state.transitionRadius !== 20 || state.islandRadius !== 15 ||
      !Number.isSafeInteger(state.revision) || state.revision < 0 ||
      !state.building || !inRange(state.building.x, -100, 100) ||
      !inRange(state.building.y, -80, 220) || state.building.w !== 20 || state.building.d !== 20) {
    return Response.json({ error: "Invalid concept dimensions" }, { status: 400 });
  }
  const R = state.bulbRadius;
  const bottom = Math.sqrt((R + 20) ** 2 - (state.roadWidth / 2 + 20) ** 2) + 110;
  // Tiny broad-phase padding includes touching boundaries, not just penetration.
  const tolerance = 1e-6;
  const issues = validateTopology([
    { id: "concept-road", x: -R - tolerance, y: -R - tolerance, w: 2 * R + 2 * tolerance, d: bottom + R + 2 * tolerance },
    { id: "test-building", x: state.building.x, y: state.building.y, w: 20, d: 20 },
  ]);
  return Response.json({ revision: state.revision, issues, check: "bounding-box-only" },
    { headers: { "Cache-Control": "no-store" } });
}
