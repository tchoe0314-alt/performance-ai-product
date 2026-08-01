import type { SiteObjectType } from "../types";

export type DashboardObjectCommandIntent =
  | { kind: "grading_context"; mode: "grading" | "drainage" | "both" }
  | { kind: "parking_count"; stalls: number }
  | { kind: "office_area"; areaSf: number }
  | { kind: "building_dims"; width: number; depth: number }
  | { kind: "object"; type: SiteObjectType; width: number | null; depth: number | null }
  | { kind: "basin"; width: number; depth: number }
  | { kind: "entrance" }
  | { kind: "plot_dims"; width: number; height: number }
  | { kind: "plot_acres"; acres: number };

const CHAT_OBJECT_TYPE_MAP: Record<string, SiteObjectType> = {
  "retail building": "retail_building",
  "multifamily building": "multifamily_building",
  "industrial building": "industrial_building",
  "office building": "office_building",
  pad: "pad",
  pool: "pool",
  "amenity area": "amenity",
  "open space": "open_space",
  entrance: "entrance",
  "access point": "entrance",
  driveway: "driveway",
  road: "road",
  "drive aisle": "road",
  "parking field": "parking",
  parking: "parking",
  sidewalk: "sidewalk",
  path: "sidewalk",
  basin: "basin",
  "detention pond": "basin",
  outfall: "outfall",
  inlet: "inlet",
  manhole: "manhole",
  hydrant: "hydrant",
  "setback zone": "setback_zone",
  "no-build zone": "no_build_zone",
  "utility corridor": "utility_corridor",
  "lot block": "lot_block",
  "subdivision block": "lot_block",
  bridge: "bridge",
};

