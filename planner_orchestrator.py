
from __future__ import annotations

"""
planner_orchestrator.py (FINAL INTEGRATION HARDENED TRUE MAX VERSION)

Purpose
-------
Top-level workflow shell for the AI civil / CAD / infrastructure platform.

This file keeps the current orchestrator as the base and hardens the final
integration behavior across:
- planner.py as the execution brain
- planner_intelligence.py as the candidate / scoring / refinement layer
- project_manager.py / planner metadata as the state/score/conflict source
- system_runner.py as the runtime / test harness layer

Key hardening upgrades
----------------------
- preserve strict single-plan and assisted multi-option flows
- preserve full-design iterative orchestration
- add stronger conflict/fix/rerun adjustment logic between iterations
- add planner/QA/score-aware stop logic
- add richer option summaries / trace payloads
- add final consistency packaging for runner/UI readiness
- keep planner as execution truth and orchestrator as workflow shell
"""

from dataclasses import dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import importlib
import importlib.util
import math
import re
import uuid


# =============================================================================
# OPTION 2 / FIELD-INTENT HELPERS
# =============================================================================

FIELD_SOURCE_USER = "user"
FIELD_SOURCE_INFER = "infer"
FIELD_SOURCE_OMIT = "omit"
FIELD_SOURCES = {FIELD_SOURCE_USER, FIELD_SOURCE_INFER, FIELD_SOURCE_OMIT}


def _is_field_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and "source" in value and "value" in value


def _field_source(value: Any, default: str = FIELD_SOURCE_INFER) -> str:
    if _is_field_wrapper(value) and value.get("source") in FIELD_SOURCES:
        return value.get("source")
    return default


def _field_value(value: Any, default: Any = None) -> Any:
    if _is_field_wrapper(value):
        if value.get("source") == FIELD_SOURCE_OMIT:
            return None
        return deepcopy(value.get("value", default))
    return deepcopy(value if value is not None else default)


def _field_is_omitted(value: Any) -> bool:
    return _field_source(value) == FIELD_SOURCE_OMIT


def _wrap_field(value: Any, source: str = FIELD_SOURCE_INFER, assumption: str | None = None, confidence: float | None = None) -> Dict[str, Any]:
    return {"value": deepcopy(value), "source": source, "assumption": assumption, "confidence": confidence}


def _resolve_value(value: Any, default: Any = None, *, allow_infer: bool = True) -> Any:
    if not _is_field_wrapper(value):
        return deepcopy(value if value is not None else default)
    src = _field_source(value)
    if src == FIELD_SOURCE_OMIT:
        return None
    if src == FIELD_SOURCE_USER:
        return deepcopy(value.get("value", default))
    if src == FIELD_SOURCE_INFER:
        if allow_infer:
            return deepcopy(value.get("value", default))
        return None
    return deepcopy(default)


def _deep_merge_field_aware(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if key not in out:
            out[key] = deepcopy(value)
            continue
        current = out[key]
        if _field_is_omitted(current):
            continue
        if isinstance(current, dict) and isinstance(value, dict) and not _is_field_wrapper(current) and not _is_field_wrapper(value):
            out[key] = _deep_merge_field_aware(current, value)
            continue
        if _is_field_wrapper(current) and _field_is_omitted(current):
            continue
        out[key] = deepcopy(value)
    return out


def _extract_field_states(payload: Any, prefix: str = "") -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    if prefix == "meta.field_states" or prefix.startswith("meta.field_states."):
        return states
    if _is_field_wrapper(payload):
        states[prefix] = deepcopy(payload)
        return states
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else key
            states.update(_extract_field_states(value, path))
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            states.update(_extract_field_states(value, path))
    return states


def _preserve_field_intent(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload.setdefault("meta", {})
    field_states = dict(payload["meta"].get("field_states") or {})
    field_states.update(_extract_field_states(payload))
    payload["meta"]["field_states"] = field_states
    payload["meta"]["field_contract_version"] = payload["meta"].get("field_contract_version") or "option2_v1"
    return payload


# =============================================================================
# OPTIONAL INPUT SOURCES
# =============================================================================

try:
    from parsers.ai_parser import command_mode
except Exception:  # pragma: no cover
    command_mode = None

try:
    from parsers.sketch_parser import SketchInput, SketchParser
except Exception:  # pragma: no cover
    SketchInput = None
    SketchParser = None

try:
    from vision.image_analysis_engine import ImageAnalysisEngine, ImageAnalysisInput
except Exception:  # pragma: no cover
    ImageAnalysisEngine = None
    ImageAnalysisInput = None


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
        module_name = path.stem.replace(".", "_")
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
        "/mnt/data/planner_real_max_integrated_civil_grade.py",
    ],
)

planner_intelligence = _import_module_from_candidates(
    ["planner_intelligence", "planner.intelligence", "project_root.planner_intelligence"],
    fallback_paths=[
        "/mnt/data/planner_intelligence.py",
        "/mnt/data/planner.intelligence.py",
        "/mnt/data/planner_intelligence_true_max_merged_civil_grade.py",
    ],
)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class PlannerIssue:
    code: str
    severity: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerAssumption:
    field_name: str
    assumed_value: Any
    reason: str


@dataclass
class PlannerOptionSummary:
    option_name: str
    option_family: str = ""
    score: float = 0.0
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    candidate_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignLoopIteration:
    iteration_index: int
    workflow: str
    success: bool
    message: str
    recommended_option_name: Optional[str] = None
    recommended_candidate_id: Optional[str] = None
    recommended_score: float = 0.0
    warning_count: int = 0
    error_count: int = 0
    issue_count: int = 0
    changes_applied: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignLoopState:
    best_score: float = float("-inf")
    best_plan: Dict[str, Any] = field(default_factory=dict)
    best_parsed_payload: Dict[str, Any] = field(default_factory=dict)
    best_result_metadata: Dict[str, Any] = field(default_factory=dict)
    best_option_name: Optional[str] = None
    best_candidate_id: Optional[str] = None
    improvement_history: List[float] = field(default_factory=list)
    iterations: List[DesignLoopIteration] = field(default_factory=list)

    def improved(self, score: float) -> bool:
        return score > self.best_score

    def record_score(self, score: float) -> None:
        self.improvement_history.append(score)


@dataclass
class PlannerOrchestratorRequest:
    input_mode: str = "assisted"
    strict_mode: bool = False

    # high-level workflow controls
    full_design_mode: bool = False
    optimize_goal: Optional[str] = None
    global_iteration_limit: int = 3
    stop_when_clean: bool = True
    stop_when_score_stalls: bool = True
    score_improvement_epsilon: float = 1.0

    # source inputs
    prompt_text: Optional[str] = None
    image_path: Optional[str] = None
    manual_fields: Dict[str, Any] = field(default_factory=dict)

    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None
    pixels_per_unit: Optional[float] = None

    plan_type_hint: Optional[str] = None
    units: str = "ft"

    allow_ai_fill_for_blanks: bool = True
    persist_trace_metadata: bool = True

    max_candidates: int = 10
    top_k: int = 4
    evolution_rounds: int = 3

    meta: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Callable[..., None]] = None


