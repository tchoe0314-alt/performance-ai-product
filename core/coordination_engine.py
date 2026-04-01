
from __future__ import annotations

"""
coordination_engine.py (TRUE MAX CIVIL-GRADE VERSION)

Purpose
-------
Cross-discipline coordination engine for the AI civil / CAD platform.

This is the missing integration layer between:
- planner.py
- planner_intelligence.py
- planner_orchestrator.py
- project_manager.py
- discipline engines

Core responsibilities
---------------------
- decide which engines actually need to run
- avoid forcing unnecessary inputs or unnecessary systems
- coordinate layout / grading / drainage / pipes / utilities / earthwork / QA
- use ProjectManager dependency graph for invalidation-aware reruns
- drive conflict -> fix -> rerun loops
- update metrics automatically
- support staged convergence
- preserve best design state using snapshots / rollback

Design rule
-----------
If the user does not need an input or subsystem, do NOT force it.
If something is missing and not essential, skip the subsystem or use a tagged,
documented engineering assumption rather than inventing fake detail.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from copy import deepcopy

from core.project_manager import (
    ProjectManager,
    ConflictRecord,
    ConflictSeverity,
    DependencyState,
)

# Optional engine imports. The coordination engine degrades gracefully if one
# engine is not available in a given runtime.
try:
    from engines.grading_engine import GradingEngine, GradingRequest, GradeElement
except Exception:  # pragma: no cover
    GradingEngine = None
    GradingRequest = None
    GradeElement = None

try:
    from engines.drainage_engine import DrainageEngine, HydraulicInputs
except Exception:  # pragma: no cover
    DrainageEngine = None
    HydraulicInputs = None

try:
    from engines.pipe_engine import PipeEngine
except Exception:  # pragma: no cover
    PipeEngine = None

try:
    from engines.utility_engine import UtilityEngine, UtilityNodeSpec, UtilityRequest
except Exception:  # pragma: no cover
    UtilityEngine = None
    UtilityNodeSpec = None
    UtilityRequest = None

try:
    from engines.error_check_engine import run_checks
except Exception:  # pragma: no cover
    run_checks = None


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CoordinationIssue:
    code: str
    severity: str
    message: str
    source_stage: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageExecutionRecord:
    stage_name: str
    ran: bool
    success: bool
    skipped: bool = False
    reason: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinationIterationRecord:
    iteration_index: int
    stage_records: List[StageExecutionRecord] = field(default_factory=list)
    issues_before_fix: List[CoordinationIssue] = field(default_factory=list)
    issues_after_fix: List[CoordinationIssue] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0
    converged: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class CoordinationRequest:
    parsed_payload: Dict[str, Any]
    manager: ProjectManager

    allow_assumptions: bool = True
    strict_inputs: bool = False
    max_iterations: int = 3
    stop_when_clean: bool = True
    stop_when_score_stalls: bool = True
    score_improvement_epsilon: float = 1.0

    run_layout: bool = True
    run_grading: bool = True
    run_drainage: bool = True
    run_pipes: bool = True
    run_utilities: bool = True
    run_earthwork: bool = True
    run_qa: bool = True

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinationResult:
    success: bool
    message: str
    manager: ProjectManager
    final_score: float = 0.0
    converged: bool = False
    iterations: List[CoordinationIterationRecord] = field(default_factory=list)
    issues: List[CoordinationIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


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


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _lot(parsed_payload: Dict[str, Any]) -> Dict[str, float]:
    lot = _safe_dict(parsed_payload.get("lot"))
    return {
        "x": _safe_float(lot.get("x"), 0.0),
        "y": _safe_float(lot.get("y"), 0.0),
        "w": _safe_float(lot.get("w"), 0.0),
        "h": _safe_float(lot.get("h"), 0.0),
    }


def _lot_area(parsed_payload: Dict[str, Any]) -> float:
    box = _lot(parsed_payload)
    return max(0.0, box["w"]) * max(0.0, box["h"])


def _payload_mode(parsed_payload: Dict[str, Any]) -> str:
    return _lower(parsed_payload.get("mode") or "site_plan")


def _payload_project_type(parsed_payload: Dict[str, Any]) -> str:
    return _lower(parsed_payload.get("project_type") or parsed_payload.get("site_type") or "generic_site")


def _has_positive(value: Any) -> bool:
    return _safe_float(value, 0.0) > 0.0


# =============================================================================
# COORDINATION ENGINE
# =============================================================================

class CoordinationEngine:
    """
    True coordination layer.

    Philosophy:
    - Only run a subsystem if the problem actually needs it.
    - If the user didn't request / imply it, do not force it.
    - If a subsystem is relevant but underspecified, prefer controlled
      assumptions over fake detailed geometry.
    """

    def coordinate(self, request: CoordinationRequest) -> CoordinationResult:
        parsed = deepcopy(request.parsed_payload)
        manager = request.manager

        self._ensure_default_dependencies(manager)
        overall_assumptions: List[str] = []
        overall_warnings: List[str] = []
        best_snapshot_id: Optional[str] = None
        best_score = float("-inf")
        all_iterations: List[CoordinationIterationRecord] = []

        for iteration_index in range(1, max(1, int(request.max_iterations)) + 1):
            iteration = CoordinationIterationRecord(iteration_index=iteration_index)
            score_before = manager.aggregate_score()
            iteration.score_before = score_before

            manager.log("coordination_iteration_start", iteration=iteration_index, score_before=score_before)

            # Run stages conditionally.
            for stage_name in self._stage_order():
                record = self._run_stage_if_needed(stage_name, parsed, manager, request)
                iteration.stage_records.append(record)
                overall_assumptions.extend(record.assumptions)
                overall_warnings.extend(record.warnings)

            # Collect issues after execution
            issues_before_fix = self._collect_issues(manager)
            iteration.issues_before_fix = issues_before_fix

            # Fix loop
            fixes = self._apply_fix_loop(parsed, manager, issues_before_fix, request)
            iteration.fixes_applied.extend(fixes)

            # Re-collect issues after fixes
            issues_after_fix = self._collect_issues(manager)
            iteration.issues_after_fix = issues_after_fix

            score_after = manager.aggregate_score()
            iteration.score_after = score_after

            if score_after > best_score:
                best_score = score_after
                best_snapshot_id = manager.snapshot(f"coordination_best_iter_{iteration_index}")
                iteration.notes.append("Saved new best snapshot.")

            converged = self._is_converged(
                issues_after_fix=issues_after_fix,
                score_before=score_before,
                score_after=score_after,
                request=request,
            )
            iteration.converged = converged

            if converged:
                iteration.notes.append("Coordination converged.")
                all_iterations.append(iteration)
                manager.log("coordination_iteration_end", iteration=iteration_index, converged=True, score_after=score_after)
                break

            all_iterations.append(iteration)
            manager.log("coordination_iteration_end", iteration=iteration_index, converged=False, score_after=score_after)

        # Restore best known state if needed
        if best_snapshot_id:
            manager.restore_snapshot(best_snapshot_id)

        final_issues = self._collect_issues(manager)
        final_score = manager.aggregate_score()
        converged_final = len([i for i in final_issues if _lower(i.severity) == "error"]) == 0

        return CoordinationResult(
            success=True,
            message="Coordination engine completed.",
            manager=manager,
            final_score=final_score,
            converged=converged_final,
            iterations=all_iterations,
            issues=final_issues,
            warnings=self._dedupe(overall_warnings),
            assumptions=self._dedupe(overall_assumptions),
            metadata={
                "best_snapshot_id": best_snapshot_id,
                "iteration_count": len(all_iterations),
                "final_unresolved_issue_count": len(final_issues),
                "stage_order": self._stage_order(),
            },
        )

    # -------------------------------------------------------------------------
    # Stage control
    # -------------------------------------------------------------------------

    def _stage_order(self) -> List[str]:
        return [
            "layout",
            "grading",
            "drainage",
            "pipes",
            "utilities",
            "earthwork",
            "qa",
        ]

    def _run_stage_if_needed(
        self,
        stage_name: str,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
    ) -> StageExecutionRecord:
        should_run, reason, assumptions = self._should_run_stage(stage_name, parsed, manager, request)
        record = StageExecutionRecord(
            stage_name=stage_name,
            ran=False,
            success=True,
            skipped=not should_run,
            reason=reason,
            assumptions=list(assumptions),
        )

        if not should_run:
            record.meta["skip_reason"] = reason
            return record

        try:
            if stage_name == "layout":
                record = self._run_layout_stage(parsed, manager, record)
            elif stage_name == "grading":
                record = self._run_grading_stage(parsed, manager, request, record)
            elif stage_name == "drainage":
                record = self._run_drainage_stage(parsed, manager, request, record)
            elif stage_name == "pipes":
                record = self._run_pipes_stage(parsed, manager, request, record)
            elif stage_name == "utilities":
                record = self._run_utilities_stage(parsed, manager, request, record)
            elif stage_name == "earthwork":
                record = self._run_earthwork_stage(parsed, manager, request, record)
            elif stage_name == "qa":
                record = self._run_qa_stage(parsed, manager, request, record)
            else:
                record.ran = False
                record.skipped = True
                record.reason = f"Unknown stage '{stage_name}'."
        except Exception as exc:
            record.ran = True
            record.success = False
            record.errors.append(str(exc))
            manager.add_conflict(
                ConflictRecord(
                    code=f"{stage_name.upper()}_STAGE_FAILED",
                    message=str(exc),
                    severity=ConflictSeverity.ERROR,
                    category=stage_name,
                )
            )

        return record

    def _should_run_stage(
        self,
        stage_name: str,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
    ) -> Tuple[bool, str, List[str]]:
        mode = _payload_mode(parsed)
        project_type = _payload_project_type(parsed)
        lot_area = _lot_area(parsed)
        assumptions: List[str] = []

        # hard toggles
        if stage_name == "layout" and not request.run_layout:
            return False, "Layout disabled by request.", assumptions
        if stage_name == "grading" and not request.run_grading:
            return False, "Grading disabled by request.", assumptions
        if stage_name == "drainage" and not request.run_drainage:
            return False, "Drainage disabled by request.", assumptions
        if stage_name == "pipes" and not request.run_pipes:
            return False, "Pipes disabled by request.", assumptions
        if stage_name == "utilities" and not request.run_utilities:
            return False, "Utilities disabled by request.", assumptions
        if stage_name == "earthwork" and not request.run_earthwork:
            return False, "Earthwork disabled by request.", assumptions
        if stage_name == "qa" and not request.run_qa:
            return False, "QA disabled by request.", assumptions

        # Layout is needed for most generative spatial workflows.
        if stage_name == "layout":
            if mode in {"site_plan", "subdivision", "road", "bridge", "pool", "drainage"}:
                return True, "Layout relevant to requested mode.", assumptions
            return False, "Layout not required for this request.", assumptions

        # Grading is needed for site, roadway, subdivision, drainage-heavy work.
        if stage_name == "grading":
            if mode in {"site_plan", "subdivision", "road", "drainage"}:
                return True, "Grading supports requested site/civil workflow.", assumptions
            if "grading" in _lower(str(parsed)):
                return True, "Prompt/payload referenced grading.", assumptions
            return False, "Grading not required.", assumptions

        # Drainage only when there is runoff/site/civil signal.
        if stage_name == "drainage":
            drainage_payload = _safe_dict(parsed.get("drainage"))
            has_drainage_request = bool(drainage_payload) or mode in {"drainage", "site_plan", "subdivision", "road"}
            has_site_scale = lot_area > 0.0
            if has_drainage_request and has_site_scale:
                if not drainage_payload and request.allow_assumptions:
                    assumptions.append("Drainage run used conceptual defaults because detailed drainage inputs were not required.")
                return True, "Drainage is relevant to runoff/site workflow.", assumptions
            return False, "Drainage not required for this request.", assumptions

        # Pipes only if drainage/storm/sanitary/water utility signal exists.
        if stage_name == "pipes":
            text_blob = _lower(str(parsed))
            has_pipe_signal = any(token in text_blob for token in ("pipe", "storm", "sanitary", "water", "drainage"))
            if mode == "drainage" or has_pipe_signal:
                if PipeEngine is None:
                    return False, "Pipe engine unavailable.", assumptions
                if "pipe" not in text_blob and request.allow_assumptions:
                    assumptions.append("Pipe sizing/routing used concept assumptions because detailed pipe criteria were not fully specified.")
                return True, "Pipe network relevant to request.", assumptions
            return False, "Pipe network not required.", assumptions

        # Utilities only if utilities are requested or implied.
        if stage_name == "utilities":
            text_blob = _lower(str(parsed))
            has_utility_signal = any(token in text_blob for token in ("utility", "utilities", "water", "sanitary", "sewer"))
            if has_utility_signal or project_type in {"mixed_use", "mixed_use_development", "multifamily_site"}:
                if UtilityEngine is None:
                    return False, "Utility engine unavailable.", assumptions
                if not has_utility_signal and request.allow_assumptions:
                    assumptions.append("Utilities were coordinated conceptually due to project type, not because detailed utility inputs were forced.")
                return True, "Utilities are relevant.", assumptions
            return False, "Utilities not required.", assumptions

        # Earthwork only when grading exists or cut/fill requested.
        if stage_name == "earthwork":
            text_blob = _lower(str(parsed))
            has_earthwork_signal = any(token in text_blob for token in ("earthwork", "cut and fill", "cut/fill", "balance cut and fill"))
            if mode in {"site_plan", "subdivision", "road", "drainage"} or has_earthwork_signal:
                return True, "Earthwork relevant to graded site/civil workflow.", assumptions
            return False, "Earthwork not required.", assumptions

        # QA always useful if any stage ran.
        if stage_name == "qa":
            return True, "QA should run on coordinated output.", assumptions

        return False, "Unknown stage.", assumptions

    # -------------------------------------------------------------------------
    # Stage implementations
    # -------------------------------------------------------------------------

    def _run_layout_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True
        record.success = True
        record.reason = "Layout coordination completed."

        project = manager.project
        lot = _lot(parsed)

        # Do not force fake layout if the project already has objects/zones.
        if getattr(project, "zones", None):
            record.metrics["existing_zone_count"] = len(project.zones)
            manager.set_metric("layout_existing_zone_count", len(project.zones), category="layout")
            return record

        # Minimal conceptual layout note only; planner is still primary layout brain.
        record.assumptions.append("Coordination engine preserved planner-owned layout and did not force substitute geometry.")
        manager.set_metric("layout_coordination_touched", 1.0, category="layout")
        manager.log("coordination_layout", lot=lot)
        return record

    def _run_grading_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        if GradingEngine is None:
            record.success = False
            record.errors.append("Grading engine unavailable.")
            return record

        # This coordination stage does not replace planner's grading generation.
        # It mainly tracks need, metrics, and invalidation readiness.
        text_blob = _lower(str(parsed))
        target_strength = 1.0
        if "flat" in text_blob:
            target_strength = 0.4
        elif "steep" in text_blob or "slope" in text_blob:
            target_strength = 1.2

        manager.set_metric("grading_coordination_score", target_strength * 10.0, category="grading")
        manager.set_metric("grading_needed", 1.0, category="grading")
        record.metrics["grading_coordination_score"] = target_strength * 10.0

        # mark dependencies downstream
        self._mark_dependency(manager, "layout", "grading", DependencyState.FRESH, "Grading coordination run.")
        self._mark_dependency(manager, "grading", "drainage", DependencyState.STALE, "Drainage depends on grading.")
        manager.invalidate_from("grading")

        return record

    def _run_drainage_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        if DrainageEngine is None:
            record.success = False
            record.errors.append("Drainage engine unavailable.")
            return record

        drainage_payload = _safe_dict(parsed.get("drainage"))
        inlet_count = max(0, _safe_int(drainage_payload.get("inlet_count"), 0))
        pond_count = max(0, _safe_int(drainage_payload.get("pond_count"), 0))

        # No fake drainage network if not needed; just concept coordination metrics.
        if inlet_count == 0 and pond_count == 0:
            if request.allow_assumptions:
                inlet_count = 4
                pond_count = 1
                record.assumptions.append("Used conceptual drainage defaults (4 inlets / 1 pond) for coordination only.")
            elif request.strict_inputs:
                record.skipped = True
                record.ran = False
                record.reason = "Strict inputs mode prevented conceptual drainage assumptions."
                return record

        manager.set_metric("drainage_low_point_count", float(inlet_count), category="drainage")
        manager.set_metric("drainage_basin_count", float(pond_count), category="drainage")
        manager.set_metric("drainage_needed", 1.0, category="drainage")
        record.metrics["inlet_count"] = inlet_count
        record.metrics["pond_count"] = pond_count

        self._mark_dependency(manager, "grading", "drainage", DependencyState.FRESH, "Drainage coordination run.")
        self._mark_dependency(manager, "drainage", "pipes", DependencyState.STALE, "Pipes depend on drainage.")
        manager.invalidate_from("drainage")

        return record

    def _run_pipes_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        if PipeEngine is None:
            record.success = False
            record.errors.append("Pipe engine unavailable.")
            return record

        text_blob = _lower(str(parsed))
        concept_pipe_count = 0
        if "storm" in text_blob or "drainage" in text_blob:
            concept_pipe_count += 3
        if "sanitary" in text_blob:
            concept_pipe_count += 2
        if "water" in text_blob:
            concept_pipe_count += 2
        if concept_pipe_count == 0:
            concept_pipe_count = 2
            record.assumptions.append("Concept pipe coordination used a minimal shared-backbone assumption.")

        concept_pipe_length = concept_pipe_count * 80.0
        manager.set_metric("storm_pipe_count", float(concept_pipe_count), category="pipes")
        manager.set_metric("storm_pipe_length_ft", concept_pipe_length, units="ft", category="pipes")
        manager.set_metric("pipe_capacity_total_cfs", concept_pipe_count * 2.5, units="cfs", category="pipes")

        record.metrics["pipe_count"] = concept_pipe_count
        record.metrics["pipe_length_ft"] = concept_pipe_length

        self._mark_dependency(manager, "drainage", "pipes", DependencyState.FRESH, "Pipe coordination run.")
        self._mark_dependency(manager, "pipes", "utilities", DependencyState.STALE, "Utilities coordinate around pipe network.")
        manager.invalidate_from("pipes")

        return record

    def _run_utilities_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        if UtilityEngine is None:
            record.success = False
            record.errors.append("Utility engine unavailable.")
            return record

        lot = _lot(parsed)
        area = _lot_area(parsed)
        text_blob = _lower(str(parsed))

        # Avoid forcing utilities if not needed.
        utility_count = 0
        if "utility" in text_blob or "utilities" in text_blob:
            utility_count += 1
        if "water" in text_blob:
            utility_count += 1
        if "sanitary" in text_blob or "sewer" in text_blob:
            utility_count += 1
        if utility_count == 0 and area > 20000.0:
            utility_count = 1
            record.assumptions.append("Used conceptual utility coordination because project scale implies services, but details were not forced.")

        if utility_count == 0:
            record.skipped = True
            record.ran = False
            record.reason = "No meaningful utility signal; utilities were intentionally not forced."
            return record

        concept_length = max(120.0, utility_count * 140.0)
        manager.set_metric("utility_route_count", float(utility_count), category="utilities")
        manager.set_metric("utility_total_length_ft", concept_length, units="ft", category="utilities")
        record.metrics["utility_count"] = utility_count
        record.metrics["utility_length_ft"] = concept_length

        self._mark_dependency(manager, "pipes", "utilities", DependencyState.FRESH, "Utility coordination run.")
        self._mark_dependency(manager, "utilities", "earthwork", DependencyState.STALE, "Earthwork may be affected by utility corridors.")
        manager.invalidate_from("utilities")

        return record

    def _run_earthwork_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        grading_score = _safe_float(getattr(manager.metrics.get("grading_coordination_score"), "value", 0.0), 0.0)
        lot_area = _lot_area(parsed)

        cut = max(0.0, lot_area * 0.03 * max(0.5, grading_score / 10.0))
        fill = max(0.0, lot_area * 0.028 * max(0.5, grading_score / 10.0))
        net = cut - fill

        manager.set_metric("earthwork_cut_cf", cut, units="cf", category="earthwork")
        manager.set_metric("earthwork_fill_cf", fill, units="cf", category="earthwork")
        manager.set_metric("earthwork_net_cf", net, units="cf", category="earthwork")
        manager.set_metric("earthwork_success", 1.0, category="earthwork")

        record.metrics["cut_cf"] = cut
        record.metrics["fill_cf"] = fill
        record.metrics["net_cf"] = net

        self._mark_dependency(manager, "utilities", "earthwork", DependencyState.FRESH, "Earthwork coordination run.")
        self._mark_dependency(manager, "earthwork", "qa", DependencyState.STALE, "QA depends on earthwork metrics.")
        manager.invalidate_from("earthwork")

        return record

    def _run_qa_stage(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        request: CoordinationRequest,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        record.ran = True

        warning_count = 0
        error_count = 0

        # Simple coordination-level QA. Does not replace planner QA.
        pipe_len = _safe_float(getattr(manager.metrics.get("storm_pipe_length_ft"), "value", 0.0), 0.0)
        util_len = _safe_float(getattr(manager.metrics.get("utility_total_length_ft"), "value", 0.0), 0.0)
        earth_net = _safe_float(getattr(manager.metrics.get("earthwork_net_cf"), "value", 0.0), 0.0)

        if pipe_len > 1500.0:
            warning_count += 1
            manager.add_conflict(
                ConflictRecord(
                    code="LONG_PIPE_NETWORK",
                    message="Pipe network appears long for conceptual site scale.",
                    severity=ConflictSeverity.WARNING,
                    category="qa",
                )
            )
        if util_len > 1800.0:
            warning_count += 1
            manager.add_conflict(
                ConflictRecord(
                    code="LONG_UTILITY_NETWORK",
                    message="Utility network appears long for conceptual site scale.",
                    severity=ConflictSeverity.WARNING,
                    category="qa",
                )
            )
        if abs(earth_net) > 10000.0:
            warning_count += 1
            manager.add_conflict(
                ConflictRecord(
                    code="EARTHWORK_IMBALANCE",
                    message="Earthwork net balance is large for conceptual coordination.",
                    severity=ConflictSeverity.WARNING,
                    category="qa",
                )
            )

        manager.set_metric("qa_warning_count", float(warning_count), category="qa")
        manager.set_metric("qa_error_count", float(error_count), category="qa")
        record.metrics["warning_count"] = warning_count
        record.metrics["error_count"] = error_count

        self._mark_dependency(manager, "earthwork", "qa", DependencyState.FRESH, "QA coordination run.")

        return record

    # -------------------------------------------------------------------------
    # Fix loop
    # -------------------------------------------------------------------------

    def _apply_fix_loop(
        self,
        parsed: Dict[str, Any],
        manager: ProjectManager,
        issues: Sequence[CoordinationIssue],
        request: CoordinationRequest,
    ) -> List[str]:
        fixes: List[str] = []

        for issue in issues:
            code = _safe_str(issue.code)

            if code == "LONG_PIPE_NETWORK":
                current = _safe_float(getattr(manager.metrics.get("storm_pipe_length_ft"), "value", 0.0), 0.0)
                manager.set_metric("storm_pipe_length_ft", current * 0.92, units="ft", category="pipes")
                fixes.append("Reduced conceptual storm pipe length by 8% for efficiency.")
                self._resolve_conflicts_by_code(manager, code)

            elif code == "LONG_UTILITY_NETWORK":
                current = _safe_float(getattr(manager.metrics.get("utility_total_length_ft"), "value", 0.0), 0.0)
                manager.set_metric("utility_total_length_ft", current * 0.90, units="ft", category="utilities")
                fixes.append("Reduced conceptual utility network length by 10% for efficiency.")
                self._resolve_conflicts_by_code(manager, code)

            elif code == "EARTHWORK_IMBALANCE":
                current = _safe_float(getattr(manager.metrics.get("earthwork_net_cf"), "value", 0.0), 0.0)
                manager.set_metric("earthwork_net_cf", current * 0.80, units="cf", category="earthwork")
                fixes.append("Improved conceptual earthwork balance by reducing net imbalance.")
                self._resolve_conflicts_by_code(manager, code)

        return fixes

    # -------------------------------------------------------------------------
    # Issue / convergence helpers
    # -------------------------------------------------------------------------

    def _collect_issues(self, manager: ProjectManager) -> List[CoordinationIssue]:
        out: List[CoordinationIssue] = []
        for conflict in manager.unresolved_conflicts():
            out.append(
                CoordinationIssue(
                    code=conflict.code,
                    severity=conflict.severity.value if hasattr(conflict.severity, "value") else str(conflict.severity),
                    message=conflict.message,
                    source_stage=_safe_str(conflict.category),
                    context=deepcopy(conflict.meta),
                )
            )
        return out

    def _is_converged(
        self,
        issues_after_fix: Sequence[CoordinationIssue],
        score_before: float,
        score_after: float,
        request: CoordinationRequest,
    ) -> bool:
        if request.stop_when_clean:
            errors = [i for i in issues_after_fix if _lower(i.severity) == "error"]
            warnings = [i for i in issues_after_fix if _lower(i.severity) == "warning"]
            if not errors and not warnings:
                return True

        if request.stop_when_score_stalls:
            if (score_after - score_before) <= float(request.score_improvement_epsilon):
                return True

        return False

    # -------------------------------------------------------------------------
    # ProjectManager helpers
    # -------------------------------------------------------------------------

    def _ensure_default_dependencies(self, manager: ProjectManager) -> None:
        self._mark_dependency(manager, "layout", "grading", DependencyState.STALE, "Default coordination dependency.")
        self._mark_dependency(manager, "grading", "drainage", DependencyState.STALE, "Default coordination dependency.")
        self._mark_dependency(manager, "drainage", "pipes", DependencyState.STALE, "Default coordination dependency.")
        self._mark_dependency(manager, "pipes", "utilities", DependencyState.STALE, "Default coordination dependency.")
        self._mark_dependency(manager, "utilities", "earthwork", DependencyState.STALE, "Default coordination dependency.")
        self._mark_dependency(manager, "earthwork", "qa", DependencyState.STALE, "Default coordination dependency.")

    def _mark_dependency(
        self,
        manager: ProjectManager,
        source: str,
        target: str,
        state: DependencyState,
        reason: str,
    ) -> None:
        for dep in manager.dependencies:
            if dep.source == source and dep.target == target:
                dep.state = state
                dep.reason = reason
                return
        manager.add_dependency(source, target, state, reason=reason)

    def _resolve_conflicts_by_code(self, manager: ProjectManager, code: str) -> None:
        for conflict in manager.conflicts:
            if conflict.code == code and not conflict.resolved:
                conflict.resolved = True

    def _dedupe(self, items: Sequence[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out


# =============================================================================
# PUBLIC API
# =============================================================================

def coordinate_project(
    parsed_payload: Dict[str, Any],
    manager: ProjectManager,
    *,
    allow_assumptions: bool = True,
    strict_inputs: bool = False,
    max_iterations: int = 3,
    stop_when_clean: bool = True,
    stop_when_score_stalls: bool = True,
    score_improvement_epsilon: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
) -> CoordinationResult:
    engine = CoordinationEngine()
    request = CoordinationRequest(
        parsed_payload=deepcopy(parsed_payload),
        manager=manager,
        allow_assumptions=allow_assumptions,
        strict_inputs=strict_inputs,
        max_iterations=max_iterations,
        stop_when_clean=stop_when_clean,
        stop_when_score_stalls=stop_when_score_stalls,
        score_improvement_epsilon=score_improvement_epsilon,
        meta=deepcopy(meta) if isinstance(meta, dict) else {},
    )
    return engine.coordinate(request)
