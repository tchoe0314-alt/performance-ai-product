from __future__ import annotations

"""
system_runner.py (FINAL TRUE MAX ALIGNED VERSION)

Purpose
-------
Top-level end-to-end runtime entrypoint for the AI civil / CAD platform.

This version keeps your current system_runner.py as the base and aligns it to:
- the final integration-hardened planner_orchestrator
- the final aligned planner
- the upgraded ProjectManager lifecycle/state layer
- the upgraded pipe backend and planner metrics
- stronger runtime trace/suite/regression behavior

Design rules
------------
- use the planner stack as source of truth
- keep orchestrator as the workflow shell
- keep classifier as front-door routing intelligence
- keep ProjectManager + coordination for lifecycle/fix-loop work
- remove clutter only if it adds no capability
- preserve useful behavior and expand it
"""

from dataclasses import dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import importlib
import importlib.util
import time
import traceback
import uuid


# =============================================================================
# IMPORT HELPERS
# =============================================================================

def _import_module_from_candidates(candidates: Sequence[str], fallback_paths: Sequence[str] = ()) -> Any:
    for name in candidates:
        try:
            return importlib.import_module(name)
        except Exception:
            pass

    for raw_path in fallback_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        module_name = path.stem.replace(".", "_") + "_" + uuid.uuid4().hex[:8]
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    raise ImportError(f"Unable to import any candidate modules: {candidates} / {fallback_paths}")


planner = _import_module_from_candidates(
    ["planner", "project_root.planner"],
    fallback_paths=[
        "/mnt/data/planner.py",
        "/mnt/data/planner_final_true_max_aligned.py",
        "/mnt/data/planner_real_max_integrated_civil_grade.py",
    ],
)

planner_orchestrator = _import_module_from_candidates(
    ["planner_orchestrator", "project_root.planner_orchestrator"],
    fallback_paths=[
        "/mnt/data/planner_orchestrator.py",
        "/mnt/data/planner_orchestrator_final_integration_hardened.py",
        "/mnt/data/planner_orchestrator_true_max_merged_integrated.py",
    ],
)

project_classifier = _import_module_from_candidates(
    ["project_classifier", "project_root.project_classifier"],
    fallback_paths=[
        "/mnt/data/project_classifier.py",
    ],
)

project_manager_mod = _import_module_from_candidates(
    ["core.project_manager", "project_manager", "project_root.project_manager"],
    fallback_paths=[
        "/mnt/data/project_manager.py",
        "/mnt/data/project_manager_real_max_merged_integrated.py",
    ],
)
ProjectManager = getattr(project_manager_mod, "ProjectManager")

try:
    coordination_engine = _import_module_from_candidates(
        ["core.coordination_engine", "coordination_engine", "project_root.coordination_engine"],
        fallback_paths=["/mnt/data/coordination_engine.py"],
    )
    coordinate_project = getattr(coordination_engine, "coordinate_project")
except Exception:
    coordinate_project = None

try:
    config_mod = _import_module_from_candidates(
        ["core.config", "config", "project_root.config"],
        fallback_paths=["/mnt/data/config.py"],
    )
    APP_NAME = getattr(config_mod, "APP_NAME", "Civil AI Assistant")
    APP_VERSION = getattr(config_mod, "APP_VERSION", "0.0.0")
    DEBUG = bool(getattr(config_mod, "DEBUG", True))
    ENABLE_AUTOFIX = bool(getattr(config_mod, "ENABLE_AUTOFIX", True))
    ENABLE_VALIDATION = bool(getattr(config_mod, "ENABLE_VALIDATION", True))
    ENABLE_PIPE_NETWORK = bool(getattr(config_mod, "ENABLE_PIPE_NETWORK", True))
except Exception:
    APP_NAME = "Civil AI Assistant"
    APP_VERSION = "0.0.0"
    DEBUG = True
    ENABLE_AUTOFIX = True
    ENABLE_VALIDATION = True
    ENABLE_PIPE_NETWORK = True

try:
    report_builder = importlib.import_module("report_builder")