export function parseDashboardObjectCommandIntent(message: string): DashboardObjectCommandIntent | null {
  const lower = message.toLowerCase();
  const parkingCountCommandMatch = lower.match(/\badd\s+(\d{1,5})\s+(?:parking\s+)?(?:spaces|stalls)\b/);
  const officeAreaCommandMatch = lower.match(
    /\b(?:add|create|place|make|put|include)\b[^\d]{0,48}(\d{1,3}(?:,\d{3})+|\d{3,8})\s*(?:sf|sq\s*ft|sqft|square\s*feet)\s+(?:(?:office\s+)?building|office\s+project)\b/,
  );
  const addBuildingMatch = lower.match(
    /(add|create|place)\s+(a\s+)?building[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
  );
  const addObjectMatch = lower.match(
    /(add|create|place)\s+(a\s+)?(retail building|multifamily building|industrial building|office building|pad|pool|amenity area|open space|entrance|access point|driveway|road|drive aisle|parking field|parking|sidewalk|path|basin|detention pond|outfall|inlet|manhole|hydrant|setback zone|no-build zone|utility corridor|lot block|subdivision block|bridge)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
  );
  const plotDimsMatch = lower.match(
    /(add|create|set)\s+(a\s+)?(lot|plot|site)[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
  );
  const plotAcreMatch = lower.match(/(add|create|set)\s+(a\s+)?(\d+(\.\d+)?)\s*acre/);

  if (
    /\b(add|create|place|show|draw|make)\b/.test(lower) &&
    /\b(grading|grade|fall line|slope direction|drainage area|drainage context|flow path)\b/.test(lower)
  ) {
    const wantsGrading = /\b(grading|grade|fall line|slope direction)\b/.test(lower);
    const wantsDrainage = /\b(drainage|flow path|drainage area)\b/.test(lower);
    return { kind: "grading_context", mode: wantsGrading && wantsDrainage ? "both" : wantsGrading ? "grading" : "drainage" };
  }

  if (parkingCountCommandMatch) {
    const stalls = Number(parkingCountCommandMatch[1]);
    return Number.isFinite(stalls) && stalls > 0 ? { kind: "parking_count", stalls } : null;
  }
  if (officeAreaCommandMatch) {
    const areaSf = Number(officeAreaCommandMatch[1].replace(/,/g, ""));
    return Number.isFinite(areaSf) && areaSf > 0 ? { kind: "office_area", areaSf } : null;
  }
  if (addBuildingMatch) {
    const width = Number(addBuildingMatch[3]);
    const depth = Number(addBuildingMatch[7]);
    return Number.isFinite(width) && Number.isFinite(depth) ? { kind: "building_dims", width, depth } : null;
  }
  if (addObjectMatch) {
    const type = CHAT_OBJECT_TYPE_MAP[addObjectMatch[3]];
    if (!type) return null;
    const width = addObjectMatch[4] ? Number(addObjectMatch[4]) : null;
    const depth = addObjectMatch[8] ? Number(addObjectMatch[8]) : null;
    return {
      kind: "object",
      type,
      width: width !== null && Number.isFinite(width) ? width : null,
      depth: depth !== null && Number.isFinite(depth) ? depth : null,
    };
  }
  const addBasinMatch = lower.match(
    /(add|create|place)\s+(a\s+)?(basin|detention)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
  );
  if (addBasinMatch) {
    const width = addBasinMatch[4] ? Number(addBasinMatch[4]) : 80;
    const depth = addBasinMatch[8] ? Number(addBasinMatch[8]) : 60;
    return { kind: "basin", width: Number.isFinite(width) ? width : 80, depth: Number.isFinite(depth) ? depth : 60 };
  }
  if (lower.match(/(add|create|place)\s+(an?\s+)?entrance/)) {
    return { kind: "entrance" };
  }
  if (plotDimsMatch) {
    const width = Number(plotDimsMatch[4]);
    const height = Number(plotDimsMatch[8]);
    return Number.isFinite(width) && Number.isFinite(height) ? { kind: "plot_dims", width, height } : null;
  }
  if (plotAcreMatch) {
    const acres = Number(plotAcreMatch[3]);
    return Number.isFinite(acres) ? { kind: "plot_acres", acres } : null;
  }
  return null;
}

export function parseDashboardDirectSiteSetupCommand(
  message: string,
  currentAddress: string,
): { address: string; width: number; height: number } | null {
  const compact = message.trim().replace(/\s+/g, " ");
  if (!compact) return null;
  const sizeMatch = compact.match(
    /(\d{2,5}(?:,\d{3})?(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(?:by|x|×)\s*(\d{2,5}(?:,\d{3})?(?:\.\d+)?)\s*(?:ft|feet|foot|')?/i,
  );
  if (!sizeMatch || sizeMatch.index === undefined) return null;
  const width = Number(sizeMatch[1].replace(/,/g, ""));
  const height = Number(sizeMatch[2].replace(/,/g, ""));
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const beforeSize = compact.slice(0, sizeMatch.index).trim();
  const afterSize = compact.slice(sizeMatch.index + sizeMatch[0].length).trim();
  const looksLikeStreetAddress = (value: string) =>
    value.length >= 6 &&
    /\d/.test(value) &&
    /\b(?:st|street|ave|avenue|rd|road|dr|drive|blvd|boulevard|ln|lane|ct|court|way|pkwy|parkway|hwy|highway|ne|nw|se|sw|tx|ga|co|az|nc|nebraska|texas|georgia|colorado|arizona|carolina)\b/i.test(
      value,
    );
  const cleanAddressCandidate = (value: string) =>
    value
      .replace(/^.*?\baddress\b\s*(?:is|as|to be|to|=|:)?\s*/i, "")
      .replace(/^\b(?:with|using|at|centered\s+(?:at|on)|centred\s+(?:at|on))\b\s*/i, "")
      .replace(/^(?:is|it'?s|it is|gonna|going to be|will be|should be)\b\s*/i, "")
      .replace(/\b(?:as|for|with)?\s*(?:the\s+)?(?:center|centre)(?:\s+point)?\b.*$/i, "")
      .replace(/\b(?:and\s+)?(?:it'?s|it is|its|site|lot|gonna|going to be|will be|should be)\s*$/i, "")
      .replace(/\b(?:and|with|that|it'?s|it is|site|lot|gonna|going to be|will be|should be)\s*$/i, "")
      .replace(/[.,;:]+$/g, "")
      .trim();
  const explicitAddressMatch =
    compact.match(
      /\baddress\b\s*(?:is|as|to be|to|=|:)?\s+(.+?)(?=\s+(?:and\s+)?(?:it'?s|it is|its|site|lot|gonna|going to be|will be|should be|with\s+(?:a\s+)?\d|make\s+it|set\s+it|center(?:ed)?|as\s+the\s+center)|$)/i,
    ) ||
    compact.match(
      /\b(?:at|use|around|center(?:ed)?\s+(?:at|on))\s+(.+?)(?=\s+(?:and\s+)?(?:make|set|it'?s|it is|its|site|lot|with\s+(?:a\s+)?\d|center(?:ed)?|as\s+the\s+center)|$)/i,
    );
  const beforeStreetCandidate = beforeSize
    .replace(/\b(?:i want|make|set|create|start|the|site|lot|address|with|use|at|around|center point|centered|center|as|to be)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
  const afterStreetCandidate = afterSize
    .replace(/\b(?:with|as|the|center|centre|point|address|is|to be|it'?s|it is|gonna|going|will|should|site|lot)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
  const afterAddressLead = explicitAddressMatch ? cleanAddressCandidate(explicitAddressMatch[1]) : cleanAddressCandidate(beforeSize);
  const addressAfterSize = cleanAddressCandidate(afterSize);
  const addressCandidates = [afterAddressLead, addressAfterSize, beforeStreetCandidate, afterStreetCandidate, currentAddress]
    .map((candidate) => candidate.replace(/[.,;:]+$/g, "").trim())
    .filter(Boolean);
  let address =
    addressCandidates.find(looksLikeStreetAddress) ||
    addressCandidates.find((candidate) => candidate.length >= 6 && /\d/.test(candidate)) ||
    addressCandidates[0] ||
    "";
  if (/^(?:the\s+)?address$/i.test(address) && currentAddress) {
    address = currentAddress;
  }
  if (!address && currentAddress && /\baddress\b/i.test(afterSize)) {
    address = currentAddress;
  }
  address = cleanAddressCandidate(address).replace(/\b(?:and\s+)?(?:it'?s|it is|its)\s*$/i, "").trim();
  if (address.length < 6 || !/\d/.test(address)) return null;
  return { address, width, height };
}
