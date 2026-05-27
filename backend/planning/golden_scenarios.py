from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Tuple

from .engine_contracts import GOLDEN_SCENARIOS, engine_contracts


@dataclass(frozen=True)
class GoldenScenario:
    scenario_id: str
    name: str
    purpose: str
    required_engine_ids: FrozenSet[str]
    required_canonical_signals: Tuple[str, ...]
    production_gates: Tuple[str, ...]
    blocked_without: Tuple[str, ...]
    benchmark_payload: Dict[str, Any]


def _fs(*items: str) -> FrozenSet[str]:
    return frozenset(item for item in items if item)


def _payload(name: str, *, project_type: str, lot_w: float, lot_h: float, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "project_name": name,
        "units": "ft",
        "mode": "site_plan",
        "project_type": project_type,
        "lot": {"x": 0.0, "y": 0.0, "w": lot_w, "h": lot_h},
        "site_plan": {"building_width": 64.0, "building_depth": 42.0, "parking_count": 36},
    }
    payload.update(extra)
    return payload


GOLDEN_SCENARIO_REGISTRY: Tuple[GoldenScenario, ...] = (
    GoldenScenario(
        scenario_id="small_commercial_pad",
        name="Small Commercial Pad",
        purpose="Baseline pad site with parking, grading, drainage, storm, sanitary, water, QA, quantities, and exports.",
        required_engine_ids=_fs("geometry", "grading", "drainage", "storm_pipe", "sanitary", "water", "qa_validation", "quantity", "export_cad"),
        required_canonical_signals=("site_boundary", "grading", "drainage", "storm_pipes", "sanitary", "utilities", "quantities"),
        production_gates=("survey/GIS attached or blocked", "storm hydraulics checked", "export audit complete"),
        blocked_without=("survey_surface", "gis_layers", "coordinate_system", "design_standards"),
        benchmark_payload=_payload("Golden Commercial Pad", project_type="commercial_pad", lot_w=220.0, lot_h=160.0),
    ),
    GoldenScenario(
        scenario_id="multifamily_site",
        name="Multifamily Site",
        purpose="Multi-building residential project with service coverage, parking, ADA paths, sanitary, and storm networks.",
        required_engine_ids=_fs("geometry", "grading", "storm_pipe", "sanitary", "roadway_corridor", "qa_validation"),
        required_canonical_signals=("site_boundary", "building_count", "parking_program", "sanitary", "storm_pipes"),
        production_gates=("all buildings served", "ADA paths checked", "storm graph valid"),
        blocked_without=("service_coverage", "ada_path_checks", "survey_surface"),
        benchmark_payload=_payload(
            "Golden Multifamily",
            project_type="multifamily",
            lot_w=460.0,
            lot_h=360.0,
            site_plan={"building_width": 110.0, "building_depth": 58.0, "parking_count": 96, "building_count": 3},
        ),
    ),
    GoldenScenario(
        scenario_id="mixed_use_14_acre_site",
        name="14-Acre Mixed-Use",
        purpose="Large mixed-use benchmark for the whole coordinated civil backend.",
        required_engine_ids=_fs("geometry", "grading", "drainage", "storm_pipe", "sanitary", "water", "utility_coordination", "hydrology", "quantity", "export_cad", "ai_orchestration"),
        required_canonical_signals=("site_boundary", "alignments", "grading", "drainage", "storm_pipes", "sanitary", "utilities", "coordination"),
        production_gates=("detention routing complete", "utility conflicts resolved", "quantities traceable"),
        blocked_without=("detention_routing", "hgl_profile", "coordinate_system", "design_standards"),
        benchmark_payload=_payload(
            "Golden 14-Acre Mixed Use",
            project_type="mixed_use",
            lot_w=875.0,
            lot_h=700.0,
            site_plan={"building_width": 110.0, "building_depth": 58.0, "parking_count": 180, "building_count": 4},
            drainage={"runoff_c": 0.82, "intensity_in_hr": 4.0},
        ),
    ),
    GoldenScenario(
        scenario_id="sloped_detention_site",
        name="Sloped Detention Site",
        purpose="Surface, drainage, hydrology, storm, and earthwork depth on a sloped site with detention.",
        required_engine_ids=_fs("terrain_surface", "grading", "drainage", "storm_pipe", "hydrology", "earthwork", "gis_existing_conditions"),
        required_canonical_signals=("existing_surface", "proposed_surface", "low_points", "basins", "detention_routing", "earthwork"),
        production_gates=("survey/DEM source known", "stage-storage routed", "overflow route reviewed"),
        blocked_without=("survey_surface", "detention_routing", "overflow_route"),
        benchmark_payload=_payload("Golden Sloped Detention", project_type="commercial_pad", lot_w=360.0, lot_h=260.0, terrain={"slope_direction": "southeast", "fall_ft": 8.0}),
    ),
    GoldenScenario(
        scenario_id="roadway_corridor",
        name="Roadway Corridor",
        purpose="Road alignments, profiles, crowns, sidewalks, sections, utilities, and exports.",
        required_engine_ids=_fs("geometry", "terrain_surface", "grading", "roadway_corridor", "utility_coordination", "profile_section", "export_cad", "reactive_model"),
        required_canonical_signals=("alignments", "profiles", "cross_sections", "road_crown_controls", "sheet_registry"),
        production_gates=("profiles trace alignments", "sections trace surface", "ADA checked"),
        blocked_without=("alignments", "profiles", "ada_path_checks", "coordinate_system"),
        benchmark_payload=_payload("Golden Roadway Corridor", project_type="roadway_corridor", lot_w=900.0, lot_h=220.0, deliverables=["road_profile", "cross_sections"]),
    ),
    GoldenScenario(
        scenario_id="utility_conflict_heavy_site",
        name="Utility-Heavy Site",
        purpose="Dense storm, sanitary, water, and conflict solving benchmark.",
        required_engine_ids=_fs("storm_pipe", "sanitary", "water", "utility_coordination", "conflict_resolution", "profile_section", "qa_validation"),
        required_canonical_signals=("storm_pipes", "sanitary", "utilities", "coordination", "resolution_history"),
        production_gates=("crossing rules applied", "reroutes post-validated", "unresolved conflicts explicit"),
        blocked_without=("post_reroute_validation", "separation_rules", "constructability_score"),
        benchmark_payload=_payload("Golden Utility Heavy", project_type="mixed_use", lot_w=520.0, lot_h=420.0, deliverables=["storm_pipe_plan", "sanitary_plan", "utility_plan"]),
    ),
    GoldenScenario(
        scenario_id="floodplain_wetland_constrained_site",
        name="Floodplain/Wetland Constrained",
        purpose="Existing-conditions and protected-zone routing benchmark.",
        required_engine_ids=_fs("gis_existing_conditions", "geometry", "terrain_surface", "drainage", "hydrology", "qa_validation"),
        required_canonical_signals=("existing_conditions", "floodplain_data", "wetland_data", "protected_zones", "drainage"),
        production_gates=("constraints source cited", "protected zones avoided", "overflow risk flagged"),
        blocked_without=("floodplain", "wetlands", "coordinate_system", "protected_zone_routing"),
        benchmark_payload=_payload("Golden Floodplain Wetland", project_type="constrained_site", lot_w=420.0, lot_h=320.0),
    ),
    GoldenScenario(
        scenario_id="retaining_wall_site",
        name="Retaining Wall Site",
        purpose="Steep grading, walls, structures, utility conflicts, sections, and earthwork tradeoffs.",
        required_engine_ids=_fs("terrain_surface", "grading", "structure", "earthwork", "utility_coordination", "profile_section", "quantity"),
        required_canonical_signals=("retaining_walls", "wall_tie_in_checks", "earthwork", "cross_sections", "quantities"),
        production_gates=("wall tie-ins checked", "excavation impacts included", "wall quantities traceable"),
        blocked_without=("wall_tie_in_checks", "structure_conflicts", "section_samples"),
        benchmark_payload=_payload("Golden Retaining Wall", project_type="retaining_wall_site", lot_w=280.0, lot_h=220.0, terrain={"fall_ft": 18.0}),
    ),
    GoldenScenario(
        scenario_id="incomplete_bad_input_case",
        name="Incomplete Input",
        purpose="Truthfulness benchmark proving missing data blocks production readiness.",
        required_engine_ids=_fs("geometry", "gis_existing_conditions", "qa_validation", "ai_orchestration"),
        required_canonical_signals=("missing_requirements", "civil_design_readiness", "engine_readiness"),
        production_gates=("missing data explicit", "no fake production success", "assistant asks for required input"),
        blocked_without=("site_boundary", "survey_surface", "gis_layers", "design_standards"),
        benchmark_payload={"project_name": "Golden Incomplete Input", "units": "ft", "mode": "site_plan"},
    ),
    GoldenScenario(
        scenario_id="manual_production_gate_case",
        name="Manual Production Gate",
        purpose="Manual-mode benchmark proving omitted/locked fields and production gates are not silently autofilled.",
        required_engine_ids=_fs("qa_validation", "conflict_resolution", "export_cad", "reactive_model", "ai_orchestration"),
        required_canonical_signals=("manual_validation", "truth_audit", "civil_design_readiness", "engine_readiness"),
        production_gates=("manual omissions preserved", "export blocked when stale/missing", "assumptions labeled"),
        blocked_without=("manual_validation", "export_audit", "stale_output_blocking"),
        benchmark_payload=_payload("Golden Manual Gate", project_type="commercial_pad", lot_w=180.0, lot_h=140.0, meta={"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True}),
    ),
)


SCENARIO_BY_ID = {scenario.scenario_id: scenario for scenario in GOLDEN_SCENARIO_REGISTRY}


def golden_scenarios() -> Tuple[GoldenScenario, ...]:
    return GOLDEN_SCENARIO_REGISTRY


def get_golden_scenario(scenario_id: str) -> GoldenScenario:
    return SCENARIO_BY_ID[scenario_id]


def scenario_engine_coverage() -> Dict[str, List[str]]:
    coverage: Dict[str, List[str]] = {scenario_id: [] for scenario_id in GOLDEN_SCENARIOS}
    for contract in engine_contracts():
        for scenario_id in contract.golden_scenarios:
            coverage.setdefault(scenario_id, []).append(contract.engine_id)
    return {key: sorted(value) for key, value in coverage.items()}


def validate_golden_scenarios() -> List[str]:
    issues: List[str] = []
    registry_ids = [scenario.scenario_id for scenario in GOLDEN_SCENARIO_REGISTRY]
    if tuple(registry_ids) != GOLDEN_SCENARIOS:
        issues.append("golden scenario registry must match engine contract scenario order")
    if len(registry_ids) != len(set(registry_ids)):
        issues.append("golden scenario ids must be unique")
    known_engines = {contract.engine_id for contract in engine_contracts()}
    for scenario in GOLDEN_SCENARIO_REGISTRY:
        if not scenario.required_engine_ids:
            issues.append(f"{scenario.scenario_id}: required engines missing")
        unknown = sorted(set(scenario.required_engine_ids) - known_engines)
        if unknown:
            issues.append(f"{scenario.scenario_id}: unknown engines {unknown}")
        if not scenario.required_canonical_signals:
            issues.append(f"{scenario.scenario_id}: canonical signals missing")
        if not scenario.production_gates:
            issues.append(f"{scenario.scenario_id}: production gates missing")
        if not scenario.blocked_without:
            issues.append(f"{scenario.scenario_id}: blocked_without missing")
        if not scenario.benchmark_payload.get("project_name"):
            issues.append(f"{scenario.scenario_id}: benchmark payload missing project_name")
    return issues


__all__ = [
    "GoldenScenario",
    "golden_scenarios",
    "get_golden_scenario",
    "scenario_engine_coverage",
    "validate_golden_scenarios",
]