except Exception:
    report_builder = None

try:
    session_state_mod = importlib.import_module("session_state")
except Exception:
    session_state_mod = None


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class RunnerExportRecord:
    export_type: str
    path: Optional[str] = None
    success: bool = False
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerRequest:
    prompt_text: Optional[str] = None
    manual_fields: Dict[str, Any] = field(default_factory=dict)
    input_mode: str = "prompt"

    strict_mode: bool = False
    full_design_mode: Optional[bool] = None
    optimize_goal: Optional[str] = None

    use_coordination_engine: bool = True
    allow_assumptions: bool = True
    strict_inputs: bool = False
    max_coordination_iterations: int = 3

    max_candidates: int = 10
    top_k: int = 4
    evolution_rounds: int = 3

    image_path: Optional[str] = None
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None
    pixels_per_unit: Optional[float] = None

    units: str = "ft"
    plan_type_hint: Optional[str] = None

    create_report: bool = True
    persist_session: bool = False
    session_id: Optional[str] = None

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerTrace:
    run_id: str
    timestamp_start: float
    timestamp_end: float
    duration_sec: float
    request_summary: Dict[str, Any] = field(default_factory=dict)
    routing: Dict[str, Any] = field(default_factory=dict)
    workflow: str = ""
    score: float = 0.0
    success: bool = False
    warning_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerResponse:
    success: bool
    message: str

    request: Dict[str, Any] = field(default_factory=dict)
    routing: Dict[str, Any] = field(default_factory=dict)

    design: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    assumptions: List[Dict[str, Any]] = field(default_factory=list)

    analysis: Dict[str, Any] = field(default_factory=dict)
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    exports: List[Dict[str, Any]] = field(default_factory=list)

    session: Dict[str, Any] = field(default_factory=dict)
    trace: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerSuiteCase:
    case_id: str
    title: str
    request: RunnerRequest
    expected_min_score: Optional[float] = None
    expected_max_errors: Optional[int] = None
    expected_workflow: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerSuiteResult:
    success: bool
    title: str
    case_count: int
    results: List[RunnerResponse] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _dedupe_keep_order(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = deepcopy(a) if isinstance(a, dict) else {}
    if not isinstance(b, dict):
        return result
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def _classification_to_dict(result: Any) -> Dict[str, Any]:
    if result is None:
        return {}
    return {
        "mode": getattr(getattr(result, "mode", None), "value", str(getattr(result, "mode", ""))),
        "discipline": getattr(getattr(result, "discipline", None), "value", str(getattr(result, "discipline", ""))),
        "subtasks": [getattr(s, "value", str(s)) for s in getattr(result, "subtasks", []) or []],
        "confidence": getattr(result, "confidence", 0.0),
        "requested_outputs": list(getattr(result, "requested_outputs", []) or []),
        "assumptions": list(getattr(result, "assumptions", []) or []),
        "notes": list(getattr(result, "notes", []) or []),
        "matched_keywords": deepcopy(getattr(result, "matched_keywords", {}) or {}),
    }


def _routing_decision_to_dict(decision: Any) -> Dict[str, Any]:
    if decision is None:
        return {}
    return {
        "mode": getattr(getattr(decision, "mode", None), "value", str(getattr(decision, "mode", ""))),
        "discipline": getattr(getattr(decision, "discipline", None), "value", str(getattr(decision, "discipline", ""))),
        "pipeline": getattr(getattr(decision, "pipeline", None), "value", str(getattr(decision, "pipeline", ""))),
        "engines": list(getattr(decision, "engines", []) or []),
        "workflow": _safe_str(getattr(decision, "workflow", "")),
        "complexity": getattr(getattr(decision, "complexity", None), "value", str(getattr(decision, "complexity", ""))),
        "requires_iterations": bool(getattr(decision, "requires_iterations", False)),
        "use_intelligence_layer": bool(getattr(decision, "use_intelligence_layer", False)),
        "use_full_design_mode": bool(getattr(decision, "use_full_design_mode", False)),
        "prefer_multi_option": bool(getattr(decision, "prefer_multi_option", False)),
        "needs_image_analysis": bool(getattr(decision, "needs_image_analysis", False)),
        "needs_sketch_parser": bool(getattr(decision, "needs_sketch_parser", False)),
        "plan_type_hint": getattr(decision, "plan_type_hint", None),
        "optimize_goal": getattr(decision, "optimize_goal", None),
        "requested_outputs": list(getattr(decision, "requested_outputs", []) or []),
        "assumptions": list(getattr(decision, "assumptions", []) or []),
        "notes": list(getattr(decision, "notes", []) or []),
        "matched_keywords": deepcopy(getattr(decision, "matched_keywords", {}) or {}),
        "metadata": deepcopy(getattr(decision, "metadata", {}) or {}),
    }


def _orchestrator_assumptions_to_dict(items: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "field_name": getattr(item, "field_name", ""),
            "assumed_value": getattr(item, "assumed_value", None),
            "reason": getattr(item, "reason", ""),
        }
        for item in items or []
    ]


