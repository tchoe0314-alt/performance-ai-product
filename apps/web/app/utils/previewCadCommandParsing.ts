export type CadCommandPoint = [number, number];

const CAD_COMMAND_ALIASES: Record<string, string> = {
  L: "LINE",
  PL: "PLINE",
  REC: "RECTANGLE",
  RECT: "RECTANGLE",
  B: "BOX",
  C: "CIRCLE",
  A: "ARC",
  AR: "ARRAY",
  AL: "ALIGN",
  DALIGN: "DISTRIBUTE",
  DISTRIB: "DISTRIBUTE",
  M: "MOVE",
  RO: "ROTATE",
  SC: "SCALE",
  CO: "COPY",
  O: "OFFSET",
  TR: "TRIM",
  EX: "EXTEND",
  F: "FILLET",
  J: "JOIN",
  BR: "SPLIT",
  BREAK: "SPLIT",
  CL: "CLOSE",
  H: "HATCH",
  BH: "HATCH",
  REV: "REVERSE",
  MI: "MIRROR",
  E: "ERASE",
  D: "DIM",
  DI: "DIST",
  T: "TEXT",
  LA: "LAYER",
  SEL: "SELECT",
};

const KNOWN_CAD_COMMANDS = new Set([
  "LINE",
  "PLINE",
  "RECTANGLE",
  "RECT",
  "BOX",
  "CIRCLE",
  "ARC",
  "ARRAY",
  "ALIGN",
  "DISTRIBUTE",
  "DIST",
  "MEASURE",
  "MOVE",
  "ROTATE",
  "SCALE",
  "COPY",
  "DELETE",
  "ERASE",
  "OFFSET",
  "TRIM",
  "EXTEND",
  "FILLET",
  "JOIN",
  "SPLIT",
  "BREAK",
  "CLOSE",
  "OPEN",
  "REVERSE",
  "HATCH",
  "MIRROR",
  "FLIP",
  "DIM",
  "TEXT",
  "LAYER",
  "SELECT",
  "SEL",
  "SNAP",
  "ORTHO",
  "FINISH",
  "DONE",
  "CANCEL",
  "ESC",
]);

const roundCadCoordinate = (value: number) => Math.round(value * 1000) / 1000;

export function normalizeCadCommandKey(command: string) {
  const normalized = command.toUpperCase();
  return CAD_COMMAND_ALIASES[normalized] ?? normalized;
}

export function isKnownCadCommand(command: string) {
  return KNOWN_CAD_COMMANDS.has(command);
}

export function isSelectedCadCommandArg(arg: string) {
  return arg.toLowerCase() === "selected";
}

export function parseCadNumber(value: string, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function parseCadPointToken(token: string): CadCommandPoint | null {
  const match = token.trim().match(/^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
  if (!match) return null;
  const x = Number(match[1]);
  const y = Number(match[2]);
  return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
}

export function parseCadRelativePointToken(
  token: string,
  basePoint: CadCommandPoint | null,
): CadCommandPoint | null {
  if (!basePoint) return null;
  const trimmed = token.trim();
  const relativeMatch = trimmed.match(/^@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
  if (relativeMatch) {
    const dx = Number(relativeMatch[1]);
    const dy = Number(relativeMatch[2]);
    return Number.isFinite(dx) && Number.isFinite(dy)
      ? [roundCadCoordinate(basePoint[0] + dx), roundCadCoordinate(basePoint[1] + dy)]
      : null;
  }
  const polarMatch = trimmed.match(/^@(-?\d+(?:\.\d+)?)<(-?\d+(?:\.\d+)?)$/);
  if (polarMatch) {
    const distance = Number(polarMatch[1]);
    const angleDeg = Number(polarMatch[2]);
    if (!Number.isFinite(distance) || !Number.isFinite(angleDeg)) return null;
    const radians = (angleDeg * Math.PI) / 180;
    return [
      roundCadCoordinate(basePoint[0] + Math.cos(radians) * distance),
      roundCadCoordinate(basePoint[1] + Math.sin(radians) * distance),
    ];
  }
  return null;
}

export function parseCadVectorToken(token: string): CadCommandPoint | null {
  return parseCadPointToken(token) ?? parseCadRelativePointToken(token, [0, 0]);
}

export function parseCadPointTokens(tokens: string[]) {
  return tokens
    .map((token) => parseCadPointToken(token))
    .filter((point): point is CadCommandPoint => Boolean(point));
}

export function getCadCommandPointArgs(args: string[]) {
  return parseCadPointTokens(args.filter((arg) => !isSelectedCadCommandArg(arg)));
}

export function getCadCommandFirstValue(args: string[], fallback: string) {
  return args.find((arg) => !isSelectedCadCommandArg(arg)) ?? fallback;
}

export function hasSelectedCadCommandArg(args: string[]) {
  return args.some(isSelectedCadCommandArg);
}

export function buildReviewRequiredCommandMeta(command: string, extra: Record<string, unknown> = {}) {
  return {
    cad_command: command.toUpperCase(),
    cad_command_source: "typed_command_line",
    source: "manual_drawn",
    engineering_status: "draft_review_required",
    review_status: "engineer_review_required",
    handoff_status: "draft_review_required",
    construction_release_allowed: false,
    ...extra,
  };
}

export function buildDraftGeometryCreatedMessage(command: string) {
  return `${command.toUpperCase()} created editable draft geometry for review. Rerun affected systems before relying on it.`;
}