@dataclass
class PlannerOrchestratorResult:
    success: bool
    message: str

    parsed_payload: Dict[str, Any] = field(default_factory=dict)
    final_plan: Dict[str, Any] = field(default_factory=dict)

    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    option_summaries: List[PlannerOptionSummary] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    issues: List[PlannerIssue] = field(default_factory=list)
    assumptions: List[PlannerAssumption] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    return _deep_merge_field_aware(base, override)


def _manual_numeric_is_blank(path: str, value: Any) -> bool:
    if value is None:
        return True
    try:
        numeric = float(value)
    except Exception:
        return False
    blank_numeric_paths = {
        "setback",
        "building_width",
        "building_depth",
        "site_plan.parking_count",
        "lot.w",
        "lot.h",
    }
    return path in blank_numeric_paths and numeric <= 0.0


def _sanitize_manual_fill_value(path: str, value: Any, allow_fill_for_blanks: bool) -> Any:
    if not allow_fill_for_blanks:
        return deepcopy(value)
    if _is_field_wrapper(value):
        return deepcopy(value)
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, nested in value.items():
            nested_path = f"{path}.{key}" if path else key
            cleaned = _sanitize_manual_fill_value(nested_path, nested, allow_fill_for_blanks)
            if cleaned is None:
                continue
            sanitized[key] = cleaned
        if path == "lot":
            width = _safe_float(sanitized.get("w"), 0.0)
            height = _safe_float(sanitized.get("h"), 0.0)
            if width <= 0.0 or height <= 0.0:
                return None
        if path == "site_plan" and not sanitized:
            return None
        return sanitized or None
    if isinstance(value, list):
        cleaned_items = [deepcopy(item) for item in value if item not in (None, "", [], {})]
        return cleaned_items or None
    if value in (None, "", [], {}):
        return None
    if _manual_numeric_is_blank(path, value):
        return None
    return deepcopy(value)


def _merge_manual_fields(parsed: Dict[str, Any], manual_fields: Dict[str, Any], allow_fill_for_blanks: bool = True) -> Dict[str, Any]:
    out = deepcopy(parsed)
    manual_fields = _safe_dict(manual_fields)
    if allow_fill_for_blanks:
        manual_fields = _safe_dict(_sanitize_manual_fill_value("", manual_fields, allow_fill_for_blanks))

    def _looks_like_field_wrapper(value: Any) -> bool:
        return isinstance(value, dict) and "source" in value and "value" in value

    for key, value in manual_fields.items():
        if key not in out:
            out[key] = deepcopy(value)
            continue

        if _field_is_omitted(out.get(key)):
            continue

        if isinstance(out[key], dict) and isinstance(value, dict) and not _is_field_wrapper(out[key]) and not _is_field_wrapper(value):
            out[key] = _deep_merge(out[key], value)
            continue

        current = out[key]
        if allow_fill_for_blanks and current in (None, "", [], {}):
            out[key] = deepcopy(value)
            continue

        if _is_field_wrapper(current):
            src = _field_source(current)
            if src == FIELD_SOURCE_INFER:
                out[key] = deepcopy(value)

    return _preserve_field_intent(out)


