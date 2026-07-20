import type { DrawMode } from "./cadToolTypes";
import {
  parseCadNumber,
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

type HandlePreviewCadTransformCommandContext = {
  commandKey: string;
  args: string[];
  firstValue: string;
  selectedRequested: boolean;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setCadCommandDraft: (command: string) => void;
  setCadTransformValue: (value: string) => void;
  moveSelectedCadObjectsByVector: (dx: number, dy: number) => void;
  copySelectedCadObjectsByVector: (vectorOverride?: [number, number]) => void;
  transformSelectedCadObjects: (operation: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", value: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadTransformCommand({
  commandKey,
  args,
  firstValue,
  selectedRequested,
  setCadActiveCommand,
  setCadCommandDraft,
  setCadTransformValue,
  moveSelectedCadObjectsByVector,
  copySelectedCadObjectsByVector,
  transformSelectedCadObjects,
  pushCadCommandFeedback,
}: HandlePreviewCadTransformCommandContext) {
  if (commandKey === "MOVE") {
    const vectorArg = args.find((arg) => arg.toLowerCase() !== "selected");
    const vector = vectorArg ? parseCadVectorToken(vectorArg) : null;
    if (!args.length) {
      setCadActiveCommand({ command: "MOVE", kind: "transform" });
      setCadCommandDraft("");
      pushCadCommandFeedback("MOVE", "info", "MOVE active. Type a vector like 20,0, @20,0, @75<45, or a distance like 5 for a diagonal move.");
    } else if (selectedRequested && vector) {
      moveSelectedCadObjectsByVector(vector[0], vector[1]);
    } else {
      setCadTransformValue(firstValue);
      transformSelectedCadObjects("move", firstValue);
    }
    return true;
  }
  if (commandKey === "ROTATE" || commandKey === "SCALE") {
    if (!args.length) {
      setCadActiveCommand({ command: commandKey as "ROTATE" | "SCALE", kind: "transform" });
      setCadCommandDraft("");
      pushCadCommandFeedback(commandKey, "info", `${commandKey} active. Type ${commandKey === "ROTATE" ? "an angle like 45" : "a factor like 1.2"}.`);
    } else {
      setCadTransformValue(firstValue);
      transformSelectedCadObjects(commandKey.toLowerCase() as "rotate" | "scale", firstValue);
    }
    return true;
  }
  if (commandKey === "COPY") {
    if (!args.length) {
      setCadActiveCommand({ command: "COPY", kind: "transform" });
      setCadCommandDraft("");
      pushCadCommandFeedback("COPY", "info", "COPY active. Type a vector like 10,10, @20,0, @75<45, or run empty to use the default offset.");
    } else {
      const vectorArg = args.find((arg) => arg.toLowerCase() !== "selected");
      copySelectedCadObjectsByVector((vectorArg ? parseCadVectorToken(vectorArg) : null) ?? [10, 10]);
    }
    return true;
  }
  if (commandKey === "MIRROR" || commandKey === "FLIP") {
    const axisArg = (args[0] || "").trim().toLowerCase();
    const horizontal = ["h", "x", "horizontal"].includes(axisArg);
    const vertical = ["v", "y", "vertical"].includes(axisArg);
    if (!horizontal && !vertical) {
      pushCadCommandFeedback(commandKey, "blocked", `${commandKey} blocked: use ${commandKey} H or ${commandKey} V after selecting editable draft objects.`);
      return true;
    }
    transformSelectedCadObjects(horizontal ? "flip_horizontal" : "flip_vertical", "0");
    return true;
  }
  return false;
}

type HandlePreviewCadGeometryCommandContext = {
  commandKey: string;
  args: string[];
  pointArgs: Array<[number, number]>;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setDrawMode: (mode: DrawMode) => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  createCadCommandGeometry: (
    command: string,
    mode: "polyline" | "polygon" | "rect" | "point",
    points: Array<[number, number]>,
    options?: { label?: string; meta?: Record<string, unknown>; minPoints?: number },
  ) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadGeometryCommand({
  commandKey,
  args,
  pointArgs,
  setDraftPoints,
  setDraftPreviewPoint,
  setCadActiveCommand,
  setDrawMode,
  onSetPreviewInteraction,
  createCadCommandGeometry,
  pushCadCommandFeedback,
}: HandlePreviewCadGeometryCommandContext) {
  if (commandKey === "LINE") {
    if (pointArgs.length >= 2) {
      createCadCommandGeometry("LINE", "polyline", pointArgs, { label: "Command Line", minPoints: 2 });
    } else {
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand({ command: "LINE", kind: "draw", mode: "polyline", minPoints: 2 });
      setDrawMode("polyline");
      onSetPreviewInteraction("edit");
      pushCadCommandFeedback("LINE", "info", "LINE active. Type the first point like 0,0, then the next point like 100,0. Press Enter/Run empty to finish.");
    }
    return true;
  }
  if (commandKey === "PLINE") {
    if (pointArgs.length >= 2) {
      createCadCommandGeometry("PLINE", "polyline", pointArgs, { label: "Command Polyline", minPoints: 2 });
    } else {
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand({ command: "PLINE", kind: "draw", mode: "polyline", minPoints: 2 });
      setDrawMode("polyline");
      onSetPreviewInteraction("edit");
      pushCadCommandFeedback("PLINE", "info", "PLINE active. Type points one at a time, then press Enter/Run empty to finish.");
    }
    return true;
  }
  if (commandKey === "RECTANGLE" || commandKey === "BOX") {
    if (pointArgs.length >= 2) {
      createCadCommandGeometry("RECTANGLE", "rect", pointArgs.slice(0, 2), { label: "Command Rectangle", minPoints: 2 });
    } else {
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand({ command: "RECTANGLE", kind: "draw", mode: "rect", minPoints: 2 });
      setDrawMode("rect");
      onSetPreviewInteraction("edit");
      pushCadCommandFeedback("RECTANGLE", "info", "RECTANGLE active. Type first corner like 0,0, then opposite corner like 100,60.");
    }
    return true;
  }
  if (commandKey === "CIRCLE") {
    const radius = parseCadNumber(args[1] ?? args[0] ?? "", NaN);
    const center = pointArgs[0];
    if (!center || !Number.isFinite(radius) || radius <= 0) {
      pushCadCommandFeedback("CIRCLE", "blocked", "CIRCLE blocked: use CIRCLE centerX,centerY radius.");
      return true;
    }
    const points = Array.from({ length: 32 }, (_, index) => {
      const radians = (index / 32) * Math.PI * 2;
      return [center[0] + Math.cos(radians) * radius, center[1] + Math.sin(radians) * radius] as [number, number];
    });
    createCadCommandGeometry("CIRCLE", "polygon", points, {
      label: "Command Circle",
      meta: { cad_curve_storage: "32_segment_chord_polygon", cad_radius_ft: radius },
      minPoints: 3,
    });
    return true;
  }
  if (commandKey === "ARC") {
    const center = pointArgs[0];
    const radius = parseCadNumber(args[1] ?? "", NaN);
    const startDeg = parseCadNumber(args[2] ?? "", NaN);
    const endDeg = parseCadNumber(args[3] ?? "", NaN);
    if (!center || !Number.isFinite(radius) || radius <= 0 || !Number.isFinite(startDeg) || !Number.isFinite(endDeg)) {
      pushCadCommandFeedback("ARC", "blocked", "ARC blocked: use ARC centerX,centerY radius startDeg endDeg.");
      return true;
    }
    const sweep = endDeg >= startDeg ? endDeg - startDeg : endDeg + 360 - startDeg;
    const steps = Math.max(4, Math.ceil(sweep / 12));
    const points = Array.from({ length: steps + 1 }, (_, index) => {
      const radians = ((startDeg + (sweep * index) / steps) * Math.PI) / 180;
      return [center[0] + Math.cos(radians) * radius, center[1] + Math.sin(radians) * radius] as [number, number];
    });
    createCadCommandGeometry("ARC", "polyline", points, {
      label: "Command Arc",
      meta: { cad_curve_storage: "sampled_chord_polyline", cad_radius_ft: radius, cad_start_deg: startDeg, cad_end_deg: endDeg },
      minPoints: 2,
    });
    return true;
  }
  return false;
}
