import type { DrawMode } from "./cadToolTypes";
import {
  parseCadPointToken,
  parseCadPointTokens,
  parseCadRelativePointToken,
  parseCadVectorToken,
} from "./previewCadCommandParsing";
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

type HandlePreviewCadActiveCommandInputContext = {
  cadActiveCommand: CadActiveCommand;
  raw: string;
  tokens: string[];
  selectedCadObject: unknown | null;
  selectedCadIds: string[];
  draftPoints: Array<[number, number]>;
  setCadOffsetDistance: (value: string) => void;
  setCadTransformValue: (value: string) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setCadCommandDraft: (command: string) => void;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setDrawMode: (mode: DrawMode) => void;
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
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadActiveCommandInput({
  cadActiveCommand,
  raw,
  tokens,
  selectedCadObject,
  selectedCadIds,
  draftPoints,
  setCadOffsetDistance,
  setCadTransformValue,
  setCadActiveCommand,
  setCadCommandDraft,
  setDraftPoints,
  setDraftPreviewPoint,
  setDrawMode,
  offsetSelectedCadObjectBy,
  trimExtendSelectedCadObject,
  moveSelectedCadObjectsByVector,
  copySelectedCadObjectsByVector,
  transformSelectedCadObjects,
  createCadCommandGeometry,
  pushCadCommandFeedback,
}: HandlePreviewCadActiveCommandInputContext) {
  if (cadActiveCommand.kind === "offset") {
    const distance = Number(raw);
    if (!Number.isFinite(distance) || Math.abs(distance) < 0.001) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET expected a non-zero distance like 10.");
      return true;
    }
    setCadOffsetDistance(String(distance));
    if (!selectedCadObject) {
      setCadActiveCommand({ command: "OFFSET", kind: "offset", distance });
      setCadCommandDraft("");
      pushCadCommandFeedback("OFFSET", "info", `OFFSET distance set to ${distance}. Select one draft object, then run OFFSET or press Run empty.`);
      return true;
    }
    offsetSelectedCadObjectBy(String(distance));
    setCadActiveCommand(null);
    setCadCommandDraft("");
    return true;
  }
  if (cadActiveCommand.kind === "modify") {
    const amount = Number(raw);
    if (!Number.isFinite(amount) || Math.abs(amount) < 0.001) {
      pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} expected a non-zero amount like 8.`);
      return true;
    }
    setCadTransformValue(String(amount));
    if (!selectedCadObject) {
      setCadActiveCommand({ command: cadActiveCommand.command, kind: "modify", amount });
      setCadCommandDraft("");
      pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} amount set to ${amount}. Select one line/polyline draft object, then run ${cadActiveCommand.command} or press Run empty.`);
      return true;
    }
    trimExtendSelectedCadObject(cadActiveCommand.command.toLowerCase() as "trim" | "extend", String(amount));
    setCadActiveCommand(null);
    setCadCommandDraft("");
    return true;
  }
  if (cadActiveCommand.kind === "transform") {
    setCadActiveCommand({ command: cadActiveCommand.command, kind: "transform", value: raw });
    setCadCommandDraft("");
    if (!selectedCadObject && cadActiveCommand.command === "COPY") {
      pushCadCommandFeedback("COPY", "info", `COPY vector set to ${raw}. Select one editable draft object, then run COPY or press Run empty.`);
      return true;
    }
    if (!selectedCadIds.length && cadActiveCommand.command !== "COPY") {
      pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} value set to ${raw}. Select one or more editable draft objects, then run ${cadActiveCommand.command} or press Run empty.`);
      return true;
    }
    if (cadActiveCommand.command === "MOVE") {
      const vector = parseCadVectorToken(raw);
      if (vector) {
        moveSelectedCadObjectsByVector(vector[0], vector[1]);
      } else {
        transformSelectedCadObjects("move", raw);
      }
    } else if (cadActiveCommand.command === "COPY") {
      copySelectedCadObjectsByVector(parseCadVectorToken(raw) ?? undefined);
    } else {
      transformSelectedCadObjects(cadActiveCommand.command.toLowerCase() as "rotate" | "scale", raw);
    }
    setCadActiveCommand(null);
    return true;
  }
  const activePoints = parseCadPointTokens(tokens);
  if (!activePoints.length) {
    pushCadCommandFeedback(
      cadActiveCommand.command,
      "blocked",
      `${cadActiveCommand.command} expected a coordinate like 100,50, or press Enter to finish.`,
    );
    return true;
  }
  const nextPoints = [...draftPoints, ...activePoints];
  if (cadActiveCommand.mode === "rect" && nextPoints.length >= 2) {
    createCadCommandGeometry("RECTANGLE", "rect", nextPoints.slice(0, 2), { label: "Command Rectangle", minPoints: 2 });
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    setCadActiveCommand(null);
    setDrawMode("select");
    setCadCommandDraft("");
    return true;
  }
  setDraftPoints(nextPoints);
  setCadCommandDraft("");
  pushCadCommandFeedback(
    cadActiveCommand.command,
    "info",
    `${cadActiveCommand.command} accepted ${nextPoints.length} point${nextPoints.length === 1 ? "" : "s"}. Type next point or press Enter/Run with an empty command to finish.`,
  );
  return true;
}

type HandlePreviewActiveCanvasDrawInputContext = {
  raw: string;
  drawMode: DrawMode;
  draftPoints: Array<[number, number]>;
  draftPreviewPoint: [number, number] | null;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setCadCommandDraft: (command: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewActiveCanvasDrawInput({
  raw,
  drawMode,
  draftPoints,
  draftPreviewPoint,
  setDraftPoints,
  setDraftPreviewPoint,
  setCadCommandDraft,
  pushCadCommandFeedback,
}: HandlePreviewActiveCanvasDrawInputContext) {
  const basePoint = draftPoints.length ? draftPoints[draftPoints.length - 1] : null;
  const typedPoint = parseCadPointToken(raw) ?? parseCadRelativePointToken(raw, basePoint);
  const typedDistance = Number(raw);
  let nextPoint: [number, number] | null = typedPoint;
  if (!nextPoint && Number.isFinite(typedDistance) && Math.abs(typedDistance) > 0.001) {
    if (!basePoint) {
      pushCadCommandFeedback("DRAW", "blocked", "DRAW distance input needs a first point. Pick a start point or type x,y first.");
      return true;
    }
    const guidePoint = draftPreviewPoint ?? ([basePoint[0] + 1, basePoint[1]] as [number, number]);
    const dx = guidePoint[0] - basePoint[0];
    const dy = guidePoint[1] - basePoint[1];
    const length = Math.hypot(dx, dy);
    const unit = length > 0.001 ? { x: dx / length, y: dy / length } : { x: 1, y: 0 };
    nextPoint = [
      Math.round((basePoint[0] + unit.x * typedDistance) * 1000) / 1000,
      Math.round((basePoint[1] + unit.y * typedDistance) * 1000) / 1000,
    ];
  }
  if (!nextPoint) {
    pushCadCommandFeedback("DRAW", "blocked", "DRAW expected 100,50, @20,0, @75<45, or a distance like 75 while a draw tool is active.");
    return true;
  }
  const nextPoints = [...draftPoints, nextPoint];
  setDraftPoints(nextPoints);
  setDraftPreviewPoint(null);
  setCadCommandDraft("");
  const minPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
  const readyText = nextPoints.length >= minPoints ? " Press Enter/Finish to complete." : "";
  pushCadCommandFeedback(
    "DRAW",
    "info",
    `DRAW accepted point ${nextPoints.length} at ${nextPoint[0].toFixed(1)},${nextPoint[1].toFixed(1)}.${readyText}`,
  );
  return true;
}
