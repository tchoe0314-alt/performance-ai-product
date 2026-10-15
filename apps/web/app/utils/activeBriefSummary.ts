import type { BuildingPlacement, ProjectInput } from "../types";
import { canonicalControlState } from "./canonicalEditCommands";
import { geometryIssues } from "./siteObjectDefinition";
import { validateAdditionalBriefRequirements } from "./briefRequirements";

export type BriefSummaryRow = {
  id: string;
  label: string;
  value: string;
  basis: string;
  known: boolean;
  valueKey?: string;
};

const number = (value: unknown, allowZero = false): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || (!allowZero && value === 0)) return null;
  return value;
};
const format = (value: number) => value.toLocaleString("en-US", { maximumFractionDigits: 2 });

/** Read-only projection of live inputs. Never fill blanks from design outputs,
 * bounding boxes, local-code guesses or previous calculation results. */
export function buildActiveBriefSummary(input: ProjectInput, savedInput?: ProjectInput): BriefSummaryRow[] {
  const fields = input.manual_fields ?? {};
  const sitePlan = fields.site_plan ?? {};
  const controls = input.meta?.edit_controls_v1 as Record<string, unknown> | undefined;
  const objects = (fields.site_objects ?? []).map(item => ({
    ...item, label: item.label ?? item.name ?? item.id ?? "Object",
    geometryType: item.geometry_type,
  } as BuildingPlacement));
  const sites = objects.filter(item => item.type === "site" && item.placed !== false);
  const unit = fields.units === "ft" ? "ft" : fields.units === "m" ? "m" : null;
  let area: number | null = null;
  let areaBasis = "Calculated from site dimensions; not survey verified";
  if (unit && sites.length === 1 && geometryIssues(sites[0]).length === 0) {
    const site = sites[0];
    if (site.geometryType === "polygon") {
      const points = site.geometry!;
      area = Math.abs(points.reduce((sum, p, i) => {
        const q = points[(i + 1) % points.length];
        return sum + p[0] * q[1] - q[0] * p[1];
      }, 0)) / 2;
      areaBasis = "Calculated from site outline; not survey verified";
    } else if (!site.geometryType || site.geometryType === "rect") area = site.w * site.d;
  } else if (unit && sites.length === 0) {
    const width = number(fields.lot?.w), depth = number(fields.lot?.h);
    if (width !== null && depth !== null) area = width * depth;
  }
  const acres = area !== null && Number.isFinite(area) ? area / (unit === "m" ? 4046.8564224 : 43560) : null;
  const protectedObjects = objects.filter(item => item.placed !== false && (
    item.locked || ["fixed", "existing", "reference"].includes(canonicalControlState(item))
  ));
  const unknown = (id: string, label: string): BriefSummaryRow => ({ id, label, value: "Not set", basis: "No explicit requirement", known: false });
  const value = (id: string, label: string, text: string | null, basis: string): BriefSummaryRow =>
    text === null ? unknown(id, label) : { id, label, value: text, basis, known: true };
  // The live payload builder recreates controls but does not carry every legacy
  // program field. Preserve explicit saved program targets, never saved geometry
  // or prior quantities. An explicit live value (including invalid/blank) wins.
  const savedPlan = savedInput?.manual_fields?.site_plan;
  const areaTarget = number(Object.hasOwn(sitePlan, "building_program_sf") ? sitePlan.building_program_sf : savedPlan?.building_program_sf);
  const buildingUse = Object.hasOwn(sitePlan, "building_type") ? sitePlan.building_type : savedPlan?.building_type;
  // A placed parking field's stall count is not a parking requirement.
  const rawParking = controls && Object.hasOwn(controls, "parkingCount") ? controls.parkingCount : sitePlan.parking_count;
  const parking = typeof rawParking === "string" && rawParking.trim() !== "" ? number(Number(rawParking), true) : number(rawParking, true);
  const setback = number(fields.setback, true);
  const rows: BriefSummaryRow[] = [
    value("gross-acreage", "Gross acreage", acres === null ? null : `${format(acres)} ac`, areaBasis),
    unknown("usable-acreage", "Usable acreage"),
    value("building-area", "Building-area target", areaTarget === null ? null : `${format(areaTarget)} sf`, "Stored program target; unverified"),
    unknown("storeys", "Storey target"),
    value("building-use", "Building use", typeof buildingUse === "string" && buildingUse.trim() ? buildingUse.replaceAll("_", " ") : null, "Stored program use; unverified"),
    unknown("parking-ratio", "Parking ratio"),
    value("required-parking", "Required parking", parking !== null && Number.isInteger(parking) ? `${format(parking)} spaces` : null, controls ? "Entered parking target; unverified" : "Stored parking count; requirement unconfirmed"),
    unknown("drive-aisles", "Drive-aisle dimensions"),
    unknown("access", "Access requirements"),
    unknown("egress", "Egress requirements"),
    value("setbacks", "Setbacks", setback === null || unit === null ? null : `${format(setback)} ${unit}`, "Entered setback; unverified"),
    unknown("height", "Height limits"),
    unknown("lot-coverage", "Lot coverage limit"),
    unknown("impervious", "Max. impervious coverage"),
    unknown("open-space", "Open-space target"),
    unknown("stormwater", "Stormwater assumptions"),
    value("protected", "Protected geometry", protectedObjects.length ? protectedObjects.map(item => item.label).join(", ") : "None recorded", "Current object protection; not engineering approval"),
    unknown("priorities", "Optimization priorities"),
  ];
  const rawValues: Record<string, unknown> = {
    "gross-acreage": [acres, unit, sites.map(site => [site.geometryType ?? "rect", site.w, site.d, site.geometry ?? [], site.source]), fields.lot],
    "building-area": areaTarget, "building-use": buildingUse,
    "required-parking": parking, setbacks: [setback, unit],
    protected: protectedObjects.map(item => [item.id, item.label, canonicalControlState(item), item.locked === true]),
  };
  const additional = input.meta?.site_inputs?.brief_requirements_v1 === undefined ? undefined : validateAdditionalBriefRequirements(input.meta.site_inputs.brief_requirements_v1);
  for (const row of rows) {
    const entry = additional?.fields[row.id as keyof typeof additional.fields];
    if (!entry || entry.value === null) continue;
    row.known = true;
    row.value = typeof entry.value === "number" ? `${format(entry.value)} ${entry.unit}` : entry.value;
    row.basis = "Entered requirement; not automatically checked";
    rawValues[row.id] = [entry.value, entry.unit];
  }
  return rows.map(row => ({ ...row, valueKey: JSON.stringify([row.id, row.known, rawValues[row.id] ?? null, row.basis]) }));
}
