import { useEffect, useState } from "react";
import type { BuildingPlacement } from "../types";

type Props = {
  object: BuildingPlacement;
  disabled?: boolean;
  onUpdate: (object: BuildingPlacement, updates: Partial<BuildingPlacement>) => void;
};

type Basis = Record<string, unknown>;

const numberValue = (value: unknown) => Number.isFinite(Number(value)) ? Number(value) : "";
const textValue = (value: unknown) => typeof value === "string" ? value : "";
const pointValue = (value: unknown, index: number) => Array.isArray(value) && Number.isFinite(Number(value[index])) ? Number(value[index]) : "";

function parsePolygon(value: string): { points?: [number, number][]; error?: string } {
  if (!value.trim()) return {};
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed) || parsed.length < 3 || parsed.some((point) =>
      !Array.isArray(point) || point.length < 2 || !Number.isFinite(Number(point[0])) || !Number.isFinite(Number(point[1]))
    )) return { error: "Use at least three [x, y] coordinate pairs." };
    return { points: parsed.map((point) => [Number(point[0]), Number(point[1])]) };
  } catch {
    return { error: "Use JSON coordinates such as [[0,0],[20,0],[20,20],[0,20]]." };
  }
}

function NumericField({ label, value, min = 0, step = "any", disabled, onChange, testId }: {
  label: string; value: unknown; min?: number; step?: number | "any"; disabled?: boolean;
  onChange: (value: number | null) => void; testId?: string;
}) {
  return <label className="text-[11px] font-semibold text-slate-600">{label}
    <input data-testid={testId} type="number" min={min} step={step} value={numberValue(value)} disabled={disabled}
      onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 disabled:bg-slate-100" />
  </label>;
}

function SourceField({ label, value, disabled, onChange, testId }: {
  label: string; value: unknown; disabled?: boolean; onChange: (value: string) => void; testId?: string;
}) {
  return <label className="text-[11px] font-semibold text-slate-600">{label}
    <input key={textValue(value)} data-testid={testId} type="text" defaultValue={textValue(value)} disabled={disabled}
      placeholder="Document, survey, study, or adopted criteria ID"
      onBlur={(event) => onChange(event.target.value.trim())}
      className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 disabled:bg-slate-100" />
  </label>;
}

