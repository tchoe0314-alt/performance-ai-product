import type { DrawMode } from "./cadToolTypes";
import { parseCadVectorToken } from "./previewCadCommandParsing";
import type { CadActiveCommand } from "../components/previewPanelTypes";

type CadCommandFeedbackStatus = "applied" | "blocked" | "info";

type FinishPreviewCadActiveCommandContext = {
  cadActiveCommand: CadActiveCommand | null;
  draftPoints: Array<[number, number]>;
  offsetSelectedCadObjectBy: (valueOverride?: string) => void;
  trimExtendSelectedCadObject: (operationOverride: "trim" | "extend", amountOverride?: string) => void;
  moveSelectedCadObjectsByVector: (dx: number, dy: number) => void;
  copySelectedCadObjectsByVector: (vectorOverride?: [number, number]) => void;
  transformSelectedCadObjects: (operation: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", value: string) => void;
  createCadCommandGeometry: (
    command: string,
    mode: "polyline" | "polygon" | "rect" | "point",
    points: Array<[number, number]>,
    options?: { label?: string; meta?: Record<string, unknown>; minPoints?: number },
  ) => void;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setDrawMode: (mode: DrawMode) => void;
  setCadCommandDraft: (command: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function finishPreviewCadActiveCommand({
  cadActiveCommand,
  draftPoints,
  offsetSelectedCadObjectBy,
  trimExtendSelectedCadObject,
  moveSelectedCadObjectsByVector,
  copySelectedCadObjectsByVector,
  transformSelectedCadObjects,
  createCadCommandGeometry,
  setDraftPoints,
  setDraftPreviewPoint,
  setCadActiveCommand,
  setDrawMode,
  setCadCommandDraft,
  pushCadCommandFeedback,
}: FinishPreviewCadActiveCommandContext) {
  if (!cadActiveCommand) return false;
  if (cadActiveCommand.kind === "offset") {
    if (typeof cadActiveCommand.distance === "number") {
      offsetSelectedCadObjectBy(String(cadActiveCommand.distance));
      setCadActiveCommand(null);
      setCadCommandDraft("");
      return true;
    }
    pushCadCommandFeedback("OFFSET", "blocked", "OFFSET needs a distance like 10 before it can run.");
    return true;
  }
  if (cadActiveCommand.kind === "modify") {
    if (typeof cadActiveCommand.amount === "number") {
      trimExtendSelectedCadObject(cadActiveCommand.command.toLowerCase() as "trim" | "extend", String(cadActiveCommand.amount));
      setCadActiveCommand(null);
      setCadCommandDraft("");
      return true;
    }
    pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs an amount like 8 before it can run.`);
    return true;
  }
  if (cadActiveCommand.kind === "transform") {
    if (!cadActiveCommand.value) {
      pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs ${cadActiveCommand.command === "MOVE" || cadActiveCommand.command === "COPY" ? "a vector like 20,0 or @75<45" : cadActiveCommand.command === "ROTATE" ? "an angle like 45" : "a factor like 1.2"}.`);
      return true;
    }
    if (cadActiveCommand.command === "MOVE") {
      const vector = parseCadVectorToken(cadActiveCommand.value);
      if (vector) {
        moveSelectedCadObjectsByVector(vector[0], vector[1]);
      } else {
        transformSelectedCadObjects("move", cadActiveCommand.value);
      }
    } else if (cadActiveCommand.command === "COPY") {
      copySelectedCadObjectsByVector(parseCadVectorToken(cadActiveCommand.value) ?? undefined);
    } else {
      transformSelectedCadObjects(cadActiveCommand.command.toLowerCase() as "rotate" | "scale", cadActiveCommand.value);
    }
    setCadActiveCommand(null);
    setCadCommandDraft("");
    return true;
  }
  if (draftPoints.length < cadActiveCommand.minPoints) {
    pushCadCommandFeedback(
      cadActiveCommand.command,
      "blocked",
      `${cadActiveCommand.command} finish blocked: needs at least ${cadActiveCommand.minPoints} point${cadActiveCommand.minPoints === 1 ? "" : "s"}; ${draftPoints.length} entered.`,
    );
    return true;
  }
  createCadCommandGeometry(
    cadActiveCommand.command,
    cadActiveCommand.mode,
    draftPoints,
    {
      label: cadActiveCommand.command === "RECTANGLE" ? "Command Rectangle" : cadActiveCommand.command === "PLINE" ? "Command Polyline" : "Command Line",
      minPoints: cadActiveCommand.minPoints,
    },
  );
  setDraftPoints([]);
  setDraftPreviewPoint(null);
  setCadActiveCommand(null);
  setDrawMode("select");
  setCadCommandDraft("");
  return true;
}
