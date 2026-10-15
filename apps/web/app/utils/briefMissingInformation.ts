export type BriefMissingInformation = { why: string; blocks: string; provisional: string; assumption: string; verification: string };
const rules: Record<string, [string, string, string]> = {
  "gross-acreage": ["Defines parcel capacity.", "Area-based quantities and coverage.", "Surveyor confirms the boundary and units."],
  "usable-acreage": ["Separates usable land from exclusions.", "Usable-area capacity conclusions.", "Civil engineer confirms easements and excluded land."],
  "building-area": ["Defines the requested program.", "Program-fit and target-area comparisons.", "Project owner confirms the program."],
  storeys: ["Relates footprint to total floor area.", "Total-floor-area and height conclusions.", "Architect confirms storeys and floor area."],
  "building-use": ["Sets the intended land use.", "Use-specific parking and zoning conclusions.", "Owner and local planning professional confirm the use."],
  "parking-ratio": ["Relates the program to parking demand.", "Code-required parking conclusions.", "Local planning professional confirms the applicable ratio."],
  "required-parking": ["Defines the parking target.", "Parking-target satisfaction.", "Owner or local planning professional confirms the count."],
  "drive-aisles": ["Defines vehicle circulation space.", "Circulation and aisle-clearance approval.", "Civil engineer confirms aisle dimensions."],
  access: ["Defines permitted access locations.", "Access feasibility and approval.", "Civil engineer and road authority confirm access."],
  egress: ["Defines emergency access requirements.", "Fire/egress compliance conclusions.", "Fire authority and qualified designer confirm requirements."],
  setbacks: ["Defines the allowed placement envelope.", "Setback-compliance conclusions.", "Local planning professional confirms applicable setbacks."],
  height: ["Limits the vertical program.", "Height-compliance conclusions.", "Architect and local planning professional confirm limits."],
  "lot-coverage": ["Limits building coverage.", "Lot-coverage compliance conclusions.", "Local planning professional confirms the coverage limit."],
  impervious: ["Limits hard-surface coverage.", "Impervious-area compliance conclusions.", "Civil engineer confirms the applicable coverage limit."],
  "open-space": ["Reserves required open space.", "Open-space compliance conclusions.", "Local planning professional confirms the requirement."],
  stormwater: ["Defines drainage design assumptions.", "Stormwater sizing and engineering approval.", "Civil engineer confirms rainfall, terrain, soils and discharge conditions."],
  protected: ["Identifies geometry that must be preserved.", "Claims that all protected features are respected.", "Surveyor and civil engineer confirm protected features."],
  priorities: ["Defines how feasible concepts should be ranked.", "Claims that an alternative matches owner priorities.", "Project owner confirms priorities."],
};
export function briefMissingInformation(id: string): BriefMissingInformation {
  const [why, blocks, verification] = rules[id] ?? ["Defines a design requirement.", "Conclusions that rely on this requirement.", "A qualified professional confirms the requirement."];
  return { why, blocks, verification, provisional: "Manual concept drawing can continue; affected conclusions stay unverified.", assumption: "None applied automatically. Enter an explicit assumption and mark it Assumed." };
}