def _unwrap_manual_fields_payload(manual_fields: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    payload = _safe_dict(deepcopy(manual_fields))
    nested = _safe_dict(payload.get("manual_fields"))
    if not nested:
        return payload, {}

    control_keys = {
        "manual_fields",
        "strict_mode",
        "full_design_mode",
        "optimize_goal",
        "plan_type_hint",
        "units",
        "meta",
        "input_mode",
    }
    wrapper_extras = {key: deepcopy(value) for key, value in payload.items() if key not in control_keys}
    merged = deepcopy(nested)
    for key, value in wrapper_extras.items():
        merged.setdefault(key, value)
    if isinstance(payload.get("meta"), dict):
        merged.setdefault("meta", {})
        merged["meta"] = _deep_merge(_safe_dict(merged.get("meta")), _safe_dict(payload.get("meta")))
    return merged, payload


def _normalize_with_planner(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _preserve_field_intent(deepcopy(payload))
    if hasattr(planner, "triple_check_parsed_payload"):
        return planner.triple_check_parsed_payload(payload)
    return payload


def _collect_assumptions(parsed_payload: Dict[str, Any], final_plan: Dict[str, Any]) -> List[PlannerAssumption]:
    assumptions: List[PlannerAssumption] = []

    for path, field in _safe_dict(_safe_dict(parsed_payload.get("meta")).get("field_states")).items():
        if isinstance(field, dict) and field.get("source") == FIELD_SOURCE_INFER and field.get("assumption"):
            assumptions.append(PlannerAssumption(field_name=path, assumed_value=deepcopy(field.get("value")), reason=_safe_str(field.get("assumption"))))

    for note in _safe_list(parsed_payload.get("_planner_review_notes")):
        assumptions.append(
            PlannerAssumption(
                field_name="payload",
                assumed_value=note,
                reason="Planner normalization / review note",
            )
        )

    for note in _safe_list(final_plan.get("assumptions")):
        assumptions.append(
            PlannerAssumption(
                field_name="plan",
                assumed_value=note,
                reason="Planner execution assumption",
            )
        )

    return assumptions


def _collect_issues(final_plan: Dict[str, Any]) -> List[PlannerIssue]:
    issues: List[PlannerIssue] = []
    qa = _safe_dict(_safe_dict(final_plan.get("meta")).get("qa"))

    for issue in _safe_list(qa.get("issues")):
        issues.append(
            PlannerIssue(
                code=_safe_str(_safe_dict(issue).get("code"), "ISSUE"),
                severity=_safe_str(_safe_dict(issue).get("severity"), "warning"),
                message=_safe_str(_safe_dict(issue).get("message"), "Issue"),
                context=deepcopy(_safe_dict(_safe_dict(issue).get("context"))),
            )
        )

    return issues


def _collect_warnings_errors(final_plan: Dict[str, Any]) -> tuple[List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []

    for issue in _collect_issues(final_plan):
        if _lower(issue.severity) == "error":
            errors.append(issue.message)
        elif _lower(issue.severity) == "warning":
            warnings.append(issue.message)

    meta = _safe_dict(final_plan.get("meta"))
    for item in _safe_list(meta.get("warnings")):
        warnings.append(_safe_str(item))
    for item in _safe_list(meta.get("errors")):
        errors.append(_safe_str(item))

    return list(dict.fromkeys([w for w in warnings if w])), list(dict.fromkeys([e for e in errors if e]))


def _planner_score_from_plan(final_plan: Dict[str, Any]) -> float:
    meta = _safe_dict(final_plan.get("meta"))
    score_block = _safe_dict(meta.get("planner_score"))
    if "total" in score_block:
        return _safe_float(score_block.get("total"), 0.0)
    return 0.0


def _manual_plan_failed(final_plan: Dict[str, Any]) -> bool:
    meta = _safe_dict(final_plan.get("meta"))
    engineering_status = _safe_dict(meta.get("engineering_status"))
    manual_validation = _safe_dict(meta.get("manual_validation"))
    if _lower(engineering_status.get("mode")) == "manual" and _lower(engineering_status.get("status")) == "failed":
        return True
    return bool(manual_validation.get("failed"))


def _missing_requirements_from_plan(final_plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(final_plan.get("meta"))
    manual_validation = _safe_dict(meta.get("manual_validation"))
    failures = [item for item in _safe_list(manual_validation.get("failures")) if isinstance(item, dict)]
    missing_fields: List[str] = []
    why_needed: Dict[str, str] = {}
    suggested_next_actions: List[str] = []

    for failure in failures:
        field = (
            _safe_str(failure.get("system"))
            or _safe_str(failure.get("rule"))
            or _safe_str(failure.get("missing_computation"))
            or _safe_str(failure.get("code"))
        )
        field = field.replace("_gate", "").replace("_", " ").strip() or "required engineering input"
        message = _safe_str(failure.get("message"), "Required engineering information is missing.")
        if field not in missing_fields:
            missing_fields.append(field)
            why_needed[field] = message
            suggested_next_actions.append(f"Provide {field}, or turn on Assisted so Civora can infer a clearly labeled assumption.")

    if not missing_fields:
        missing_fields = ["site boundary", "grading source", "drainage outlet"]
        why_needed = {
            "site boundary": "Civora needs a locked site boundary to size and locate the design.",
            "grading source": "Civora needs survey, terrain, or an assisted assumption before grading/drainage can be completed.",
            "drainage outlet": "Civora needs a basin or outfall target before drainage can be completed.",
        }
        suggested_next_actions = [
            "Lock the site boundary.",
            "Provide survey/terrain context or turn on Assisted.",
            "Add a basin/outfall or turn on Assisted.",
        ]

    return {
        "missing_fields": missing_fields,
        "why_needed": why_needed,
        "suggested_next_actions": suggested_next_actions,
        "can_assist_if_enabled": True,
    }


def _friendly_missing_requirements_message(missing: Dict[str, Any]) -> str:
    fields = [_safe_str(item) for item in _safe_list(missing.get("missing_fields")) if _safe_str(item)]
    if not fields:
        fields = ["site boundary", "grading source", "drainage outlet"]
    return (
        f"Civora needs {', '.join(fields[:3])} before it can complete this step. "
        "Add those details, or turn on Assisted to let Civora infer reasonable, clearly labeled assumptions."
    )


def _candidate_to_alt(option: Any) -> Dict[str, Any]:
    return {
        "candidate_id": getattr(option, "candidate_id", None),
        "option_name": getattr(option, "option_name", ""),
        "option_family": getattr(option, "option_family", ""),
        "score": getattr(getattr(option, "score", None), "total", 0.0),
        "pros": list(getattr(option, "pros", []) or []),
        "cons": list(getattr(option, "cons", []) or []),
        "metadata": {
            "strategy": deepcopy(getattr(option, "strategy", {}) or {}),
            "lineage": deepcopy(getattr(getattr(option, "lineage", None), "__dict__", {}) or {}),
            "conflict_count": len(getattr(option, "conflicts", []) or []),
            "refinement_count": len(getattr(option, "refinements", []) or []),
        },
    }


def _candidate_to_summary(option: Any) -> PlannerOptionSummary:
    return PlannerOptionSummary(
        option_name=getattr(option, "option_name", ""),
        option_family=getattr(option, "option_family", ""),
        score=getattr(getattr(option, "score", None), "total", 0.0),
        pros=list(getattr(option, "pros", []) or []),
        cons=list(getattr(option, "cons", []) or []),
        candidate_id=getattr(option, "candidate_id", None),
        metadata={
            "strategy": deepcopy(getattr(option, "strategy", {}) or {}),
            "lineage": deepcopy(getattr(getattr(option, "lineage", None), "__dict__", {}) or {}),
        },
    )


def _summarize_option_blocks(result: PlannerOrchestratorResult) -> List[PlannerOptionSummary]:
    return list(result.option_summaries or [])


def _severity_counts(result: PlannerOrchestratorResult) -> Dict[str, int]:
    counts = {"warning": len(result.warnings), "error": len(result.errors), "issue": len(result.issues)}
    return counts


def _intent_summary_from_payload(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    summary = {"user": [], "infer": [], "omit": []}
    field_states = _safe_dict(_safe_dict(payload.get("meta")).get("field_states"))
    for path, field in field_states.items():
        source = _lower(_safe_dict(field).get("source"))
        if source in summary:
            summary[source].append(path)
    for key in summary:
        summary[key] = sorted(dict.fromkeys(summary[key]))
    return summary


def _parse_dim_pair_feet(text: str) -> Optional[Tuple[float, float]]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*ft\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*ft", text, flags=re.IGNORECASE)
    if not match:
        return None
    return (_safe_float(match.group(1)), _safe_float(match.group(2)))


def _extract_site_dimensions_from_prompt(prompt_text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    lowered = prompt_text.lower()
    acre_match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*acre|(\d+(?:\.\d+)?)\s*acre", lowered)
    acreage = None
    if acre_match:
        acreage = _safe_float(acre_match.group(1) or acre_match.group(2))

    explicit_lot = re.search(
        r"(?:lot|site)[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*ft",
        prompt_text,
        flags=re.IGNORECASE,
    )
    if explicit_lot:
        return (_safe_float(explicit_lot.group(1)), _safe_float(explicit_lot.group(2)), acreage)

    if acreage and acreage > 0.0:
        area_sf = acreage * 43560.0
        side = math.sqrt(area_sf)
        return (round(side, 1), round(side, 1), acreage)

    dims = _parse_dim_pair_feet(prompt_text)
    if dims:
        return (dims[0], dims[1], acreage)
    return (None, None, acreage)


def _detect_project_type_from_prompt(prompt_text: str) -> str:
    lowered = prompt_text.lower()
    if "mixed-use" in lowered or "mixed use" in lowered:
        return "mixed_use"
    if "commercial" in lowered or "retail pad" in lowered:
        return "commercial_pad"
    if "multifamily" in lowered or "residential" in lowered:
        return "multifamily"
    return "generic_site"


def _extract_buildings_from_prompt(prompt_text: str, project_type: str) -> List[Dict[str, Any]]:
    buildings: List[Dict[str, Any]] = []
    multi_match = re.search(
        r"(\d+)\s+multifamily\s+buildings?[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*x\s*(\d+(?:\.\d+)?)\s*ft",
        prompt_text,
        flags=re.IGNORECASE,
    )
    if multi_match:
        count = max(1, _safe_int(multi_match.group(1), 1))
        width = _safe_float(multi_match.group(2))
        depth = _safe_float(multi_match.group(3))
        for idx in range(count):
            buildings.append(
                {
                    "name": f"Building {idx + 1}",
                    "use": "multifamily",
                    "w": width,
                    "d": depth,
                }
            )

    retail_patterns = (
        (
            r"(\d+)\s+(?:commercial\s+)?retail\s+(?:pad|building)s?[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*x\s*(\d+(?:\.\d+)?)\s*ft",
            "Retail",
        ),
        (
            r"(\d+)\s+commercial\s+building[s]?[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*x\s*(\d+(?:\.\d+)?)\s*ft",
            "Commercial Building",
        ),
        (
            r"(\d+)\s+office\s+building[s]?[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*x\s*(\d+(?:\.\d+)?)\s*ft",
            "Office Building",
        ),
        (
            r"(\d+)\s+industrial\s+building[s]?[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*x\s*(\d+(?:\.\d+)?)\s*ft",
            "Industrial Building",
        ),
    )
    for pattern, base_name in retail_patterns:
        match = re.search(pattern, prompt_text, flags=re.IGNORECASE)
        if not match:
            continue
        count = max(1, _safe_int(match.group(1), 1))
        width = _safe_float(match.group(2))
        depth = _safe_float(match.group(3))
        use = "retail"
        if "office" in base_name.lower():
            use = "office"
        elif "industrial" in base_name.lower():
            use = "industrial"
        elif "commercial" in base_name.lower() and base_name != "Retail":
            use = "generic"
        for idx in range(count):
            if count == 1:
                name = base_name
            else:
                name = f"{base_name} {idx + 1}"
            buildings.append(
                {
                    "name": name,
                    "use": use,
                    "w": width,
                    "d": depth,
                }
            )
        break

    if buildings:
        return buildings

    single_building = re.search(
        r"(?:one|1)\s+building[^.\n]*?(\d+(?:\.\d+)?)\s*ft\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*ft",
        prompt_text,
        flags=re.IGNORECASE,
    )
    if single_building:
        buildings.append(
            {
                "name": "Building 1",
                "use": "retail" if project_type == "commercial_pad" else "generic",
                "w": _safe_float(single_building.group(1)),
                "d": _safe_float(single_building.group(2)),
            }
        )
    return buildings


def _estimate_parking_count_from_prompt(prompt_text: str, buildings: List[Dict[str, Any]]) -> int:
    explicit = re.search(r"parking\s+for\s+(\d+)\s+(?:cars|spaces?)", prompt_text, flags=re.IGNORECASE)
    if explicit:
        return max(0, _safe_int(explicit.group(1), 0))

    lowered = prompt_text.lower()
    residential_units = 0
    residential_ratio = None
    units_match = re.search(r"(?:assume|assuming)\s+(\d+)\s+units?\s+per\s+building", lowered)
    ratio_match = re.search(
        r"(?:residential(?:\s+parking)?(?:\s+at)?\s*:?\s*)(\d+(?:\.\d+)?)\s+spaces?\s+per\s+unit",
        lowered,
    )
    if units_match and ratio_match:
        residential_count = sum(1 for b in buildings if _lower(b.get("use")) == "multifamily")
        residential_units = residential_count * _safe_int(units_match.group(1), 0)
        residential_ratio = _safe_float(ratio_match.group(1), 0.0)

    commercial_spaces = 0
    commercial_match = re.search(
        r"(?:commercial(?:\s+parking)?(?:\s+at)?\s*:?\s*)1\s+space\s+per\s+(\d+(?:\.\d+)?)\s*sq\s*ft",
        lowered,
    )
    if commercial_match:
        sf_per_space = max(_safe_float(commercial_match.group(1), 250.0), 1.0)
        for b in buildings:
            if _lower(b.get("use")) == "retail":
                commercial_spaces += int(round((_safe_float(b.get("w")) * _safe_float(b.get("d"))) / sf_per_space))

    if residential_units > 0 and residential_ratio is not None:
        return int(round(residential_units * residential_ratio)) + commercial_spaces

    return max(0, commercial_spaces)


def _count_requested_systems(prompt_text: str) -> int:
    lowered = prompt_text.lower()
    return sum(
        1
        for token in ("grading", "drainage", "storm", "sanitary", "water", "utilities", "road", "ada", "detention")
        if token in lowered
    )


def _is_structured_prompt_fast_path(req: PlannerOrchestratorRequest) -> bool:
    prompt_text = _safe_str(req.prompt_text)
    if not prompt_text or _lower(req.input_mode) not in {"assisted", "prompt", "text"}:
        return False
    lowered = prompt_text.lower()
    has_site_size = bool(re.search(r"\d+(?:\.\d+)?\s*acre", lowered) or re.search(r"\d+(?:\.\d+)?\s*ft\s*(?:x|by)\s*\d+(?:\.\d+)?\s*ft", lowered))
    has_program = any(token in lowered for token in ("building", "buildings", "parking", "retail", "multifamily"))
    has_systems = _count_requested_systems(prompt_text) >= 3
    has_layout_signal = any(token in lowered for token in ("driveway", "road", "cul-de-sac", "circulation", "setback"))
    return has_site_size and has_program and (has_systems or has_layout_signal)


def _fast_parse_from_prompt(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    prompt_text = _safe_str(req.prompt_text)
    project_type = _detect_project_type_from_prompt(prompt_text)
    lot_w, lot_h, acreage = _extract_site_dimensions_from_prompt(prompt_text)
    buildings = _extract_buildings_from_prompt(prompt_text, project_type)
    parking_count = _estimate_parking_count_from_prompt(prompt_text, buildings)
    first_building = buildings[0] if buildings else {}
    lowered = prompt_text.lower()

    setback_match = re.search(r"(\d+(?:\.\d+)?)\s*ft\s+setbacks?", prompt_text, flags=re.IGNORECASE)
    driveway_match = re.search(r"(\d+(?:\.\d+)?)\s*ft\s+wide\s+driveway", prompt_text, flags=re.IGNORECASE)
    road_width_match = re.search(r"road width:\s*(\d+(?:\.\d+)?)\s*ft", prompt_text, flags=re.IGNORECASE)
    inlet_match = re.search(r"at least\s+(\d+)\s+inlets?", prompt_text, flags=re.IGNORECASE)
    trunk_match = re.search(r"one\s+trunk\s+line|1\s+trunk\s+line", lowered)
    culdesac_match = re.search(r"(\d+)\s+cul-de-sacs?", prompt_text, flags=re.IGNORECASE)
    nw_elev_match = re.search(
        r"northwest\s+corner\s*\((\d+(?:\.\d+)?)\s*ft\)",
        prompt_text,
        flags=re.IGNORECASE,
    )
    se_elev_match = re.search(
        r"southeast\s+corner\s*\((\d+(?:\.\d+)?)\s*ft\)",
        prompt_text,
        flags=re.IGNORECASE,
    )

    payload: Dict[str, Any] = {
        "project_name": "Civora Design",
        "units": req.units or "ft",
        "mode": "site_plan",
        "project_type": project_type,
        "site_type": project_type,
        "lot": {
            "x": 0.0,
            "y": 0.0,
            "w": lot_w or 140.0,
            "h": lot_h or 110.0,
        },
        "setback": _safe_float(setback_match.group(1), 15.0) if setback_match else 15.0,
        "street_edge": "bottom",
        "layout_strategy": "balanced",
        "site_plan": {
            "building_width": _safe_float(first_building.get("w"), 48.0),
            "building_depth": _safe_float(first_building.get("d"), 34.0),
            "parking_count": parking_count,
            "driveway_width": _safe_float(driveway_match.group(1), 0.0) if driveway_match else None,
            "aisle_width": 24.0 if "drive aisle" in lowered else None,
        },
        "buildings": buildings,
        "terrain": " ".join(
            part
            for part in (
                f"{acreage:g} acre site" if acreage else "",
                "gentle slope" if "gentle slope" in lowered else "",
                "slope falling from the northwest corner to the southeast corner" if "northwest" in lowered and "southeast" in lowered else "",
                f"northwest corner {nw_elev_match.group(1)} ft" if nw_elev_match else "",
                f"southeast corner {se_elev_match.group(1)} ft" if se_elev_match else "",
                "average slope of 5%" if "5%" in lowered else "",
            )
            if part
        ).strip(),
        "grading": {
            "contours_required": "contour" in lowered,
            "min_slope_pct": 1.5 if "1.5%" in lowered else 2.0,
            "corner_elevations": {
                "northwest": _safe_float(nw_elev_match.group(1), 0.0) if nw_elev_match else None,
                "southeast": _safe_float(se_elev_match.group(1), 0.0) if se_elev_match else None,
            },
        },
        "drainage": {
            "inlet_count": _safe_int(inlet_match.group(1), 2) if inlet_match else (4 if acreage and acreage >= 5 else 2),
            "trunk_line_count": 1 if trunk_match or "trunk line" in lowered else 0,
            "pond_count": 1 if "detention" in lowered else 0,
            "outfall_side": "bottom" if "southeast" in lowered or "south" in lowered else "right",
            "routing_required": "drainage" in lowered or "storm" in lowered,
            "grading_required": "grading" in lowered,
            "detention_required": "detention" in lowered,
        },
        "road": {
            "lane_width": _safe_float(road_width_match.group(1), 28.0) / 2.0 if road_width_match else None,
            "lanes": 2 if "2 lane" in lowered or "2 lanes" in lowered else None,
            "max_grade_pct": 8.0 if "8%" in lowered else None,
        },
        "subdivision": {
            "acreage": acreage,
            "culdesac_count": _safe_int(culdesac_match.group(1), 0) if culdesac_match else (2 if "cul-de-sac" in lowered else 0),
            "road_width": _safe_float(road_width_match.group(1), 0.0) if road_width_match else None,
        },
        "deliverables": [
            item
            for item in (
                "site_plan",
                "grading_plan" if "grading" in lowered or "contours" in lowered else None,
                "storm_pipe_plan" if "storm" in lowered or "drainage" in lowered else None,
                "utility_plan" if "sanitary" in lowered or "water" in lowered or "utilities" in lowered else None,
            )
            if item
        ],
        "assumptions": [
            "Prompt was parsed with deterministic fast-path rules because it already contained detailed engineering scope.",
        ],
        "meta": {
            "source_input_mode": "prompt",
            "fast_prompt_parse": True,
        },
    }
    return _normalize_with_planner(payload)


# =============================================================================
# PARSE ROUTING
# =============================================================================

def _parse_from_prompt(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    if _is_structured_prompt_fast_path(req):
        return _fast_parse_from_prompt(req)

    if command_mode is None:
        payload = deepcopy(req.manual_fields)
        payload.setdefault("meta", {})
        payload["meta"]["prompt_parse_unavailable"] = True
        payload["meta"]["source_input_mode"] = "prompt"
        return _normalize_with_planner(payload)

    parsed = command_mode(_safe_str(req.prompt_text))
    parsed.setdefault("meta", {})
    parsed["meta"]["source_input_mode"] = "prompt"
    if req.plan_type_hint:
        parsed["meta"]["plan_type_hint"] = req.plan_type_hint
    if req.units:
        parsed["units"] = req.units
    return _normalize_with_planner(parsed)


def _parse_from_manual(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    payload, _ = _unwrap_manual_fields_payload(req.manual_fields)
    payload.setdefault("units", req.units)
    payload.setdefault("meta", {})
    payload["meta"]["source_input_mode"] = "manual"
    if req.plan_type_hint:
        payload["meta"]["plan_type_hint"] = req.plan_type_hint
    return _normalize_with_planner(payload)


def _parse_from_sketch(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    payload = deepcopy(req.manual_fields)
    payload.setdefault("units", req.units)
    payload.setdefault("meta", {})
    payload["meta"]["source_input_mode"] = "sketch"

    if SketchParser is None or SketchInput is None:
        payload["meta"]["sketch_parser_unavailable"] = True
        payload["meta"]["sketch_warnings"] = ["Sketch parser is not available in this runtime."]
        return _normalize_with_planner(payload)

    sketch_payload = _safe_dict(req.manual_fields.get("sketch"))
    parser = SketchParser()
    parsed_sketch = parser.parse(SketchInput(**sketch_payload))

    payload["meta"]["sketch_summary"] = {
        "boundary_zones": len(getattr(parsed_sketch, "boundary_zones", []) or []),
        "objects": len(getattr(parsed_sketch, "objects", []) or []),
        "centerlines": len(getattr(parsed_sketch, "centerlines", []) or []),
        "warnings": list(getattr(parsed_sketch, "warnings", []) or []),
    }
    return _normalize_with_planner(payload)


def _parse_from_image(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    payload = deepcopy(req.manual_fields)
    payload.setdefault("units", req.units)
    payload.setdefault("meta", {})
    payload["meta"]["source_input_mode"] = "image"

    if ImageAnalysisEngine is None or ImageAnalysisInput is None:
        payload["meta"]["image_analysis_unavailable"] = True
        payload["meta"]["image_analysis_warnings"] = ["Image analysis engine is not available in this runtime."]
        return _normalize_with_planner(payload)

    engine = ImageAnalysisEngine()
    image_payload = _safe_dict(req.manual_fields.get("image_analysis"))
    result = engine.analyze(ImageAnalysisInput(**image_payload))

    payload["meta"]["image_analysis_counts"] = deepcopy(getattr(result, "counts", {}) or {})
    payload["meta"]["image_analysis_warnings"] = list(getattr(result, "warnings", []) or [])

    if req.image_width_px is not None:
        payload["meta"]["image_width_px"] = req.image_width_px
    if req.image_height_px is not None:
        payload["meta"]["image_height_px"] = req.image_height_px
    if req.pixels_per_unit is not None:
        payload["meta"]["pixels_per_unit"] = req.pixels_per_unit
    if req.image_path:
        payload["meta"]["image_path"] = req.image_path

    return _normalize_with_planner(payload)


def _route_parse(req: PlannerOrchestratorRequest) -> Dict[str, Any]:
    mode = _lower(req.input_mode or "assisted")

    if mode in {"assisted", "prompt", "text"} and req.prompt_text:
        parsed = _parse_from_prompt(req)
    elif mode == "manual":
        parsed = _parse_from_manual(req)
    elif mode == "sketch":
        parsed = _parse_from_sketch(req)
    elif mode == "image":
        parsed = _parse_from_image(req)
    else:
        parsed = _parse_from_manual(req) if req.manual_fields else _parse_from_prompt(req)

    merged = _merge_manual_fields(parsed, req.manual_fields, allow_fill_for_blanks=req.allow_ai_fill_for_blanks)
    merged.setdefault("meta", {})
    merged["meta"]["orchestrator_input_mode"] = mode
    merged["meta"]["strict_mode"] = req.strict_mode
    merged["meta"]["full_design_mode"] = req.full_design_mode
    merged["meta"]["optimize_goal"] = req.optimize_goal
    merged["meta"]["global_iteration_limit"] = req.global_iteration_limit
    merged["meta"]["score_improvement_epsilon"] = req.score_improvement_epsilon
    merged["meta"]["intent_summary"] = _intent_summary_from_payload(merged)
    return _normalize_with_planner(merged)


# =============================================================================
# CORE FLOWS
# =============================================================================

def _single_plan_flow(
    parsed_payload: Dict[str, Any],
    *,
    progress_callback: Optional[Callable[..., None]] = None,
) -> PlannerOrchestratorResult:
    final_plan = planner.build_plan(parsed_payload, progress_callback=progress_callback)
    warnings, errors = _collect_warnings_errors(final_plan)
    success = not _manual_plan_failed(final_plan)
    missing_requirements = _missing_requirements_from_plan(final_plan) if not success else {}
    runtime_checkpoint = _safe_dict(_safe_dict(final_plan.get("meta")).get("runtime_phase_checkpoint"))
    runtime_should_continue = bool(runtime_checkpoint.get("yielded"))
    if runtime_should_continue:
        message = _safe_str(runtime_checkpoint.get("message"), "Saved a phase checkpoint and prepared the next engineering phase.")
    else:
        message = "Generated coordinated plan." if success else _friendly_missing_requirements_message(missing_requirements)

    return PlannerOrchestratorResult(
        success=success,
        message=message,
        parsed_payload=deepcopy(parsed_payload),
        final_plan=deepcopy(final_plan),
        alternatives=deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("multi_option")).get("alternatives", [])),
        option_summaries=[],
        warnings=warnings,
        errors=errors,
        issues=_collect_issues(final_plan),
        assumptions=_collect_assumptions(parsed_payload, final_plan),
        metadata={
            "workflow": "single_plan",
            "route": deepcopy(_safe_dict(_safe_dict(final_plan.get("meta")).get("routing"))),
            "recommended_score": _planner_score_from_plan(final_plan),
            "runtime_should_continue": runtime_should_continue,
            "runtime_phase_checkpoint": deepcopy(runtime_checkpoint),
            **({"missing_requirements": missing_requirements, "needs_clarification": True} if not success else {}),
        },
    )


def _multi_option_flow(parsed_payload: Dict[str, Any], req: PlannerOrchestratorRequest) -> PlannerOrchestratorResult:
    intelligence = planner_intelligence.PlannerIntelligence()

    preferences = deepcopy(_safe_dict(req.meta.get("preferences")))
    if req.optimize_goal:
        preferences["goal"] = req.optimize_goal
    if "optimization_goals" in parsed_payload:
        preferences.update(_safe_dict(parsed_payload.get("optimization_goals")))

    result = intelligence.generate_options(
        parsed_payload,
        max_candidates=max(1, int(req.max_candidates)),
        top_k=max(1, int(req.top_k)),
        extra_preferences=preferences,
    )

    if not result.success or result.recommended is None:
        return PlannerOrchestratorResult(
            success=False,
            message="No viable planning options were generated.",
            parsed_payload=deepcopy(parsed_payload),
            final_plan={},
            alternatives=[],
            option_summaries=[],
            warnings=["No viable planning options were generated."],
            errors=[],
            issues=[],
            assumptions=[],
            metadata={
                "workflow": "multi_option",
                "result_success": False,
                "preferences": deepcopy(preferences),
            },
        )

    final_plan = deepcopy(result.recommended.plan)
    warnings, errors = _collect_warnings_errors(final_plan)

    alternatives = [_candidate_to_alt(option) for option in result.top_options[1:]]
    option_summaries = [_candidate_to_summary(option) for option in result.top_options]

    metadata = {
        "workflow": "multi_option",
        "option_groups": deepcopy(result.option_groups),
        "questions": [deepcopy(q.__dict__) for q in result.questions],
        "actions": [deepcopy(a.__dict__) for a in result.actions],
        "rejected_summary": deepcopy(result.rejected_summary),
        "saved_options": [_candidate_to_alt(opt) for opt in result.saved_options],
        "recommended_option_name": result.recommended.option_name,
        "recommended_candidate_id": result.recommended.candidate_id,
        "recommended_score": result.recommended.score.total,
        "recommended_family": result.recommended.option_family,
        "recommended_pros": list(result.recommended.pros),
        "recommended_cons": list(result.recommended.cons),
        "comparison_summary": deepcopy(_safe_dict(result.metadata).get("comparison_summary", {})),
        "candidate_count": _safe_dict(result.metadata).get("candidate_count", len(result.top_options)),
        "requested_top_k": _safe_dict(result.metadata).get("requested_top_k", req.top_k),
        "preferences": deepcopy(_safe_dict(result.metadata).get("preferences", preferences)),
    }

    return PlannerOrchestratorResult(
        success=True,
        message=result.message,
        parsed_payload=deepcopy(parsed_payload),
        final_plan=final_plan,
        alternatives=alternatives,
        option_summaries=option_summaries,
        warnings=warnings,
        errors=errors,
        issues=_collect_issues(final_plan),
        assumptions=_collect_assumptions(parsed_payload, final_plan),
        metadata=metadata,
    )


# =============================================================================
# FULL DESIGN LOOP / HARDENING
# =============================================================================

def _should_use_multi_option(parsed_payload: Dict[str, Any], req: PlannerOrchestratorRequest) -> bool:
    if _lower(req.input_mode) == "manual" or _lower(_safe_dict(parsed_payload.get("meta")).get("input_mode")) == "manual":
        return False
    if req.strict_mode:
        return False
    requested_system = _lower(_safe_dict(req.meta).get("requested_system"))
    if requested_system in {"roads", "parking", "grading", "drainage", "utilities", "full"}:
        return False

    prompt_text = _safe_str(req.prompt_text)
    lowered_prompt = prompt_text.lower()
    site_plan = _safe_dict(parsed_payload.get("site_plan"))
    project_type = _lower(parsed_payload.get("project_type") or parsed_payload.get("site_type"))
    heavy_keyword_hits = sum(
        1
        for token in (
            "storm drainage",
            "detention basin",
            "sanitary",
            "water system",
            "utilities",
            "grading",
            "ada",
            "mixed-use",
            "mixed use",
            "cul-de-sac",
        )
        if token in lowered_prompt
    )
    fully_engineered_prompt = "fully engineered civil site plan" in lowered_prompt
    large_prompt = len(prompt_text) >= 900 or prompt_text.count("\n-") >= 10
    large_parking_program = _safe_int(site_plan.get("parking_count"), 0) >= 80
    force_single_plan = (
        not req.full_design_mode
        and (
            project_type in {"mixed_use", "mixed-use", "subdivision"}
            or (fully_engineered_prompt and heavy_keyword_hits >= 4)
            or (large_prompt and heavy_keyword_hits >= 3)
            or (large_parking_program and heavy_keyword_hits >= 3)
        )
    )
    if force_single_plan:
        return False

    mode = _lower(parsed_payload.get("mode"))
    if mode in {"site_plan", "subdivision", "road", "drainage", "bridge", "pool"}:
        return True

    if _safe_dict(parsed_payload.get("optimization_goals")):
        return True

    explicit_pref = _lower(_safe_dict(req.meta).get("workflow"))
    if explicit_pref in {"multi", "multi_option", "assisted", "optimize"}:
        return True

    return not req.strict_mode


def _build_iteration_record(
    iteration_index: int,
    result: PlannerOrchestratorResult,
    changes_applied: Dict[str, Any],
    notes: Optional[List[str]] = None,
) -> DesignLoopIteration:
    return DesignLoopIteration(
        iteration_index=iteration_index,
        workflow=_safe_str(result.metadata.get("workflow"), "unknown"),
        success=result.success,
        message=result.message,
        recommended_option_name=_safe_str(result.metadata.get("recommended_option_name"), "") or None,
        recommended_candidate_id=_safe_str(result.metadata.get("recommended_candidate_id"), "") or None,
        recommended_score=_safe_float(result.metadata.get("recommended_score"), _planner_score_from_plan(result.final_plan)),
        warning_count=len(result.warnings),
        error_count=len(result.errors),
        issue_count=len(result.issues),
        changes_applied=deepcopy(changes_applied),
        notes=list(notes or []),
        metadata=deepcopy(result.metadata),
    )


def _derive_next_pass_adjustments(
    current_result: PlannerOrchestratorResult,
    current_payload: Dict[str, Any],
    req: PlannerOrchestratorRequest,
    iteration_index: int,
) -> Dict[str, Any]:
    adjustments: Dict[str, Any] = {"meta": {}}

    current_meta = _safe_dict(current_payload.get("meta"))
    current_passes = _safe_int(current_meta.get("planner_passes"), 2)

    issue_codes = {_safe_str(issue.code) for issue in current_result.issues}
    issue_messages = " ".join(issue.message for issue in current_result.issues).lower()

    # give planner more room when issues remain
    if current_result.errors or current_result.warnings:
        adjustments["meta"]["planner_passes"] = max(current_passes + 1, 3)

    # harden drainage-related reruns
    if any("DRAINAGE" in code for code in issue_codes) or "drainage" in issue_messages:
        adjustments["layout_strategy"] = "drainage_friendly"
        adjustments["drainage"] = _deep_merge(_safe_dict(current_payload.get("drainage")), {"outfall_side": "bottom"})
        adjustments["optimization_goals"] = _deep_merge(_safe_dict(current_payload.get("optimization_goals")), {"goal": "improve_drainage"})

    # harden pipe-related reruns
    if any("PIPE" in code for code in issue_codes) or "pipe" in issue_messages:
        adjustments["optimization_goals"] = _deep_merge(_safe_dict(current_payload.get("optimization_goals")), {"goal": "reduce_pipe_length"})
        adjustments["meta"]["pipe_retry_bias"] = True

    # harden utility-related reruns
    if any("UTILITY" in code for code in issue_codes) or "utility" in issue_messages:
        adjustments["layout_strategy"] = "utility_efficient"
        adjustments["meta"]["utility_retry_bias"] = True

    # harden grading / earthwork-related reruns
    if "grading" in issue_messages or "earthwork" in issue_messages:
        adjustments["layout_strategy"] = "grading_friendly"
        adjustments["optimization_goals"] = _deep_merge(_safe_dict(current_payload.get("optimization_goals")), {"goal": "reduce_grading"})

    # if many warnings and no explicit parking push, rebalance
    if len(current_result.warnings) >= 5 and _lower(req.optimize_goal) not in {"maximize_parking", "more_parking"}:
        adjustments["layout_strategy"] = "balanced"

    # keep explicit user goal active
    if req.optimize_goal:
        adjustments["optimization_goals"] = _deep_merge(_safe_dict(adjustments.get("optimization_goals")), {"goal": req.optimize_goal})

    adjustments["meta"]["evolution_round"] = iteration_index
    adjustments["meta"]["orchestrator_hardening_pass"] = True
    return adjustments


def _is_iteration_clean_enough(result: PlannerOrchestratorResult) -> bool:
    return not result.errors and not result.warnings and not result.issues


def _run_full_design_loop(parsed_payload: Dict[str, Any], req: PlannerOrchestratorRequest) -> PlannerOrchestratorResult:
    state = DesignLoopState()
    current_payload = deepcopy(parsed_payload)

    max_iters = max(1, _safe_int(req.global_iteration_limit, 3))
    epsilon = max(0.0, _safe_float(req.score_improvement_epsilon, 1.0))

    for iteration_index in range(1, max_iters + 1):
        use_multi = _should_use_multi_option(current_payload, req)
        current_result = (
            _multi_option_flow(current_payload, req)
            if use_multi
            else _single_plan_flow(current_payload, progress_callback=req.progress_callback)
        )

        current_score = _safe_float(current_result.metadata.get("recommended_score"), _planner_score_from_plan(current_result.final_plan))
        state.record_score(current_score)

        changes_applied: Dict[str, Any] = {}
        notes: List[str] = []

        if state.improved(current_score):
            state.best_score = current_score
            state.best_plan = deepcopy(current_result.final_plan)
            state.best_parsed_payload = deepcopy(current_payload)
            state.best_result_metadata = deepcopy(current_result.metadata)
            state.best_option_name = _safe_str(current_result.metadata.get("recommended_option_name"), "") or None
            state.best_candidate_id = _safe_str(current_result.metadata.get("recommended_candidate_id"), "") or None
            notes.append("Best score improved.")
        else:
            notes.append("Score did not improve.")

        if _is_iteration_clean_enough(current_result):
            notes.append("Iteration is clean enough.")
        elif _lower(req.input_mode) == "manual" and not current_result.success:
            notes.append("Assisted off returned a failed engineering-validation result.")
        elif current_result.errors:
            notes.append("Errors remain; continuing hardening loop.")
        elif current_result.warnings:
            notes.append("Warnings remain; continuing hardening loop.")

        state.iterations.append(_build_iteration_record(iteration_index, current_result, changes_applied, notes))

        if _lower(req.input_mode) == "manual" and not current_result.success:
            break

        if req.stop_when_clean and _is_iteration_clean_enough(current_result):
            break

        if iteration_index >= max_iters:
            break

        if req.stop_when_score_stalls and len(state.improvement_history) >= 2:
            if abs(state.improvement_history[-1] - state.improvement_history[-2]) <= epsilon:
                state.iterations[-1].notes.append("Stopped because score improvement stalled.")
                break

        changes_applied = _derive_next_pass_adjustments(current_result, current_payload, req, iteration_index)
        current_payload = _preserve_field_intent(_deep_merge(current_payload, changes_applied))
        state.iterations[-1].changes_applied = deepcopy(changes_applied)

    final_plan = deepcopy(state.best_plan) if state.best_plan else {}
    warnings, errors = _collect_warnings_errors(final_plan)

    result = PlannerOrchestratorResult(
        success=bool(final_plan) and not _manual_plan_failed(final_plan),
        message=(
            "Full design workflow completed."
            if final_plan and not _manual_plan_failed(final_plan)
            else _friendly_missing_requirements_message(_missing_requirements_from_plan(final_plan))
            if final_plan and _manual_plan_failed(final_plan)
            else "Full design workflow did not produce a viable final plan."
        ),
        parsed_payload=deepcopy(state.best_parsed_payload if state.best_parsed_payload else parsed_payload),
        final_plan=final_plan,
        alternatives=deepcopy(_safe_list(state.best_result_metadata.get("alternatives"))),
        option_summaries=[],
        warnings=warnings,
        errors=errors,
        issues=_collect_issues(final_plan),
        assumptions=_collect_assumptions(state.best_parsed_payload if state.best_parsed_payload else parsed_payload, final_plan) if final_plan else [],
        metadata=deepcopy(state.best_result_metadata),
    )

    result.metadata["workflow"] = "full_design_loop"
    if final_plan and _manual_plan_failed(final_plan):
        result.metadata["missing_requirements"] = _missing_requirements_from_plan(final_plan)
        result.metadata["needs_clarification"] = True
    result.metadata["best_score"] = state.best_score
    result.metadata["best_option_name"] = state.best_option_name
    result.metadata["best_candidate_id"] = state.best_candidate_id
    result.metadata["iterations"] = [deepcopy(it.__dict__) for it in state.iterations]
    result.metadata["improvement_history"] = deepcopy(state.improvement_history)
    result.metadata["global_iteration_limit"] = max_iters
    result.metadata["score_improvement_epsilon"] = epsilon
    result.metadata["full_design_mode"] = True
    result.metadata["severity_counts"] = _severity_counts(result)

    return result


# =============================================================================
# PUBLIC ENTRYPOINTS
# =============================================================================

def orchestrate_plan(req: PlannerOrchestratorRequest) -> PlannerOrchestratorResult:
    if _lower(req.input_mode) == "manual":
        req.allow_ai_fill_for_blanks = False
    parsed_payload = _preserve_field_intent(_route_parse(req))
    parsed_payload.setdefault("meta", {})
    parsed_payload["meta"]["strict_mode"] = req.strict_mode
    parsed_payload["meta"]["persist_trace_metadata"] = req.persist_trace_metadata
    parsed_payload["meta"]["allow_ai_fill_for_blanks"] = req.allow_ai_fill_for_blanks
    parsed_payload["meta"]["assisted_enabled"] = bool(req.allow_ai_fill_for_blanks)
    parsed_payload["meta"]["orchestrator_meta"] = deepcopy(req.meta)
    parsed_payload["meta"]["input_mode"] = req.input_mode
    parsed_payload["meta"]["manual_mode"] = _lower(req.input_mode) == "manual"
    parsed_payload["meta"]["optimize_goal"] = req.optimize_goal

    if req.full_design_mode:
        result = _run_full_design_loop(parsed_payload, req)
    else:
        wants_multi = _should_use_multi_option(parsed_payload, req)
        result = _multi_option_flow(parsed_payload, req) if wants_multi else _single_plan_flow(parsed_payload, progress_callback=req.progress_callback)

    result.metadata.setdefault("input_mode", req.input_mode)
    result.metadata.setdefault("manual_mode", _lower(req.input_mode) == "manual")
    result.metadata.setdefault("strict_mode", req.strict_mode)
    result.metadata.setdefault("plan_type_hint", req.plan_type_hint)
    result.metadata.setdefault("units", req.units)
    result.metadata.setdefault("max_candidates", req.max_candidates)
    result.metadata.setdefault("top_k", req.top_k)
    result.metadata.setdefault("evolution_rounds", req.evolution_rounds)
    result.metadata.setdefault("full_design_mode", req.full_design_mode)
    result.metadata.setdefault("optimize_goal", req.optimize_goal)
    result.metadata.setdefault("severity_counts", _severity_counts(result))

    # keep final option summaries in all modes when available
    result.option_summaries = _summarize_option_blocks(result)

    if req.persist_trace_metadata:
        result.metadata["parsed_payload_meta"] = deepcopy(_safe_dict(parsed_payload.get("meta")))
        result.metadata["final_plan_meta"] = deepcopy(_safe_dict(result.final_plan.get("meta")))

    return result


def orchestrate_prompt(
    prompt_text: str,
    *,
    strict_mode: bool = False,
    full_design_mode: bool = False,
    optimize_goal: Optional[str] = None,
    plan_type_hint: Optional[str] = None,
    units: str = "ft",
    meta: Optional[Dict[str, Any]] = None,
) -> PlannerOrchestratorResult:
    req = PlannerOrchestratorRequest(
        input_mode="prompt",
        strict_mode=strict_mode,
        full_design_mode=full_design_mode,
        optimize_goal=optimize_goal,
        prompt_text=prompt_text,
        plan_type_hint=plan_type_hint,
        units=units,
        meta=deepcopy(meta) if isinstance(meta, dict) else {},
    )
    return orchestrate_plan(req)


def orchestrate_manual(
    manual_fields: Dict[str, Any],
    *,
    strict_mode: bool = False,
    full_design_mode: bool = False,
    optimize_goal: Optional[str] = None,
    plan_type_hint: Optional[str] = None,
    units: str = "ft",
    meta: Optional[Dict[str, Any]] = None,
) -> PlannerOrchestratorResult:
    normalized_manual_fields, wrapper = _unwrap_manual_fields_payload(manual_fields)
    strict_mode = bool(wrapper.get("strict_mode", strict_mode))
    full_design_mode = bool(wrapper.get("full_design_mode", full_design_mode))
    optimize_goal = wrapper.get("optimize_goal", optimize_goal)
    plan_type_hint = _safe_str(wrapper.get("plan_type_hint"), plan_type_hint) if wrapper.get("plan_type_hint") is not None else plan_type_hint
    units = _safe_str(wrapper.get("units"), units) if wrapper.get("units") is not None else units
    merged_meta = deepcopy(meta) if isinstance(meta, dict) else {}
    if isinstance(wrapper.get("meta"), dict):
        merged_meta = _deep_merge(merged_meta, _safe_dict(wrapper.get("meta")))
    req = PlannerOrchestratorRequest(
        input_mode="manual",
        strict_mode=strict_mode,
        full_design_mode=full_design_mode,
        optimize_goal=optimize_goal,
        manual_fields=deepcopy(normalized_manual_fields),
        plan_type_hint=plan_type_hint,
        units=units,
        meta=merged_meta,
    )
    return orchestrate_plan(req)


def run_planner_orchestrator(req: PlannerOrchestratorRequest) -> PlannerOrchestratorResult:
    return orchestrate_plan(req)
