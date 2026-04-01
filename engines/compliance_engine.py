
from __future__ import annotations

"""
compliance_engine.py (MERGED MAX VERSION)

Purpose
-------
Unified rule-enforcement layer for the AI civil engineering platform.

This file upgrades the original lightweight compliance_engine into a real
multi-discipline compliance system by combining:
- basic compliance review behavior from the original compliance_engine
- deep engineering QA signals from error_check_engine
- geometric / object / zone rule enforcement from constraint_engine
- config-driven thresholds and platform defaults from core.config

Design intent
-------------
- Preserve architecture: planner remains the orchestration brain
- Keep constraint_engine as the geometry / rule backbone
- Keep error_check_engine as the QA / diagnostics layer
- Make compliance_engine the unified standards / rule-enforcement layer
- Return planner/intelligence-ready issue structures
- Support explain / fix / optimize workflows
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from enum import Enum

from core.config import (
    MIN_SLOPE,
    PIPE_MIN_SLOPE,
    PIPE_MAX_INLETS,
    PIPE_INTENSITY_IN_HR,
    PIPE_RUNOFF_C,
)

from core.constraint_engine import (
    BaseConstraint,
    ConstraintEvaluationSummary,
    ConstraintIssue,
    ConstraintResult,
    ConstraintSeverity,
    DuplicateObjectAnchorConstraint,
    MaxSpanConstraint,
    MinObjectSpacingConstraint,
    ObjectOverlapConstraint,
    ZoneContainmentConstraint,
    ZoneOverlapConstraint,
    evaluate_constraints,
)

from core.geometry_core import (
    ProjectModel,
    ZoneType,
)

from engines.error_check_engine import (
    DEFAULT_MAX_ADA_CROSS_SLOPE,
    DEFAULT_MAX_IMPERVIOUS_COVERAGE_RATIO,
    DEFAULT_MAX_PARKING_SLOPE,
    DEFAULT_MAX_PIPE_CAPACITY_RATIO,
    DEFAULT_MAX_ROAD_GRADE,
    DEFAULT_MIN_PIPE_SLOPE,
    DEFAULT_MIN_SITE_SLOPE,
    PARKING_EFFICIENCY_SF_PER_STALL,
    run_plan_checks,
    summarize_issues,
)

# =============================================================================
# ENUMS / MODELS
# =============================================================================


class ComplianceSource(str, Enum):
    BASIC = "basic"
    CONSTRAINT = "constraint"
    ENGINEERING = "engineering"
    PROGRAM = "program"
    SYSTEM = "system"


@dataclass
class ComplianceIssue:
    code: str
    severity: str
    message: str
    category: str = "general"
    source: str = ComplianceSource.BASIC.value
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "source": self.source,
            "context": dict(self.context),
        }


@dataclass
class ComplianceSummary:
    issue_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    critical_codes: List[str] = field(default_factory=list)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    by_code: Dict[str, int] = field(default_factory=dict)
    weighted_penalty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "critical_codes": list(self.critical_codes),
            "by_category": dict(self.by_category),
            "by_source": dict(self.by_source),
            "by_code": dict(self.by_code),
            "weighted_penalty": float(self.weighted_penalty),
        }


@dataclass
class ComplianceResult:
    success: bool
    issues: List[ComplianceIssue] = field(default_factory=list)
    summary: ComplianceSummary = field(default_factory=ComplianceSummary)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": bool(self.success),
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary.to_dict(),
            "meta": dict(self.meta),
        }


# =============================================================================
# HELPERS
# =============================================================================


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _rect_area(width: Any, height: Any) -> float:
    return max(0.0, _safe_float(width, 0.0)) * max(0.0, _safe_float(height, 0.0))


def _append_issue(
    out: List[ComplianceIssue],
    code: str,
    severity: str,
    message: str,
    *,
    category: str = "general",
    source: str = ComplianceSource.BASIC.value,
    context: Optional[Dict[str, Any]] = None,
    dedupe_keys: Optional[set] = None,
) -> None:
    key = f"{code}|{message}"
    if dedupe_keys is not None:
        if key in dedupe_keys:
            return
        dedupe_keys.add(key)
    out.append(
        ComplianceIssue(
            code=code,
            severity=severity,
            message=message,
            category=category,
            source=source,
            context={} if context is None else dict(context),
        )
    )


def _plan_actions(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [a for a in _safe_list(plan.get("actions")) if isinstance(a, dict)]


def _layer_counts(actions: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for action in actions:
        layer = _safe_str(action.get("layer"), "SITE").upper()
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _parking_target(parsed: Dict[str, Any]) -> int:
    site_plan = _safe_dict(parsed.get("site_plan"))
    explicit = _safe_int(site_plan.get("parking_count"), 0)
    if explicit > 0:
        return explicit

    lot = _safe_dict(parsed.get("lot"))
    lot_area = _rect_area(lot.get("w"), lot.get("h"))
    project_type = _lower(parsed.get("project_type"))
    ratio_sf = {
        "office_site": 300.0,
        "commercial_pad": 275.0,
        "strip_center": 250.0,
        "industrial_site": 800.0,
        "multifamily_site": 625.0,  # concept proxy for 1.6/1000 sf yield-like behavior
        "generic_site": 325.0,
    }.get(project_type, 325.0)
    if lot_area <= 0.0:
        return 0
    return max(0, int(round((lot_area * 0.35) / max(1.0, ratio_sf))))


def _estimated_parking_count_from_plan(plan: Dict[str, Any]) -> int:
    actions = _plan_actions(plan)
    parking_area = 0.0
    for action in actions:
        layer = _safe_str(action.get("layer"), "").upper()
        label = _lower(action.get("label"))
        if layer not in {"PARKING", "PAVEMENT"} and "park" not in label:
            continue
        if _lower(action.get("task")) != "rectangle":
            continue
        parking_area += _rect_area(action.get("width"), action.get("height"))
    if parking_area <= 0.0:
        return 0
    return int(round(parking_area / PARKING_EFFICIENCY_SF_PER_STALL))


def _severity_weight(severity: str) -> float:
    sev = _lower(severity)
    if sev == "error":
        return 10.0
    if sev == "warning":
        return 3.0
    return 1.0


def _summary_from_issues(issues: Sequence[ComplianceIssue]) -> ComplianceSummary:
    summary = ComplianceSummary()
    summary.issue_count = len(issues)
    critical: List[str] = []

    for issue in issues:
        sev = _lower(issue.severity)
        if sev == "error":
            summary.error_count += 1
            critical.append(issue.code)
        elif sev == "warning":
            summary.warning_count += 1
        else:
            summary.info_count += 1

        summary.by_category[issue.category] = summary.by_category.get(issue.category, 0) + 1
        summary.by_source[issue.source] = summary.by_source.get(issue.source, 0) + 1
        summary.by_code[issue.code] = summary.by_code.get(issue.code, 0) + 1
        summary.weighted_penalty += _severity_weight(issue.severity)

    summary.critical_codes = list(dict.fromkeys(critical))
    return summary


def _constraint_result_to_issue(result: ConstraintResult) -> ComplianceIssue:
    severity = str(result.severity.value if hasattr(result.severity, "value") else result.severity).lower()
    category = "constraints"
    rule_name = _safe_str(result.rule_name, "constraint")
    if "spacing" in rule_name:
        category = "spacing"
    elif "containment" in rule_name or "zone" in rule_name:
        category = "site"
    elif "span" in rule_name:
        category = "structure"
    elif "overlap" in rule_name:
        category = "geometry"

    ctx = dict(result.meta or {})
    if result.object_id:
        ctx["object_id"] = result.object_id

    return ComplianceIssue(
        code=f"CONSTRAINT_{rule_name.upper()}",
        severity=severity,
        message=result.message or f"Constraint violation: {rule_name}",
        category=category,
        source=ComplianceSource.CONSTRAINT.value,
        context=ctx,
    )


def _engineering_issue_to_compliance(issue: Dict[str, Any]) -> ComplianceIssue:
    return ComplianceIssue(
        code=_safe_str(issue.get("code"), "ENGINEERING_ISSUE"),
        severity=_safe_str(issue.get("severity"), "warning"),
        message=_safe_str(issue.get("message"), "Engineering compliance issue"),
        category=_safe_str(issue.get("category"), "general"),
        source=ComplianceSource.ENGINEERING.value,
        context=deepcopy_dict(_safe_dict(issue.get("context"))),
    )


def deepcopy_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = deepcopy_dict(v)
        elif isinstance(v, list):
            out[k] = [deepcopy_dict(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


# =============================================================================
# CORE COMPLIANCE RULES
# =============================================================================


def _review_basic_presence(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    actions = _plan_actions(plan)
    layers = _layer_counts(actions)

    if not any(layer == "BUILDING" for layer in layers):
        _append_issue(
            issues,
            "NO_BUILDING",
            "warning",
            "No building geometry found.",
            category="site",
            source=ComplianceSource.BASIC.value,
            dedupe_keys=seen,
        )

    if not any(layer in {"ROAD", "PAVEMENT", "PARKING"} for layer in layers):
        _append_issue(
            issues,
            "NO_ACCESS",
            "warning",
            "No road / pavement / parking access found.",
            category="circulation",
            source=ComplianceSource.BASIC.value,
            dedupe_keys=seen,
        )

    mode = _lower(parsed.get("mode"))
    if mode in {"site_plan", "subdivision"} and layers.get("LOT", 0) == 0:
        _append_issue(
            issues,
            "NO_LOT_SIGNAL",
            "warning",
            "No obvious lot/site boundary signal found.",
            category="site",
            source=ComplianceSource.BASIC.value,
            dedupe_keys=seen,
        )


def _review_program_compliance(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    mode = _lower(parsed.get("mode"))
    if mode not in {"site_plan", "subdivision"}:
        return

    target = _parking_target(parsed)
    actual = _estimated_parking_count_from_plan(plan)

    if target > 0 and actual < target:
        _append_issue(
            issues,
            "PARKING_PROGRAM_SHORTFALL",
            "warning",
            "Estimated parking count is below target.",
            category="parking",
            source=ComplianceSource.PROGRAM.value,
            context={"target_count": target, "estimated_count": actual},
            dedupe_keys=seen,
        )

    if target > 0 and actual > max(target * 1.5, target + 25):
        _append_issue(
            issues,
            "PARKING_PROGRAM_EXCESSIVE",
            "warning",
            "Estimated parking count is materially above target.",
            category="parking",
            source=ComplianceSource.PROGRAM.value,
            context={"target_count": target, "estimated_count": actual},
            dedupe_keys=seen,
        )


def _review_ada_and_access(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    actions = _plan_actions(plan)
    layers = _layer_counts(actions)
    mode = _lower(parsed.get("mode"))

    if mode in {"site_plan", "subdivision"}:
        has_walk = layers.get("WALK", 0) > 0 or any("sidewalk" in _lower(a.get("label")) or "sidewalk" in _lower(a.get("text")) for a in actions)
        if not has_walk:
            _append_issue(
                issues,
                "SIDEWALK_NETWORK_MISSING",
                "warning",
                "No obvious sidewalk / pedestrian network was found.",
                category="ada",
                source=ComplianceSource.SYSTEM.value,
                dedupe_keys=seen,
            )

    meta = _safe_dict(plan.get("meta"))
    eng = _safe_dict(meta.get("engineering_metrics"))
    parking_target = _safe_float(eng.get("parking_target_count"), 0.0)
    parking_actual = _safe_float(eng.get("parking_actual_count"), 0.0)
    if parking_actual >= 20 and not any("ada" in _lower(a.get("label")) or "ada" in _lower(a.get("text")) for a in actions):
        _append_issue(
            issues,
            "ADA_STALL_SIGNAL_MISSING",
            "warning",
            "Parking supply is material, but no ADA stall / aisle signal was detected.",
            category="ada",
            source=ComplianceSource.SYSTEM.value,
            context={"parking_actual_count": parking_actual, "parking_target_count": parking_target},
            dedupe_keys=seen,
        )


def _review_drainage_and_detention(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    actions = _plan_actions(plan)
    layers = _layer_counts(actions)
    mode = _lower(parsed.get("mode"))
    meta = _safe_dict(plan.get("meta"))
    eng = _safe_dict(meta.get("engineering_metrics"))

    if mode in {"drainage", "site_plan", "subdivision"}:
        if layers.get("PIPE", 0) > 0 and layers.get("BASIN_BOUNDARY", 0) == 0:
            _append_issue(
                issues,
                "DRAINAGE_WITHOUT_DETENTION_SIGNAL",
                "warning",
                "Pipe/drainage geometry exists but no basin / pond / outfall signal was found.",
                category="detention",
                source=ComplianceSource.SYSTEM.value,
                dedupe_keys=seen,
            )

        runoff = _safe_float(eng.get("rational_runoff_cfs"), 0.0)
        cap = _safe_float(eng.get("pipe_capacity_total_cfs"), 0.0)
        if runoff > 0.0 and cap > 0.0 and runoff > cap * DEFAULT_MAX_PIPE_CAPACITY_RATIO:
            _append_issue(
                issues,
                "DRAINAGE_CAPACITY_DEFICIT",
                "warning",
                "Estimated runoff materially exceeds aggregate pipe capacity.",
                category="drainage",
                source=ComplianceSource.SYSTEM.value,
                context={"rational_runoff_cfs": runoff, "pipe_capacity_total_cfs": cap},
                dedupe_keys=seen,
            )


def _review_utility_coordination(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    project_type = _lower(parsed.get("project_type"))
    if project_type not in {
        "commercial_pad",
        "office_site",
        "multifamily_site",
        "strip_center",
        "industrial_site",
        "residential_subdivision",
        "corridor_roadway",
        "generic_site",
    }:
        return

    actions = _plan_actions(plan)
    layers = _layer_counts(actions)
    utility_signal = (
        layers.get("UTILITY", 0)
        + layers.get("WATER", 0)
        + layers.get("SEWER", 0)
        + layers.get("SAN", 0)
        + layers.get("PIPE", 0)
    )

    if utility_signal == 0:
        _append_issue(
            issues,
            "UTILITY_NETWORK_MISSING",
            "warning",
            "Utility-supporting project type lacks obvious utility / storm / sewer network signals.",
            category="utilities",
            source=ComplianceSource.SYSTEM.value,
            context={"project_type": project_type},
            dedupe_keys=seen,
        )


def _review_cross_discipline_meta(parsed: Dict[str, Any], plan: Dict[str, Any], issues: List[ComplianceIssue], seen: set) -> None:
    meta = _safe_dict(plan.get("meta"))
    quantities = _safe_dict(meta.get("quantities"))
    explanation = _safe_dict(meta.get("explanation"))
    eng = _safe_dict(meta.get("engineering_metrics"))

    if not quantities:
        _append_issue(
            issues,
            "QUANTITY_REPORT_MISSING",
            "info",
            "Quantities report metadata is missing.",
            category="reports",
            source=ComplianceSource.SYSTEM.value,
            dedupe_keys=seen,
        )

    if not explanation:
        _append_issue(
            issues,
            "EXPLAIN_OUTPUT_MISSING",
            "info",
            "Explain-plan metadata is missing.",
            category="reports",
            source=ComplianceSource.SYSTEM.value,
            dedupe_keys=seen,
        )

    if _lower(parsed.get("mode")) in {"site_plan", "subdivision", "drainage"} and not eng:
        _append_issue(
            issues,
            "ENGINEERING_METRICS_MISSING",
            "warning",
            "Engineering metrics metadata is missing for a design mode that should produce it.",
            category="reports",
            source=ComplianceSource.SYSTEM.value,
            dedupe_keys=seen,
        )


# =============================================================================
# CONSTRAINT BUILDERS
# =============================================================================


def build_default_compliance_constraints(project: ProjectModel) -> List[BaseConstraint]:
    constraints: List[BaseConstraint] = []

    if getattr(project, "objects", None):
        constraints.append(
            ObjectOverlapConstraint(
                object_kinds=["building", "building_wing", "building_footprint_piece"],
                ignore_same_name_prefix=True,
                severity=ConstraintSeverity.WARNING,
            )
        )
        constraints.append(
            DuplicateObjectAnchorConstraint(
                tolerance=0.01,
                object_kinds=["building_entry", "stair", "elevator", "utility_node", "hydrant", "cleanout"],
                severity=ConstraintSeverity.INFO,
            )
        )
        constraints.append(
            MinObjectSpacingConstraint(
                min_spacing=4.0,
                object_kinds=["hydrant", "manhole", "inlet", "cleanout"],
            )
        )

    if getattr(project, "zones", None):
        constraints.append(
            ZoneOverlapConstraint(
                zone_types=[
                    ZoneType.BUILDING,
                    ZoneType.LOT,
                    ZoneType.ROAD,
                    ZoneType.CORRIDOR,
                    ZoneType.PARKING,
                    ZoneType.DRAINAGE,
                    ZoneType.DETENTION,
                ],
                severity=ConstraintSeverity.WARNING,
            )
        )

    if hasattr(project, "objects_by_kind") and project.objects_by_kind("beam"):
        constraints.append(MaxSpanConstraint(max_length=40.0, object_kind="beam"))

    return constraints


# =============================================================================
# PUBLIC ENTRYPOINTS
# =============================================================================


def review_basic_compliance(plan: Dict[str, Any]) -> ComplianceResult:
    """
    Backward-compatible lightweight entrypoint preserved from the original file.
    """
    issues: List[ComplianceIssue] = []
    seen: set = set()
    _review_basic_presence({}, plan, issues, seen)
    summary = _summary_from_issues(issues)
    return ComplianceResult(success=summary.error_count == 0, issues=issues, summary=summary)


def review_plan_compliance(
    parsed: Optional[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    project: Optional[ProjectModel] = None,
    extra_constraints: Optional[Sequence[BaseConstraint]] = None,
    persist_constraint_issues_to_project: bool = False,
    min_site_slope: float = max(DEFAULT_MIN_SITE_SLOPE, MIN_SLOPE),
    max_parking_slope: float = DEFAULT_MAX_PARKING_SLOPE,
    max_ada_cross_slope: float = DEFAULT_MAX_ADA_CROSS_SLOPE,
    max_road_grade: float = DEFAULT_MAX_ROAD_GRADE,
    min_pipe_slope: float = max(DEFAULT_MIN_PIPE_SLOPE, PIPE_MIN_SLOPE),
    max_pipe_capacity_ratio: float = DEFAULT_MAX_PIPE_CAPACITY_RATIO,
    max_impervious_coverage_ratio: float = DEFAULT_MAX_IMPERVIOUS_COVERAGE_RATIO,
) -> ComplianceResult:
    """
    Main compliance entrypoint.

    Combines:
    - basic/system/program presence checks
    - engineering QA from error_check_engine
    - geometry/zone/object rules from constraint_engine
    """
    parsed = _safe_dict(parsed)
    issues: List[ComplianceIssue] = []
    seen: set = set()

    # 1) Basic / program / system compliance
    _review_basic_presence(parsed, plan, issues, seen)
    _review_program_compliance(parsed, plan, issues, seen)
    _review_ada_and_access(parsed, plan, issues, seen)
    _review_drainage_and_detention(parsed, plan, issues, seen)
    _review_utility_coordination(parsed, plan, issues, seen)
    _review_cross_discipline_meta(parsed, plan, issues, seen)

    # 2) Engineering QA layer
    engineering_issues = run_plan_checks(
        parsed,
        plan,
        min_site_slope=min_site_slope,
        max_parking_slope=max_parking_slope,
        max_ada_cross_slope=max_ada_cross_slope,
        max_road_grade=max_road_grade,
        min_pipe_slope=min_pipe_slope,
        max_pipe_capacity_ratio=max_pipe_capacity_ratio,
        max_impervious_coverage_ratio=max_impervious_coverage_ratio,
    )
    for issue in engineering_issues:
        comp = _engineering_issue_to_compliance(issue)
        _append_issue(
            issues,
            comp.code,
            comp.severity,
            comp.message,
            category=comp.category,
            source=comp.source,
            context=comp.context,
            dedupe_keys=seen,
        )

    # 3) Constraint layer
    constraint_summary: Optional[ConstraintEvaluationSummary] = None
    if project is not None:
        constraints = build_default_compliance_constraints(project)
        if extra_constraints:
            constraints.extend(list(extra_constraints))
        constraint_summary = evaluate_constraints(
            project=project,
            constraints=constraints,
            persist_to_project=persist_constraint_issues_to_project,
        )
        for result in constraint_summary.results:
            if result.passed:
                continue
            comp_issue = _constraint_result_to_issue(result)
            _append_issue(
                issues,
                comp_issue.code,
                comp_issue.severity,
                comp_issue.message,
                category=comp_issue.category,
                source=comp_issue.source,
                context=comp_issue.context,
                dedupe_keys=seen,
            )

    summary = _summary_from_issues(issues)

    meta: Dict[str, Any] = {
        "defaults_used": {
            "min_site_slope": min_site_slope,
            "max_parking_slope": max_parking_slope,
            "max_ada_cross_slope": max_ada_cross_slope,
            "max_road_grade": max_road_grade,
            "min_pipe_slope": min_pipe_slope,
            "max_pipe_capacity_ratio": max_pipe_capacity_ratio,
            "max_impervious_coverage_ratio": max_impervious_coverage_ratio,
            "pipe_intensity_in_hr": PIPE_INTENSITY_IN_HR,
            "pipe_runoff_c": PIPE_RUNOFF_C,
            "pipe_max_inlets": PIPE_MAX_INLETS,
        },
        "engineering_summary": summarize_issues(engineering_issues),
        "constraint_summary": {
            "passed": constraint_summary.passed,
            "total_results": constraint_summary.total_results,
            "failed_results": constraint_summary.failed_results,
            "info_count": constraint_summary.info_count,
            "warning_count": constraint_summary.warning_count,
            "error_count": constraint_summary.error_count,
        } if constraint_summary else {},
        "autofix_hooks": {
            "eligible_codes": [
                "BUILDING_OUTSIDE_SETBACK",
                "BUILDING_OUTSIDE_LOT",
                "PARKING_OVERLAPS_BUILDING",
                "PARKING_OUTSIDE_LOT",
                "DRIVEWAY_OUTSIDE_LOT",
                "DRIVEWAY_NOT_CONNECTED_TO_PARKING",
                "PARKING_PROGRAM_SHORTFALL",
            ]
        },
        "optimization_hooks": {
            "penalty_weight": summary.weighted_penalty,
            "critical_codes": list(summary.critical_codes),
            "category_penalties": dict(summary.by_category),
        },
    }

    return ComplianceResult(
        success=summary.error_count == 0,
        issues=issues,
        summary=summary,
        meta=meta,
    )


def summarize_compliance_for_planner(result: ComplianceResult) -> Dict[str, Any]:
    """
    Compact planner/intelligence-facing summary.
    """
    return {
        "success": bool(result.success),
        "issue_count": result.summary.issue_count,
        "error_count": result.summary.error_count,
        "warning_count": result.summary.warning_count,
        "info_count": result.summary.info_count,
        "critical_codes": list(result.summary.critical_codes),
        "weighted_penalty": float(result.summary.weighted_penalty),
        "by_category": dict(result.summary.by_category),
        "by_source": dict(result.summary.by_source),
    }