export function SitePlanningEvidenceEditor({ object, disabled, onUpdate }: Props) {
  const [meta, setMeta] = useState<Record<string, unknown>>(() => object.meta ?? {});
  useEffect(() => setMeta(object.meta ?? {}), [object.id]);
  const updateBasis = (key: string, current: Basis, updates: Basis) => setMeta((value) => ({
    ...value, [key]: { ...current, ...updates },
  }));
  const apply = (testId: string) => <button type="button" data-testid={testId} disabled={disabled}
    onClick={() => onUpdate(object, { meta })}
    className="mt-3 w-full rounded-lg bg-sky-800 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">
    Apply evidence to project
  </button>;

  if (object.type === "parking") {
    const basis = (meta.parking_design_basis as Basis | undefined) ?? {};
    const missing = [
      !Number(basis.stall_width_ft) && "stall width",
      !Number(basis.stall_depth_ft) && "stall depth",
      !Number(basis.aisle_width_ft) && "drive aisle width",
      !textValue(basis.source).trim() && "criteria/source",
    ].filter(Boolean) as string[];
    return <section className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3" data-testid="parking-design-evidence-editor">
      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-800">Parking design evidence</p>
      <p className="mt-1 text-xs text-sky-900">Describe the supplied concept geometry. This does not establish zoning or accessibility compliance.</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <NumericField label="Stall width (ft)" value={basis.stall_width_ft} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { stall_width_ft: v })} />
        <NumericField label="Stall depth (ft)" value={basis.stall_depth_ft} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { stall_depth_ft: v })} />
        <NumericField label="Drive aisle (ft)" value={basis.aisle_width_ft} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { aisle_width_ft: v })} />
        <NumericField label="Accessible stalls" value={basis.accessible_stall_count} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { accessible_stall_count: v })} />
        <NumericField label="Accessible stall width" value={basis.accessible_stall_width_ft} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { accessible_stall_width_ft: v })} />
        <NumericField label="Access aisle width" value={basis.access_aisle_width_ft} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { access_aisle_width_ft: v })} />
      </div>
      <div className="mt-2"><SourceField testId="parking-evidence-source" label="Criteria/source record" value={basis.source} disabled={disabled} onChange={(v) => updateBasis("parking_design_basis", basis, { source: v })} /></div>
      <p className={`mt-2 text-xs font-semibold ${missing.length ? "text-amber-800" : "text-emerald-800"}`} data-testid="parking-evidence-status">{missing.length ? `Needs: ${missing.join(", ")}.` : "Required concept evidence entered; legal compliance remains unverified."}</p>
      {apply("apply-parking-evidence")}
    </section>;
  }

  if (object.type === "sidewalk") {
    const basis = (meta.accessible_route_design_basis as Basis | undefined) ?? {};
    const entrance = basis.building_entrance_xy;
    const missing = [
      !textValue(basis.route_geometry_source).trim() && "route source",
      !textValue(basis.criteria_source).trim() && "criteria source",
      !Number(basis.route_width_ft) && "route width",
      !Number(basis.maximum_running_slope_pct) && "running-slope limit",
      !Number(basis.maximum_cross_slope_pct) && "cross-slope limit",
      (!Array.isArray(entrance) || entrance.length < 2) && "entrance coordinate",
      Number(basis.vehicle_crossing_count) > 0 && !textValue(basis.vehicle_crossing_controls_source).trim() && "crossing treatment source",
    ].filter(Boolean) as string[];
    return <section className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3" data-testid="accessible-route-evidence-editor">
      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-800">Accessible route evidence</p>
      <p className="mt-1 text-xs text-sky-900">The selected polyline is the proposed route. Enter measured geometry and the criteria used for review.</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <NumericField label="Route width (ft)" value={basis.route_width_ft} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { route_width_ft: v })} />
        <NumericField label="Minimum width (ft)" value={basis.minimum_route_width_ft} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { minimum_route_width_ft: v })} />
        <NumericField label="Measured running slope (%)" value={basis.measured_running_slope_pct} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { measured_running_slope_pct: v })} />
        <NumericField label="Maximum running slope (%)" value={basis.maximum_running_slope_pct} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { maximum_running_slope_pct: v })} />
        <NumericField label="Measured cross slope (%)" value={basis.measured_cross_slope_pct} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { measured_cross_slope_pct: v })} />
        <NumericField label="Maximum cross slope (%)" value={basis.maximum_cross_slope_pct} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { maximum_cross_slope_pct: v })} />
        <NumericField label="Entrance X" value={pointValue(entrance, 0)} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { building_entrance_xy: [v, pointValue(entrance, 1)] })} />
        <NumericField label="Entrance Y" value={pointValue(entrance, 1)} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { building_entrance_xy: [pointValue(entrance, 0), v] })} />
        <NumericField label="Vehicle crossings" value={basis.vehicle_crossing_count} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { vehicle_crossing_count: v })} />
      </div>
      <div className="mt-2 space-y-2">
        <SourceField label="Route geometry source" value={basis.route_geometry_source} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { route_geometry_source: v })} />
        <SourceField label="Criteria source" value={basis.criteria_source} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { criteria_source: v })} />
        <SourceField label="Crossing treatment source" value={basis.vehicle_crossing_controls_source} disabled={disabled} onChange={(v) => updateBasis("accessible_route_design_basis", basis, { vehicle_crossing_controls_source: v })} />
      </div>
      <p className={`mt-2 text-xs font-semibold ${missing.length ? "text-amber-800" : "text-emerald-800"}`} data-testid="accessible-route-evidence-status">{missing.length ? `Needs: ${missing.join(", ")}.` : "Required route evidence entered; accessibility approval remains unverified."}</p>
      {apply("apply-accessible-route-evidence")}
    </section>;
  }

  if (!["driveway", "road"].includes(object.type ?? "")) return null;
  const basis = (meta.circulation_design_basis as Basis | undefined) ?? {};
  const vehicle = (basis.design_vehicle as Basis | undefined) ?? {};
  const swept = (basis.swept_path_evidence as Basis | undefined) ?? {};
  const fire = (basis.fire_access_design_basis as Basis | undefined) ?? {};
  const entrance = basis.site_entrance_xy;
  const envelopeText = Array.isArray(swept.swept_envelope_polygon) ? JSON.stringify(swept.swept_envelope_polygon) : "";
  const areaText = Array.isArray(swept.maneuvering_area_polygon) ? JSON.stringify(swept.maneuvering_area_polygon) : "";
  const missing = [
    !textValue(basis.route_geometry_source).trim() && "route source",
    !textValue(basis.criteria_source).trim() && "circulation criteria",
    !Number(basis.route_width_ft) && "route width",
    !Array.isArray(entrance) && "site entrance coordinate",
    !textValue(vehicle.source).trim() && "design vehicle source",
    !Number(vehicle.overall_length_ft) && "vehicle length",
    !Number(vehicle.overall_width_ft) && "vehicle width",
    !Number(vehicle.wheelbase_ft) && "wheelbase",
    !textValue(swept.source).trim() && "swept-path source",
    !Array.isArray(swept.swept_envelope_polygon) && "swept envelope polygon",
    !Array.isArray(swept.maneuvering_area_polygon) && "maneuvering area polygon",
    !textValue(fire.criteria_source).trim() && "fire criteria source",
  ].filter(Boolean) as string[];
  const updateVehicle = (updates: Basis) => updateBasis("circulation_design_basis", basis, { design_vehicle: { ...vehicle, ...updates } });
  const updateSwept = (updates: Basis) => updateBasis("circulation_design_basis", basis, { swept_path_evidence: { ...swept, ...updates } });
  const updateFire = (updates: Basis) => updateBasis("circulation_design_basis", basis, { fire_access_design_basis: { ...fire, ...updates } });
  return <section className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3" data-testid="circulation-evidence-editor">
    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-800">Circulation, turning & fire geometry</p>
    <p className="mt-1 text-xs text-sky-900">The selected line is the access route. Supplied envelopes and criteria are review evidence, not generated swept-path or fire-code approval.</p>
    <div className="mt-3 grid grid-cols-2 gap-2">
      <NumericField label="Route width (ft)" value={basis.route_width_ft} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { route_width_ft: v })} />
      <NumericField label="Minimum width (ft)" value={basis.minimum_route_width_ft} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { minimum_route_width_ft: v })} />
      <NumericField label="Entrance X" value={pointValue(entrance, 0)} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { site_entrance_xy: [v, pointValue(entrance, 1)] })} />
      <NumericField label="Entrance Y" value={pointValue(entrance, 1)} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { site_entrance_xy: [pointValue(entrance, 0), v] })} />
    </div>
    <div className="mt-2 space-y-2"><SourceField label="Route geometry source" value={basis.route_geometry_source} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { route_geometry_source: v })} /><SourceField label="Circulation criteria source" value={basis.criteria_source} disabled={disabled} onChange={(v) => updateBasis("circulation_design_basis", basis, { criteria_source: v })} /></div>
    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">Design vehicle</p>
    <div className="mt-2 grid grid-cols-2 gap-2">
      <NumericField label="Overall length (ft)" value={vehicle.overall_length_ft} disabled={disabled} onChange={(v) => updateVehicle({ overall_length_ft: v })} />
      <NumericField label="Overall width (ft)" value={vehicle.overall_width_ft} disabled={disabled} onChange={(v) => updateVehicle({ overall_width_ft: v })} />
      <NumericField label="Wheelbase (ft)" value={vehicle.wheelbase_ft} disabled={disabled} onChange={(v) => updateVehicle({ wheelbase_ft: v })} />
    </div>
    <div className="mt-2 space-y-2"><SourceField label="Vehicle name" value={vehicle.name} disabled={disabled} onChange={(v) => updateVehicle({ name: v })} /><SourceField label="Vehicle record/source" value={vehicle.source} disabled={disabled} onChange={(v) => updateVehicle({ source: v })} /></div>
    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">Supplied swept-envelope study</p>
    <div className="mt-2 space-y-2">
      <SourceField label="Study/source" value={swept.source} disabled={disabled} onChange={(v) => updateSwept({ source: v })} />
      {[{ label: "Maneuvering area polygon", value: areaText, key: "maneuvering_area_polygon" }, { label: "Swept envelope polygon", value: envelopeText, key: "swept_envelope_polygon" }].map((field) => <label key={field.key} className="block text-[11px] font-semibold text-slate-600">{field.label}
        <textarea defaultValue={field.value} disabled={disabled} rows={2} onBlur={(event) => { const parsed = parsePolygon(event.target.value); if (parsed.points) updateSwept({ [field.key]: parsed.points }); event.target.setCustomValidity(parsed.error ?? ""); event.target.reportValidity(); }} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 font-mono text-[10px] disabled:bg-slate-100" />
      </label>)}
    </div>
    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">Fire-access geometry basis</p>
    <div className="mt-2 grid grid-cols-2 gap-2">
      <NumericField label="Clear width (ft)" value={fire.clear_width_ft} disabled={disabled} onChange={(v) => updateFire({ clear_width_ft: v })} />
      <NumericField label="Minimum width (ft)" value={fire.minimum_clear_width_ft} disabled={disabled} onChange={(v) => updateFire({ minimum_clear_width_ft: v })} />
      <NumericField label="Vertical clearance (ft)" value={fire.vertical_clearance_ft} disabled={disabled} onChange={(v) => updateFire({ vertical_clearance_ft: v })} />
      <NumericField label="Minimum clearance (ft)" value={fire.minimum_vertical_clearance_ft} disabled={disabled} onChange={(v) => updateFire({ minimum_vertical_clearance_ft: v })} />
      <NumericField label="Measured max grade (%)" value={fire.measured_max_grade_pct} disabled={disabled} onChange={(v) => updateFire({ measured_max_grade_pct: v })} />
      <NumericField label="Maximum grade (%)" value={fire.maximum_grade_pct} disabled={disabled} onChange={(v) => updateFire({ maximum_grade_pct: v })} />
      <NumericField label="Surface capacity (tons)" value={fire.surface_capacity_tons} disabled={disabled} onChange={(v) => updateFire({ surface_capacity_tons: v })} />
      <NumericField label="Minimum capacity (tons)" value={fire.minimum_surface_capacity_tons} disabled={disabled} onChange={(v) => updateFire({ minimum_surface_capacity_tons: v })} />
      <NumericField label="Dead end length (ft)" value={fire.dead_end_length_ft} disabled={disabled} onChange={(v) => updateFire({ dead_end_length_ft: v })} />
      <NumericField label="Max without turnaround (ft)" value={fire.maximum_dead_end_without_turnaround_ft} disabled={disabled} onChange={(v) => updateFire({ maximum_dead_end_without_turnaround_ft: v })} />
    </div>
    <div className="mt-2 space-y-2"><SourceField label="Fire criteria source" value={fire.criteria_source} disabled={disabled} onChange={(v) => updateFire({ criteria_source: v })} /><SourceField label="Pavement capacity source" value={fire.surface_capacity_source} disabled={disabled} onChange={(v) => updateFire({ surface_capacity_source: v })} /><SourceField label="Gate/access-control source" value={fire.access_control_source} disabled={disabled} onChange={(v) => updateFire({ access_control_source: v })} /></div>
    <p className={`mt-2 text-xs font-semibold ${missing.length ? "text-amber-800" : "text-emerald-800"}`} data-testid="circulation-evidence-status">{missing.length ? `Needs: ${missing.join(", ")}.` : "Geometry evidence entered; AHJ, operational and professional approval remain required."}</p>
    {apply("apply-circulation-evidence")}
  </section>;
}