def _orchestrator_issues_to_dict(items: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "code": getattr(item, "code", ""),
            "severity": getattr(item, "severity", ""),
            "message": getattr(item, "message", ""),
            "context": deepcopy(getattr(item, "context", {}) or {}),
        }
        for item in items or []
    ]


def _coordination_iterations_to_dict(items: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        out.append({
            "iteration_index": getattr(item, "iteration_index", 0),
            "score_before": getattr(item, "score_before", 0.0),
            "score_after": getattr(item, "score_after", 0.0),
            "converged": bool(getattr(item, "converged", False)),
            "fixes_applied": list(getattr(item, "fixes_applied", []) or []),
            "notes": list(getattr(item, "notes", []) or []),
            "issues_before_fix": [
                {
                    "code": getattr(x, "code", ""),
                    "severity": getattr(x, "severity", ""),
                    "message": getattr(x, "message", ""),
                    "source_stage": getattr(x, "source_stage", ""),
                    "context": deepcopy(getattr(x, "context", {}) or {}),
                }
                for x in getattr(item, "issues_before_fix", []) or []
            ],
            "issues_after_fix": [
                {
                    "code": getattr(x, "code", ""),
                    "severity": getattr(x, "severity", ""),
                    "message": getattr(x, "message", ""),
                    "source_stage": getattr(x, "source_stage", ""),
                    "context": deepcopy(getattr(x, "context", {}) or {}),
                }
                for x in getattr(item, "issues_after_fix", []) or []
            ],
            "stage_records": [
                {
                    "stage_name": getattr(s, "stage_name", ""),
                    "ran": bool(getattr(s, "ran", False)),
                    "success": bool(getattr(s, "success", False)),
                    "skipped": bool(getattr(s, "skipped", False)),
                    "reason": getattr(s, "reason", ""),
                    "warnings": list(getattr(s, "warnings", []) or []),
                    "errors": list(getattr(s, "errors", []) or []),
                    "assumptions": list(getattr(s, "assumptions", []) or []),
                    "metrics": deepcopy(getattr(s, "metrics", {}) or {}),
                    "meta": deepcopy(getattr(s, "meta", {}) or {}),
                }
                for s in getattr(item, "stage_records", []) or []
            ],
        })
    return out


def _manager_metrics_to_dict(manager: ProjectManager) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, rec in manager.metrics.items():
        out[name] = {
            "value": rec.value,
            "units": rec.units,
            "category": rec.category,
            "weight": getattr(rec, "weight", 1.0),
            "meta": deepcopy(getattr(rec, "meta", {}) or {}),
        }
    return out


def _manager_conflicts_to_dict(manager: ProjectManager) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in manager.conflicts:
        sev = c.severity.value if hasattr(c.severity, "value") else str(c.severity)
        out.append({
            "code": c.code,
            "message": c.message,
            "severity": sev,
            "related_ids": list(getattr(c, "related_ids", []) or []),
            "category": getattr(c, "category", ""),
            "resolved": bool(getattr(c, "resolved", False)),
            "meta": deepcopy(getattr(c, "meta", {}) or {}),
        })
    return out


def _make_project_manager(final_plan: Dict[str, Any]) -> ProjectManager:
    project_cls = getattr(planner, "ProjectModel")
    project = project_cls(
        name=_safe_str(final_plan.get("project_name"), "Generated Plan"),
        units=_safe_str(final_plan.get("units"), "ft"),
    )
    return ProjectManager(project)


def _build_trace_metadata(response: RunnerResponse) -> Dict[str, Any]:
    return {
        "issue_count": len(response.issues),
        "export_count": len(response.exports),
        "alternative_count": len(_safe_list(_safe_dict(response.design).get("alternatives"))),
        "iteration_count": len(response.iterations),
        "planner_score": _safe_float(_safe_dict(response.metrics).get("planner_score"), 0.0),
        "manager_score": _safe_float(_safe_dict(response.metrics).get("manager_score"), 0.0),
    }


# =============================================================================
# RUNNER
# =============================================================================

class SystemRunner:
    """
    Product-level backend runner and runtime diagnostics shell.

    Expanded capabilities:
    - request classification and workflow routing
    - orchestrator execution
    - optional coordination hardening
    - report/export/session integration
    - run history
    - suite execution
    - regression-style comparison summaries
    """

    def __init__(self) -> None:
        self.history: List[RunnerTrace] = []

    def run(self, req: RunnerRequest) -> RunnerResponse:
        t0 = time.time()

        request_summary = {
            "input_mode": req.input_mode,
            "strict_mode": req.strict_mode,
            "full_design_mode": req.full_design_mode,
            "optimize_goal": req.optimize_goal,
            "use_coordination_engine": req.use_coordination_engine,
            "allow_assumptions": req.allow_assumptions,
            "strict_inputs": req.strict_inputs,
            "max_coordination_iterations": req.max_coordination_iterations,
            "max_candidates": req.max_candidates,
            "top_k": req.top_k,
            "evolution_rounds": req.evolution_rounds,
            "units": req.units,
            "plan_type_hint": req.plan_type_hint,
            "create_report": req.create_report,
            "persist_session": req.persist_session,
        }

        try:
            raw_text = self._build_classification_text(req)
            classification = project_classifier.classify_request(raw_text)
            routing = project_classifier.classify_and_route_request(raw_text)

            orchestrator_req = self._build_orchestrator_request(req, routing)
            orchestrator_result = planner_orchestrator.orchestrate_plan(orchestrator_req)

            final_plan = deepcopy(orchestrator_result.final_plan)
            manager = _make_project_manager(final_plan)
            self._seed_manager_from_plan(manager, final_plan)

            coordination_result = None
            should_coordinate = (
                req.use_coordination_engine and
                coordinate_project is not None and
                _safe_bool(getattr(routing, "requires_iterations", False), False)
            )
            if should_coordinate:
                coordination_result = coordinate_project(
                    parsed_payload=deepcopy(orchestrator_result.parsed_payload),
                    manager=manager,
                    allow_assumptions=req.allow_assumptions,
                    strict_inputs=req.strict_inputs,
                    max_iterations=max(1, int(req.max_coordination_iterations)),
                    stop_when_clean=True,
                    stop_when_score_stalls=True,
                    score_improvement_epsilon=1.0,
                    meta={
                        "routing": _routing_decision_to_dict(routing),
                        "source": "system_runner",
                    },
                )

            report_payload = self._build_report_payload(
                final_plan=final_plan,
                orchestrator_result=orchestrator_result,
                manager=manager,
                coordination_result=coordination_result,
                req=req,
            )
            exports = self._build_exports(report_payload, req)
            session_payload = self._build_session_payload(final_plan, orchestrator_result, routing, req)

            response = RunnerResponse(
                success=bool(orchestrator_result.success),
                message=_safe_str(orchestrator_result.message, "System runner completed."),
                request=request_summary,
                routing={
                    "classification": _classification_to_dict(classification),
                    "decision": _routing_decision_to_dict(routing),
                },
                design={
                    "main_plan": deepcopy(final_plan),
                    "alternatives": deepcopy(getattr(orchestrator_result, "alternatives", []) or []),
                    "option_summaries": deepcopy([getattr(x, "__dict__", x) for x in getattr(orchestrator_result, "option_summaries", []) or []]),
                    "preview": deepcopy(self._build_preview_payload(final_plan)),
                },
                metrics={
                    "planner_score": _safe_float(_safe_dict(_safe_dict(final_plan.get("meta")).get("planner_score")).get("total"), 0.0),
                    "planner_weighted_components": deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("planner_score")).get("weighted_components", {})),
                    "manager_score": manager.aggregate_score() if hasattr(manager, "aggregate_score") else 0.0,
                    "manager_score_by_category": manager.aggregate_score_by_category() if hasattr(manager, "aggregate_score_by_category") else {},
                    "manager_metrics": _manager_metrics_to_dict(manager),
                    "conflict_counts": manager.conflict_counts() if hasattr(manager, "conflict_counts") else {},
                },
                issues=_orchestrator_issues_to_dict(getattr(orchestrator_result, "issues", []) or []),
                warnings=_dedupe_keep_order(list(getattr(orchestrator_result, "warnings", []) or []) + (list(getattr(coordination_result, "warnings", []) or []) if coordination_result else [])),
                errors=_dedupe_keep_order(list(getattr(orchestrator_result, "errors", []) or []) + (list(getattr(coordination_result, "errors", []) or []) if coordination_result else [])),
                assumptions=_orchestrator_assumptions_to_dict(getattr(orchestrator_result, "assumptions", []) or []) + (
                    [{"field_name": "coordination", "assumed_value": a, "reason": "Coordination engine assumption"} for a in (getattr(coordination_result, "assumptions", []) or [])]
                    if coordination_result else []
                ),
                analysis={
                    "explanation": deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("explanation"))),
                    "report": deepcopy(report_payload),
                    "manager_conflicts": _manager_conflicts_to_dict(manager),
                    "orchestrator_metadata": deepcopy(getattr(orchestrator_result, "metadata", {}) or {}),
                    "coordination_metadata": deepcopy(getattr(coordination_result, "metadata", {}) or {}) if coordination_result else {},
                    "manager_export": deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("manager_export"))),
                    "planner_project_manager_meta": deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("project_manager"))),
                },
                iterations=_coordination_iterations_to_dict(getattr(coordination_result, "iterations", []) if coordination_result else []),
                exports=[{
                    "export_type": e.export_type,
                    "path": e.path,
                    "success": e.success,
                    "message": e.message,
                    "metadata": deepcopy(e.metadata),
                } for e in exports],
                session=session_payload,
                metadata={
                    "app_name": APP_NAME,
                    "app_version": APP_VERSION,
                    "debug": DEBUG,
                    "feature_flags": {
                        "enable_autofix": ENABLE_AUTOFIX,
                        "enable_validation": ENABLE_VALIDATION,
                        "enable_pipe_network": ENABLE_PIPE_NETWORK,
                        "coordination_enabled": should_coordinate,
                    },
                },
            )

            t1 = time.time()
            trace = RunnerTrace(
                run_id=str(uuid.uuid4()),
                timestamp_start=t0,
                timestamp_end=t1,
                duration_sec=round(t1 - t0, 4),
                request_summary=deepcopy(request_summary),
                routing=deepcopy(response.routing),
                workflow=_safe_str(_safe_dict(getattr(orchestrator_result, "metadata", {})).get("workflow")),
                score=_safe_float(_safe_dict(response.metrics).get("planner_score"), 0.0),
                success=response.success,
                warning_count=len(response.warnings),
                error_count=len(response.errors),
                metadata=_build_trace_metadata(response),
            )
            self.history.append(trace)
            response.trace = deepcopy(trace.__dict__)
            return response

        except Exception as exc:
            t1 = time.time()
            trace = RunnerTrace(
                run_id=str(uuid.uuid4()),
                timestamp_start=t0,
                timestamp_end=t1,
                duration_sec=round(t1 - t0, 4),
                request_summary=deepcopy(request_summary),
                routing={},
                workflow="failed",
                score=0.0,
                success=False,
                warning_count=0,
                error_count=1,
                metadata={},
            )
            self.history.append(trace)
            return RunnerResponse(
                success=False,
                message=f"System runner failed: {exc}",
                request=request_summary,
                errors=[str(exc)],
                trace=deepcopy(trace.__dict__),
                metadata={"traceback": traceback.format_exc() if DEBUG else ""},
            )

    # ------------------------------------------------------------------
    # Request shaping
    # ------------------------------------------------------------------

    def _build_classification_text(self, req: RunnerRequest) -> str:
        if req.prompt_text:
            return req.prompt_text
        if req.manual_fields:
            return str(req.manual_fields)
        return "design a site"

    def _build_orchestrator_request(self, req: RunnerRequest, routing: Any) -> Any:
        full_design_mode = req.full_design_mode
        if full_design_mode is None:
            full_design_mode = bool(getattr(routing, "use_full_design_mode", False))

        optimize_goal = req.optimize_goal or getattr(routing, "optimize_goal", None)
        plan_type_hint = req.plan_type_hint or getattr(routing, "plan_type_hint", None)

        return planner_orchestrator.PlannerOrchestratorRequest(
            input_mode=req.input_mode,
            strict_mode=req.strict_mode,
            full_design_mode=bool(full_design_mode),
            prompt_text=req.prompt_text,
            manual_fields=deepcopy(req.manual_fields),
            image_path=req.image_path,
            image_width_px=req.image_width_px,
            image_height_px=req.image_height_px,
            pixels_per_unit=req.pixels_per_unit,
            plan_type_hint=plan_type_hint,
            units=req.units,
            max_candidates=max(1, int(req.max_candidates)),
            top_k=max(1, int(req.top_k)),
            evolution_rounds=max(1, int(req.evolution_rounds)),
            optimize_goal=optimize_goal,
            meta=_deep_merge(
                deepcopy(req.meta),
                {
                    "workflow": getattr(getattr(routing, "pipeline", None), "value", str(getattr(routing, "pipeline", ""))),
                    "goal": optimize_goal,
                    "routing": _routing_decision_to_dict(routing),
                },
            ),
        )

    # ------------------------------------------------------------------
    # Manager seeding / coordination
    # ------------------------------------------------------------------

    def _seed_manager_from_plan(self, manager: ProjectManager, final_plan: Dict[str, Any]) -> None:
        meta = _safe_dict(final_plan.get("meta"))
        planner_score = _safe_dict(meta.get("planner_score"))
        qa = _safe_dict(meta.get("qa"))
        pm_meta = _safe_dict(meta.get("project_manager"))
        pm_metrics = _safe_dict(pm_meta.get("metrics"))
        manager_export = _safe_dict(meta.get("manager_export"))
        manager_export_metrics = _safe_dict(manager_export.get("metrics"))

        if "total" in planner_score:
            manager.set_metric("planner_score_total", _safe_float(planner_score.get("total"), 0.0), category="planner", weight=1.0)

        if "warning_count" in qa:
            manager.set_metric("qa_warning_count_seed", _safe_float(qa.get("warning_count"), 0.0), category="qa", weight=1.0)
        if "error_count" in qa:
            manager.set_metric("qa_error_count_seed", _safe_float(qa.get("error_count"), 0.0), category="qa", weight=2.0)

        for name, value in pm_metrics.items():
            if isinstance(value, (int, float)):
                manager.set_metric(name, value, category="planner_seed", weight=1.0)

        for name, metric_block in manager_export_metrics.items():
            metric_block = _safe_dict(metric_block)
            value = metric_block.get("value")
            if isinstance(value, (int, float)):
                manager.set_metric(
                    name,
                    value,
                    units=_safe_str(metric_block.get("units")),
                    category=_safe_str(metric_block.get("category"), "planner_export"),
                    weight=_safe_float(metric_block.get("weight"), 1.0),
                    **_safe_dict(metric_block.get("meta")),
                )

    # ------------------------------------------------------------------
    # Reporting / exports / session
    # ------------------------------------------------------------------

    def _build_report_payload(
        self,
        *,
        final_plan: Dict[str, Any],
        orchestrator_result: Any,
        manager: "ProjectManager",
        coordination_result: Any,
        req: RunnerRequest,
    ) -> Dict[str, Any]:
        if report_builder is not None and hasattr(report_builder, "build_report"):
            try:
                return report_builder.build_report(
                    final_plan=deepcopy(final_plan),
                    orchestrator_metadata=deepcopy(getattr(orchestrator_result, "metadata", {}) or {}),
                    manager_metrics=_manager_metrics_to_dict(manager),
                    manager_conflicts=_manager_conflicts_to_dict(manager),
                    coordination_metadata=deepcopy(getattr(coordination_result, "metadata", {}) or {}) if coordination_result else {},
                )
            except Exception:
                pass

        return {
            "summary": {
                "project_name": _safe_str(final_plan.get("project_name"), "Generated Plan"),
                "units": _safe_str(final_plan.get("units"), "ft"),
                "score": _safe_float(_safe_dict(_safe_dict(final_plan.get("meta")).get("planner_score")).get("total"), 0.0),
                "warning_count": len(getattr(orchestrator_result, "warnings", []) or []),
                "error_count": len(getattr(orchestrator_result, "errors", []) or []),
            },
            "engineering": {
                "manager_score": manager.aggregate_score() if hasattr(manager, "aggregate_score") else 0.0,
                "manager_score_by_category": manager.aggregate_score_by_category() if hasattr(manager, "aggregate_score_by_category") else {},
                "manager_metrics": _manager_metrics_to_dict(manager),
                "manager_conflicts": _manager_conflicts_to_dict(manager),
            },
            "coordination": deepcopy(getattr(coordination_result, "metadata", {}) or {}) if coordination_result else {},
            "alternatives": deepcopy(getattr(orchestrator_result, "alternatives", []) or []),
        }

    def _build_exports(self, report_payload: Dict[str, Any], req: RunnerRequest) -> List[RunnerExportRecord]:
        exports: List[RunnerExportRecord] = []
        if req.create_report:
            exports.append(
                RunnerExportRecord(
                    export_type="report_payload",
                    path=None,
                    success=True,
                    message="Built in-memory report payload.",
                    metadata={"keys": list(report_payload.keys())},
                )
            )
        return exports

    def _build_session_payload(self, final_plan: Dict[str, Any], orchestrator_result: Any, routing: Any, req: RunnerRequest) -> Dict[str, Any]:
        payload = {
            "session_id": req.session_id,
            "persisted": False,
            "state_available": session_state_mod is not None,
        }
        if not req.persist_session or session_state_mod is None:
            return payload

        try:
            if hasattr(session_state_mod, "save_session_state"):
                save_result = session_state_mod.save_session_state(
                    session_id=req.session_id,
                    final_plan=deepcopy(final_plan),
                    alternatives=deepcopy(getattr(orchestrator_result, "alternatives", []) or []),
                    routing=_routing_decision_to_dict(routing),
                    metadata=deepcopy(getattr(orchestrator_result, "metadata", {}) or {}),
                )
                payload["persisted"] = True
                payload["save_result"] = save_result
        except Exception as exc:
            payload["persisted"] = False
            payload["error"] = str(exc)
        return payload

    # ------------------------------------------------------------------
    # Preview / diagnostics
    # ------------------------------------------------------------------

    def _build_preview_payload(self, final_plan: Dict[str, Any]) -> Dict[str, Any]:
        actions = _safe_list(final_plan.get("actions"))
        layers: Dict[str, int] = {}
        for action in actions:
            layer = _safe_str(_safe_dict(action).get("layer"), "SITE")
            layers[layer] = layers.get(layer, 0) + 1

        return {
            "project_name": _safe_str(final_plan.get("project_name"), "Generated Plan"),
            "action_count": len(actions),
            "layers": layers,
        }

    # ------------------------------------------------------------------
    # History / suite / regression helpers
    # ------------------------------------------------------------------

    def history_summary(self) -> Dict[str, Any]:
        return {
            "run_count": len(self.history),
            "best_score": max([x.score for x in self.history], default=0.0),
            "avg_score": (sum(x.score for x in self.history) / len(self.history)) if self.history else 0.0,
            "success_count": sum(1 for x in self.history if x.success),
            "failure_count": sum(1 for x in self.history if not x.success),
            "avg_duration_sec": (sum(x.duration_sec for x in self.history) / len(self.history)) if self.history else 0.0,
        }

    def compare_history(self) -> List[Dict[str, Any]]:
        rows = [deepcopy(x.__dict__) for x in self.history]
        rows.sort(key=lambda r: (r.get("success", False), r.get("score", 0.0)), reverse=True)
        return rows

    def run_suite(self, title: str, cases: Sequence[RunnerSuiteCase]) -> RunnerSuiteResult:
        results: List[RunnerResponse] = []
        failing_case_count = 0
        for case in cases:
            resp = self.run(case.request)
            results.append(resp)
            if not resp.success:
                failing_case_count += 1
                continue
            if case.expected_min_score is not None and _safe_float(_safe_dict(resp.metrics).get("planner_score"), 0.0) < case.expected_min_score:
                failing_case_count += 1
            if case.expected_max_errors is not None and len(resp.errors) > case.expected_max_errors:
                failing_case_count += 1
            if case.expected_workflow is not None and _safe_str(_safe_dict(resp.trace).get("workflow")) != case.expected_workflow:
                failing_case_count += 1

        summary = {
            "title": title,
            "case_count": len(cases),
            "failing_case_count": failing_case_count,
            "passing_case_count": max(0, len(cases) - failing_case_count),
            "history_summary": self.history_summary(),
        }
        return RunnerSuiteResult(
            success=failing_case_count == 0,
            title=title,
            case_count=len(cases),
            results=results,
            summary=summary,
        )


