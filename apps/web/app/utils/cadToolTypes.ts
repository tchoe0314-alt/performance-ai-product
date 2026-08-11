export type DrawMode = "select" | "pan" | "site" | "polyline" | "polygon" | "rect" | "point";

export type CadToolName =
  | "select"
  | "pan"
  | "line"
  | "polyline"
  | "area"
  | "box"
  | "point"
  | "circle"
  | "arc"
  | "text"
  | "move"
  | "copy"
  | "rotate"
  | "scale"
  | "offset"
  | "trim"
  | "extend"
  | "fillet"
  | "join"
  | "split"
  | "close"
  | "open"
  | "reverse"
  | "hatch"
  | "delete"
  | "dimension"
  | "measure"
  | "symbol"
  | "layer"
  | "properties"
  | "snap"
  | "ortho"
  | "undo"
  | "redo"
  | "command";

export type CadToolRequest = {
  id: number;
  commandText?: string;
  silent?: boolean;
  tool: CadToolName;
};

export type CadSymbolKind =
  | "hydrant"
  | "inlet"
  | "manhole"
  | "valve"
  | "tree"
  | "light"
  | "sign"
  | "utility_marker"
  | "benchmark"
  | "note_callout";

export type CadDimensionMode = "linear" | "aligned";
