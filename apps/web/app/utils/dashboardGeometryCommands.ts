import type { BuildingPlacement } from "../types";

export type DashboardGeometryCommand =
  | { kind: "move"; targetText: string; distance: number; direction: string }
  | { kind: "resize"; targetText: string; width: number; depth: number };

/** The strict command bar and conversational adapter retain their accepted grammar. */
export function parseDashboardGeometryCommand(message: string, grammar: "strict" | "conversational"): DashboardGeometryCommand | null {
  const text = message.trim().toLowerCase().replace(/\s+/g, " ");
  const move = grammar === "strict"
    ? text.match(/^move\s+(.+?)\s+(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(north|south|east|west|up|down|left|right)$/)
    : text.match(/\bmove\b.*?\b(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(north|south|east|west|up|down|left|right)\b/);
  if (move) {
    const offset = grammar === "strict" ? 1 : 0;
    return { kind: "move", targetText: offset ? move[1] : "", distance: Number(move[1 + offset]), direction: move[2 + offset] };
  }
  const resize = grammar === "strict"
    ? text.match(/^(?:set|make|resize|change)\s+(.+?)\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?$/)
    : text.match(/\b(?:set|make|resize|change)\b.*?\b(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?/);
  if (!resize) return null;
  const offset = grammar === "strict" ? 1 : 0;
  return { kind: "resize", targetText: offset ? resize[1] : "", width: Number(resize[1 + offset]), depth: Number(resize[2 + offset]) };
}

/** Both chat adapters build the same patch; guarded canonical edits decide acceptance. */
export function buildDashboardGeometryCommandUpdates(target: BuildingPlacement, command: DashboardGeometryCommand): Partial<BuildingPlacement> {
  const meta = { ...(target.meta ?? {}), canonical_edit_source: "chat" };
  if (command.kind === "resize") return { w: command.width, d: command.depth, meta };
  const { direction, distance } = command;
  const dx = direction === "east" || direction === "right" ? distance : direction === "west" || direction === "left" ? -distance : 0;
  const dy = direction === "south" || direction === "down" ? distance : direction === "north" || direction === "up" ? -distance : 0;
  return { x: (target.x ?? 0) + dx, y: (target.y ?? 0) + dy, placed: true, meta };
}