# =============================================================================
# PUBLIC API
# =============================================================================

def run_system(
    prompt_text: Optional[str] = None,
    *,
    manual_fields: Optional[Dict[str, Any]] = None,
    input_mode: str = "prompt",
    strict_mode: bool = False,
    full_design_mode: Optional[bool] = None,
    optimize_goal: Optional[str] = None,
    use_coordination_engine: bool = True,
    allow_assumptions: bool = True,
    strict_inputs: bool = False,
    max_coordination_iterations: int = 3,
    max_candidates: int = 10,
    top_k: int = 4,
    evolution_rounds: int = 3,
    image_path: Optional[str] = None,
    image_width_px: Optional[int] = None,
    image_height_px: Optional[int] = None,
    pixels_per_unit: Optional[float] = None,
    units: str = "ft",
    plan_type_hint: Optional[str] = None,
    create_report: bool = True,
    persist_session: bool = False,
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> RunnerResponse:
    runner = SystemRunner()
    req = RunnerRequest(
        prompt_text=prompt_text,
        manual_fields=deepcopy(manual_fields) if isinstance(manual_fields, dict) else {},
        input_mode=input_mode,
        strict_mode=strict_mode,
        full_design_mode=full_design_mode,
        optimize_goal=optimize_goal,
        use_coordination_engine=use_coordination_engine,
        allow_assumptions=allow_assumptions,
        strict_inputs=strict_inputs,
        max_coordination_iterations=max_coordination_iterations,
        max_candidates=max_candidates,
        top_k=top_k,
        evolution_rounds=evolution_rounds,
        image_path=image_path,
        image_width_px=image_width_px,
        image_height_px=image_height_px,
        pixels_per_unit=pixels_per_unit,
        units=units,
        plan_type_hint=plan_type_hint,
        create_report=create_report,
        persist_session=persist_session,
        session_id=session_id,
        meta=deepcopy(meta) if isinstance(meta, dict) else {},
    )
    return runner.run(req)
