import type { CadToolRequest, DrawMode } from "./cadToolTypes";
import {
  parseCadNumber,
  parseCadPointToken,
  parseCadPointTokens,
  parseCadRelativePointToken,
  parseCadVectorToken,
} from "./previewCadCommandParsing";
import type { CadActiveCommand } from "../components/previewPanelTypes";
import type { BuildingPlacement } from "../types";

type CadCommandFeedbackStatus = "applied" | "blocked" | "info";

type HandlePreviewCadToolRequestContext = {
  cadToolRequest: CadToolRequest;
  lotWidth: number;
  lotHeight: number;
  cadOffsetDistance: string;
  selectedDeletableObject: BuildingPlacement | null;
  setDraftPoints: (points: Array<[number, number]>) => void;
  draftPointsRef?: { current: Array<[number, number]> };
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setDrawAutoFinishPointCount: (count: number | null) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setCadCommandDraft: (command: string | ((value: string) => string)) => void;
  setDrawMode: (mode: DrawMode) => void;
  setManagedObjectId: (id: string | null) => void;
  setHoveredObjectId: (id: string | null) => void;
  setSelectedVertex: (vertex: { id: string; index: number } | null) => void;
  setCadSelectionSet: (ids: string[]) => void;
  setCadSnapEnabled: (updater: boolean | ((value: boolean) => boolean)) => void;
  setCadOrthoEnabled: (updater: boolean | ((value: boolean) => boolean)) => void;
  onSelectBuilding: (id: string | null) => void;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onRemoveBuilding: (id: string) => void;
  transformSelectedCadObjects: (operation: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", value?: string) => void;
  offsetSelectedCadObjectBy: (valueOverride?: string) => void;
  trimExtendSelectedCadObject: (operationOverride: "trim" | "extend", amountOverride?: string) => void;
  filletSelectedCadObject: () => void;
  joinSelectedCadObjects: () => void;
  splitSelectedJoinedObject: () => void;
  changeSelectedPolylineState: (operation: "close" | "open" | "reverse") => void;
  toggleSelectedCadHatch: () => void;
  applySelectedCadDimension: () => void;
  insertCadSymbol: () => void;
  applySelectedCadLayer: () => void;
  applyCadProperties: () => void;
  undoCadCommand: () => void;
  redoCadCommand: () => void;
  runCadCommand: (commandOverride?: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadToolRequest({
  cadToolRequest,
  lotWidth,
  lotHeight,
  cadOffsetDistance,
  selectedDeletableObject,
  setDraftPoints,
  draftPointsRef,
  setDraftPreviewPoint,
  setDrawAutoFinishPointCount,
  setCadActiveCommand,
  setCadCommandDraft,
  setDrawMode,
  setManagedObjectId,
  setHoveredObjectId,
  setSelectedVertex,
  setCadSelectionSet,
  setCadSnapEnabled,
  setCadOrthoEnabled,
  onSelectBuilding,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onRemoveBuilding,
  transformSelectedCadObjects,
  offsetSelectedCadObjectBy,
  trimExtendSelectedCadObject,
  filletSelectedCadObject,
  joinSelectedCadObjects,
  splitSelectedJoinedObject,
  changeSelectedPolylineState,
  toggleSelectedCadHatch,
  applySelectedCadDimension,
  insertCadSymbol,
  applySelectedCadLayer,
  applyCadProperties,
  undoCadCommand,
  redoCadCommand,
  runCadCommand,
  pushCadCommandFeedback,
}: HandlePreviewCadToolRequestContext) {
  onSetPreviewMode("2d");
  onSetPreviewInteraction("edit");

  const activateDrawMode = (mode: DrawMode, label: string, autoFinishPointCount: number | null = null) => {
    if (draftPointsRef) draftPointsRef.current = [];
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    setDrawAutoFinishPointCount(autoFinishPointCount);
    setCadActiveCommand(null);
    onSelectBuilding(null);
    setManagedObjectId(null);
    setHoveredObjectId(null);
    setSelectedVertex(null);
    setCadSelectionSet([]);
    setDrawMode(mode);
    pushCadCommandFeedback(
      label,
      "info",
      autoFinishPointCount
        ? `${label} tool active. Pick ${autoFinishPointCount} point${autoFinishPointCount === 1 ? "" : "s"} on the canvas to create the draft object.`
        : `${label} tool active. Pick points on the canvas, then Finish when shown.`,
    );
  };

  switch (cadToolRequest.tool) {
    case "select":
      setDrawMode("select");
      if (draftPointsRef) draftPointsRef.current = [];
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setDrawAutoFinishPointCount(null);
      pushCadCommandFeedback("SELECT", "info", "SELECT tool active. Click an object on the canvas or choose one from the object list.");
      break;
    case "line":
      activateDrawMode("polyline", "LINE", 2);
      break;
    case "polyline":
      activateDrawMode("polyline", "PLINE");
      break;
    case "area":
      activateDrawMode("polygon", "AREA");
      break;
    case "box":
      activateDrawMode("rect", "RECTANGLE");
      break;
    case "point":
      activateDrawMode("point", "POINT");
      break;
    case "circle":
      setCadCommandDraft(`CIRCLE ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} 25`);
      pushCadCommandFeedback("CIRCLE", "info", "CIRCLE command loaded. Adjust center/radius in the command line, then press Run.");
      break;
    case "arc":
      setCadCommandDraft(`ARC ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} 40 0 90`);
      pushCadCommandFeedback("ARC", "info", "ARC command loaded. Adjust center/radius/start/end in the command line, then press Run.");
      break;
    case "text":
      setCadCommandDraft(`TEXT ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} note`);
      pushCadCommandFeedback("TEXT", "info", "TEXT command loaded. Edit the point and note text, then press Run.");
      break;
    case "move":
      transformSelectedCadObjects("move");
      break;
    case "copy":
      setCadCommandDraft("COPY selected 10,10");
      pushCadCommandFeedback("COPY", "info", "COPY command loaded. Select an object, adjust the vector if needed, then press Run.");
      break;
    case "rotate":
      transformSelectedCadObjects("rotate");
      break;
    case "scale":
      transformSelectedCadObjects("scale");
      break;
    case "offset":
      offsetSelectedCadObjectBy(cadOffsetDistance);
      break;
    case "trim":
      trimExtendSelectedCadObject("trim");
      break;
    case "extend":
      trimExtendSelectedCadObject("extend");
      break;
    case "fillet":
      filletSelectedCadObject();
      break;
    case "join":
      joinSelectedCadObjects();
      break;
    case "split":
      splitSelectedJoinedObject();
      break;
    case "close":
      changeSelectedPolylineState("close");
      break;
    case "open":
      changeSelectedPolylineState("open");
      break;
    case "reverse":
      changeSelectedPolylineState("reverse");
      break;
    case "hatch":
      toggleSelectedCadHatch();
      break;
    case "delete":
      if (selectedDeletableObject) {
        onRemoveBuilding(selectedDeletableObject.id);
        pushCadCommandFeedback("DELETE", "applied", "DELETE removed the selected draft object.");
      } else {
        pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: select one unlocked draft object first.");
      }
      break;
    case "dimension":
      applySelectedCadDimension();
      break;
    case "measure":
      runCadCommand("DIST");
      break;
    case "symbol":
      insertCadSymbol();
      break;
    case "layer":
      applySelectedCadLayer();
      break;
    case "properties":
      applyCadProperties();
      break;
    case "snap":
      setCadSnapEnabled((value) => {
        pushCadCommandFeedback("SNAP", "info", `SNAP ${!value ? "on" : "off"}.`);
        return !value;
      });
      break;
    case "ortho":
      setCadOrthoEnabled((value) => {
        pushCadCommandFeedback("ORTHO", "info", `ORTHO ${!value ? "on" : "off"}.`);
        return !value;
      });
      break;
    case "undo":
      undoCadCommand();
      break;
    case "redo":
      redoCadCommand();
      break;
    case "command":
      if (cadToolRequest.commandText?.trim()) {
        setCadCommandDraft(cadToolRequest.commandText);
        window.requestAnimationFrame(() => runCadCommand(cadToolRequest.commandText));
      } else {
        setCadCommandDraft((value) => value || "LINE 0,0 100,0");
        pushCadCommandFeedback("COMMAND", "info", "Command line focused. Type a command or run the loaded example.");
      }
      break;
    default:
      break;
  }
}

type HandlePreviewCadSelectionCommandContext = {
  commandKey: string;
  args: string[];
  buildingPlacements: BuildingPlacement[];
  selectedCadIds: string[];
  setCadSelectionSet: (ids: string[]) => void;
  onSelectObjects?: (ids: string[]) => void;
  onSelectBuilding: (id: string | null) => void;
  setSelectedVertex: (vertex: { id: string; index: number } | null) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadSelectionCommand({
  commandKey,
  args,
  buildingPlacements,
  selectedCadIds,
  setCadSelectionSet,
  onSelectObjects,
  onSelectBuilding,
  setSelectedVertex,
  pushCadCommandFeedback,
}: HandlePreviewCadSelectionCommandContext) {
  if (commandKey !== "SELECT") return false;
  const mode = (args[0] || "").trim().toUpperCase();
  if (mode === "NONE" || mode === "CLEAR") {
    setCadSelectionSet([]);
    onSelectObjects?.([]);
    onSelectBuilding(null);
    setSelectedVertex(null);
    pushCadCommandFeedback("SELECT", "info", "SELECT NONE cleared the draft object selection.");
    return true;
  }
  const selectableObjects = buildingPlacements.filter((item) => item.type !== "site" && !item.locked);
  if (mode === "ALL") {
    const ids = selectableObjects.map((item) => item.id);
    setCadSelectionSet(ids);
    onSelectObjects?.(ids);
    onSelectBuilding(ids[0] ?? null);
    setSelectedVertex(null);
    pushCadCommandFeedback("SELECT", ids.length ? "applied" : "blocked", ids.length ? `SELECT ALL selected ${ids.length} editable draft object${ids.length === 1 ? "" : "s"}.` : "SELECT ALL found no editable draft objects.");
    return true;
  }
  if (mode === "LAYER") {
    const layer = (args[1] || "").trim().toUpperCase();
    if (!layer) {
      pushCadCommandFeedback("SELECT", "blocked", "SELECT LAYER blocked: provide a layer like SELECT LAYER C-UTIL.");
      return true;
    }
    const ids = selectableObjects
      .filter((item) => String(item.meta?.cad_layer || item.type || "").toUpperCase() === layer)
      .map((item) => item.id);
    setCadSelectionSet(ids);
    onSelectObjects?.(ids);
    onSelectBuilding(ids[0] ?? null);
    setSelectedVertex(null);
    pushCadCommandFeedback("SELECT", ids.length ? "applied" : "blocked", ids.length ? `SELECT LAYER ${layer} selected ${ids.length} editable draft object${ids.length === 1 ? "" : "s"}.` : `SELECT LAYER ${layer} found no editable draft objects.`);
    return true;
  }
  pushCadCommandFeedback("SELECT", "info", `SELECT supports ALL, NONE, CLEAR, or LAYER. Current selection: ${selectedCadIds.length}.`);
  return true;
}

type HandlePreviewCadActiveCommandControlContext = {
  commandKey: string;
  cadActiveCommand: CadActiveCommand | null;
  finishCadActiveCommand: () => void;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setDrawMode: (mode: DrawMode) => void;
  setCadCommandDraft: (command: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadActiveCommandControl({
  commandKey,
  cadActiveCommand,
  finishCadActiveCommand,
  setDraftPoints,
  setDraftPreviewPoint,
  setCadActiveCommand,
  setDrawMode,
  setCadCommandDraft,
  pushCadCommandFeedback,
}: HandlePreviewCadActiveCommandControlContext) {
  if (!cadActiveCommand) return false;
  if (commandKey === "FINISH" || commandKey === "DONE") {
    finishCadActiveCommand();
    return true;
  }
  if (commandKey === "CANCEL" || commandKey === "ESC") {
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    setCadActiveCommand(null);
    setDrawMode("select");
    pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} cancelled.`);
    setCadCommandDraft("");
    return true;
  }
  return false;
}

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

type SelectedCadMetrics = {
  segmentCount: number;
  totalLength: number;
  firstAngle: number;
};

type HandlePreviewCadArrangeMeasureCommandContext = {
  commandKey: string;
  args: string[];
  pointArgs: Array<[number, number]>;
  selectedCadObject: BuildingPlacement | null;
  selectedCadMetrics: SelectedCadMetrics | null;
  visibleCadObjects: BuildingPlacement[];
  getObjectGeometryPoints: (item: BuildingPlacement) => Array<[number, number]>;
  arraySelectedCadObject: (rows: number, columns: number, spacing: [number, number]) => void;
  alignOrDistributeSelectedCadObjects: (
    command: "ALIGN" | "DISTRIBUTE",
    mode: "LEFT" | "RIGHT" | "CENTER" | "TOP" | "BOTTOM" | "MIDDLE" | "X" | "Y",
  ) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadArrangeMeasureCommand({
  commandKey,
  args,
  pointArgs,
  selectedCadObject,
  selectedCadMetrics,
  visibleCadObjects,
  getObjectGeometryPoints,
  arraySelectedCadObject,
  alignOrDistributeSelectedCadObjects,
  pushCadCommandFeedback,
}: HandlePreviewCadArrangeMeasureCommandContext) {
  if (commandKey === "ARRAY") {
    const rows = parseCadNumber(args[0] ?? "", 0);
    const columns = parseCadNumber(args[1] ?? "", 0);
    const spacing = parseCadPointToken(args[2] ?? "") ?? [20, 20];
    if (!Number.isFinite(rows) || !Number.isFinite(columns) || rows < 1 || columns < 1) {
      pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: use ARRAY rows columns dx,dy, for example ARRAY 2 3 20,15.");
      return true;
    }
    arraySelectedCadObject(rows, columns, spacing);
    return true;
  }
  if (commandKey === "ALIGN") {
    const modeArg = (args[0] || "LEFT").trim().toUpperCase();
    const modeAliases: Record<string, "LEFT" | "RIGHT" | "CENTER" | "TOP" | "BOTTOM" | "MIDDLE" | "X" | "Y"> = {
      L: "LEFT",
      LEFT: "LEFT",
      R: "RIGHT",
      RIGHT: "RIGHT",
      C: "CENTER",
      CENTER: "CENTER",
      CENTRE: "CENTER",
      X: "X",
      T: "TOP",
      TOP: "TOP",
      B: "BOTTOM",
      BOTTOM: "BOTTOM",
      M: "MIDDLE",
      MID: "MIDDLE",
      MIDDLE: "MIDDLE",
      Y: "Y",
    };
    const mode = modeAliases[modeArg];
    if (!mode) {
      pushCadCommandFeedback("ALIGN", "blocked", "ALIGN blocked: use ALIGN LEFT, RIGHT, CENTER, TOP, BOTTOM, or MIDDLE.");
      return true;
    }
    alignOrDistributeSelectedCadObjects("ALIGN", mode);
    return true;
  }
  if (commandKey === "DISTRIBUTE") {
    const modeArg = (args[0] || "X").trim().toUpperCase();
    const axis = ["Y", "V", "VERTICAL"].includes(modeArg) ? "Y" : "X";
    alignOrDistributeSelectedCadObjects("DISTRIBUTE", axis);
    return true;
  }
  if (commandKey === "DIST" || commandKey === "MEASURE") {
    if (pointArgs.length >= 2) {
      const [a, b] = pointArgs;
      const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const angle = ((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI + 360) % 360;
      pushCadCommandFeedback("DIST", "info", `DIST ${length.toFixed(2)} ft at ${angle.toFixed(1)} deg between typed points.`);
      return true;
    }
    const fallbackCadObject = selectedCadObject ?? [...visibleCadObjects]
      .reverse()
      .find((item) => item.type !== "site" && getObjectGeometryPoints(item).length >= 2) ?? null;
    const fallbackPoints = fallbackCadObject ? getObjectGeometryPoints(fallbackCadObject) : [];
    const fallbackSegments = fallbackCadObject && fallbackPoints.length >= 2
      ? fallbackPoints.map((point, index) => {
          if (index === fallbackPoints.length - 1 && fallbackCadObject.geometryType === "polyline") return null;
          const next = index === fallbackPoints.length - 1 ? fallbackPoints[0] : fallbackPoints[index + 1];
          return {
            length: Math.hypot(next[0] - point[0], next[1] - point[1]),
            angle: ((Math.atan2(next[1] - point[1], next[0] - point[0]) * 180) / Math.PI + 360) % 360,
          };
        }).filter(Boolean) as Array<{ length: number; angle: number }>
      : [];
    const metrics = selectedCadMetrics ?? (fallbackSegments.length
      ? {
          segmentCount: fallbackSegments.length,
          totalLength: fallbackSegments.reduce((sum, segment) => sum + segment.length, 0),
          firstAngle: fallbackSegments[0]?.angle ?? 0,
        }
      : null);
    if (!metrics || !fallbackCadObject) {
      pushCadCommandFeedback("DIST", "blocked", "DIST blocked: select a draft line/polyline/area or use DIST x1,y1 x2,y2.");
      return true;
    }
    pushCadCommandFeedback(
      "DIST",
      "info",
      `DIST selected ${fallbackCadObject.label || "object"}: ${metrics.totalLength.toFixed(2)} ft total, ${metrics.segmentCount} segment${metrics.segmentCount === 1 ? "" : "s"}, first angle ${metrics.firstAngle.toFixed(1)} deg.`,
    );
    return true;
  }
  return false;
}

type HandlePreviewCadModifyCommandContext = {
  commandKey: string;
  args: string[];
  firstValue: string;
  selectedDeletableObject: BuildingPlacement | null;
  setCadOffsetDistance: (value: string) => void;
  setCadTransformValue: (value: string) => void;
  setCadFilletRadius: (value: string) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setCadCommandDraft: (command: string) => void;
  onRemoveBuilding: (id: string) => void;
  offsetSelectedCadObjectBy: (valueOverride?: string) => void;
  trimExtendSelectedCadObject: (operationOverride: "trim" | "extend", amountOverride?: string) => void;
  filletSelectedCadObject: () => void;
  joinSelectedCadObjects: () => void;
  splitSelectedJoinedObject: () => void;
  changeSelectedPolylineState: (operation: "close" | "open" | "reverse") => void;
  toggleSelectedCadHatch: () => void;
  applySelectedCadDimension: () => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadModifyCommand({
  commandKey,
  args,
  firstValue,
  selectedDeletableObject,
  setCadOffsetDistance,
  setCadTransformValue,
  setCadFilletRadius,
  setCadActiveCommand,
  setCadCommandDraft,
  onRemoveBuilding,
  offsetSelectedCadObjectBy,
  trimExtendSelectedCadObject,
  filletSelectedCadObject,
  joinSelectedCadObjects,
  splitSelectedJoinedObject,
  changeSelectedPolylineState,
  toggleSelectedCadHatch,
  applySelectedCadDimension,
  pushCadCommandFeedback,
}: HandlePreviewCadModifyCommandContext) {
  if (commandKey === "DELETE" || commandKey === "ERASE") {
    if (!selectedDeletableObject) {
      pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: select one unlocked draft object first.");
      return true;
    }
    onRemoveBuilding(selectedDeletableObject.id);
    pushCadCommandFeedback("DELETE", "applied", "DELETE removed the selected draft object. Downstream systems remain review-required until rerun.");
    return true;
  }
  if (commandKey === "OFFSET") {
    if (args.length) {
      setCadOffsetDistance(firstValue);
      offsetSelectedCadObjectBy(firstValue);
      setCadActiveCommand(null);
    } else {
      setCadActiveCommand({ command: "OFFSET", kind: "offset" });
      setCadCommandDraft("");
      pushCadCommandFeedback("OFFSET", "info", "OFFSET active. Type a non-zero distance like 10. Select one draft object first for immediate offset.");
    }
    return true;
  }
  if (commandKey === "TRIM" || commandKey === "EXTEND") {
    if (args.length) {
      setCadTransformValue(firstValue);
      trimExtendSelectedCadObject(commandKey.toLowerCase() as "trim" | "extend", firstValue);
      setCadActiveCommand(null);
    } else {
      setCadActiveCommand({ command: commandKey as "TRIM" | "EXTEND", kind: "modify" });
      setCadCommandDraft("");
      pushCadCommandFeedback(commandKey, "info", `${commandKey} active. Type an amount like 8. Select one line/polyline draft object first for immediate ${commandKey.toLowerCase()}.`);
    }
    return true;
  }
  if (commandKey === "FILLET") {
    setCadFilletRadius(firstValue);
    filletSelectedCadObject();
    return true;
  }
  if (commandKey === "JOIN") {
    joinSelectedCadObjects();
    return true;
  }
  if (commandKey === "SPLIT" || commandKey === "BREAK") {
    splitSelectedJoinedObject();
    return true;
  }
  if (commandKey === "CLOSE") {
    changeSelectedPolylineState("close");
    return true;
  }
  if (commandKey === "OPEN") {
    changeSelectedPolylineState("open");
    return true;
  }
  if (commandKey === "REVERSE") {
    changeSelectedPolylineState("reverse");
    return true;
  }
  if (commandKey === "HATCH") {
    toggleSelectedCadHatch();
    return true;
  }
  if (commandKey === "DIM") {
    applySelectedCadDimension();
    return true;
  }
  return false;
}

type HandlePreviewCadAnnotationSettingsCommandContext = {
  commandKey: string;
  args: string[];
  pointArgs: Array<[number, number]>;
  selectedCadIds: string[];
  buildingPlacements: BuildingPlacement[];
  cadLayerOptions: string[];
  cadSnapEnabled: boolean;
  cadOrthoEnabled: boolean;
  setHiddenCadLayers: (updater: string[] | ((prev: string[]) => string[])) => void;
  setCadLayerDraft: (layer: string) => void;
  setCadSnapEnabled: (enabled: boolean) => void;
  setCadOrthoEnabled: (enabled: boolean) => void;
  createCadCommandGeometry: (
    command: string,
    mode: "polyline" | "polygon" | "rect" | "point",
    points: Array<[number, number]>,
    options?: { label?: string; meta?: Record<string, unknown>; minPoints?: number },
  ) => void;
  updateCadObject: (item: BuildingPlacement, updates: Partial<BuildingPlacement>, label: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

export function handlePreviewCadAnnotationSettingsCommand({
  commandKey,
  args,
  pointArgs,
  selectedCadIds,
  buildingPlacements,
  cadLayerOptions,
  cadSnapEnabled,
  cadOrthoEnabled,
  setHiddenCadLayers,
  setCadLayerDraft,
  setCadSnapEnabled,
  setCadOrthoEnabled,
  createCadCommandGeometry,
  updateCadObject,
  pushCadCommandFeedback,
}: HandlePreviewCadAnnotationSettingsCommandContext) {
  if (commandKey === "TEXT") {
    const point = pointArgs[0];
    const text = args.filter((arg) => !parseCadPointToken(arg)).join(" ").trim();
    if (!point || !text) {
      pushCadCommandFeedback("TEXT", "blocked", "TEXT blocked: use TEXT x,y note text.");
      return true;
    }
    createCadCommandGeometry("TEXT", "point", [point], { label: text.slice(0, 48), meta: { cad_text: text, cad_layer: "C-ANNO" }, minPoints: 1 });
    return true;
  }
  if (commandKey === "LAYER") {
    const layerAction = (args[0] || "").trim().toUpperCase();
    const layer = (args[1] || "").trim().toUpperCase();
    if (layerAction === "ALL" || layerAction === "SHOWALL") {
      setHiddenCadLayers([]);
      pushCadCommandFeedback("LAYER", "applied", "LAYER ALL showed every draft layer.");
      return true;
    }
    if (["HIDE", "OFF", "SHOW", "ON", "ONLY", "ISOLATE"].includes(layerAction)) {
      if (!layer) {
        pushCadCommandFeedback("LAYER", "blocked", `LAYER ${layerAction} blocked: provide a layer name like LAYER ${layerAction} C-UTIL.`);
        return true;
      }
      if (layerAction === "HIDE" || layerAction === "OFF") {
        setHiddenCadLayers((prev) => Array.from(new Set([...prev, layer])));
        pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} hid ${layer}.`);
        return true;
      }
      if (layerAction === "SHOW" || layerAction === "ON") {
        setHiddenCadLayers((prev) => prev.filter((item) => item !== layer));
        pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} showed ${layer}.`);
        return true;
      }
      setHiddenCadLayers(cadLayerOptions.filter((item) => item !== layer));
      pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} isolated ${layer}.`);
      return true;
    }
    const targetLayer = layerAction;
    if (!targetLayer) {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: provide a layer name like LAYER C-UTIL.");
      return true;
    }
    setCadLayerDraft(targetLayer);
    if (selectedCadIds.length) {
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") return;
        updateCadObject(target, { meta: { ...(target.meta ?? {}), cad_layer: targetLayer } }, "Layer");
      });
      pushCadCommandFeedback("LAYER", "applied", `LAYER applied ${targetLayer} to selected draft object(s).`);
    } else {
      pushCadCommandFeedback("LAYER", "info", `Current draft layer set to ${targetLayer}. Select objects to apply it.`);
    }
    return true;
  }
  if (commandKey === "SNAP") {
    const arg = (args[0] || "").toLowerCase();
    const next = arg === "off" ? false : arg === "on" ? true : !cadSnapEnabled;
    setCadSnapEnabled(next);
    pushCadCommandFeedback("SNAP", "info", `SNAP ${next ? "on" : "off"}.`);
    return true;
  }
  if (commandKey === "ORTHO") {
    const arg = (args[0] || "").toLowerCase();
    const next = arg === "off" ? false : arg === "on" ? true : !cadOrthoEnabled;
    setCadOrthoEnabled(next);
    pushCadCommandFeedback("ORTHO", "info", `ORTHO ${next ? "on" : "off"}.`);
    return true;
  }
  return false;
}
