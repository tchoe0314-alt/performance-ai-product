from __future__ import annotations

"""
planner_intelligence.py (FINAL TRUE MAX ALIGNED VERSION)

Purpose
-------
Deep planning-intelligence layer for the AI civil / CAD product.

This version keeps your current planner_intelligence.py as the base and aligns it to:
- the final integration-hardened planner_orchestrator
- the final aligned planner
- the upgraded ProjectManager lifecycle/state layer
- the upgraded pipe backend and planner metric packaging
- stronger candidate evolution, refinement, scoring, and UI-ready comparison output

Design goals
------------
- preserve planner.py as the execution engine
- preserve the strong existing architecture and data models
- add global iteration memory, candidate evolution, and cross-candidate learning
- stay deterministic, inspectable, and production-oriented
- produce UI-ready metadata, questions, actions, and comparison structures
"""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple
import importlib
import uuid


# =============================================================================
# DEFAULTS / TUNING
# =============================================================================

MAX_DEFAULT_CANDIDATES = 8
DEFAULT_TOP_OPTIONS = 4
DEFAULT_MAX_SAVED_OPTIONS = 20
DEFAULT_REFINEMENT_PASSES = 3
DEFAULT_GLOBAL_EVOLUTION_ROUNDS = 3

MIN_ACCEPTABLE_SCORE = -250.0

DEFAULT_SCORE_WEIGHTS = {
    "program_fit": 1.00,
    "parking": 1.15,
    "circulation": 1.00,
    "grading": 1.05,
    "drainage": 1.10,
    "pipes": 0.95,
    "utilities": 1.00,
    "compliance": 1.20,
    "constructability": 1.05,
    "completeness": 1.00,
    "confidence": 0.90,
}

SITE_MODES = {
    "site_plan",
    "subdivision",
    "road",
    "bridge",
    "pool",
    "drainage",
    "direct_actions",
}

SITE_LAYOUT_STRATEGIES = {
    "front_parking",
    "rear_parking",
    "side_parking",
    "street_building",
    "building_courts",
    "double_loaded_court",
    "yield_max",
    "grading_friendly",
    "drainage_friendly",
    "frontage_emphasis",
    "utility_efficient",
    "balanced",
}


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _dedupe_keep_order(items: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _mode(payload: Dict[str, Any]) -> str:
    return _lower(payload.get("mode") or "site_plan")


def _project_type(payload: Dict[str, Any]) -> str:
    return _lower(payload.get("project_type") or "generic_site")


def _lot(payload: Dict[str, Any]) -> Dict[str, float]:
    lot = _safe_dict(payload.get("lot"))
    return {
        "x": _safe_float(lot.get("x"), 0.0),
        "y": _safe_float(lot.get("y"), 0.0),
        "w": _safe_float(lot.get("w"), 0.0),
        "h": _safe_float(lot.get("h"), 0.0),
    }


def _lot_area(payload: Dict[str, Any]) -> float:
    box = _lot(payload)
    return max(0.0, box["w"]) * max(0.0, box["h"])


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if key not in out:
            out[key] = deepcopy(value)
            continue
        if isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _coverage_ratio(plan_meta: Dict[str, Any]) -> float:
    qa = _safe_dict(plan_meta.get("qa"))
    stats = _safe_dict(qa.get("stats"))
    return _safe_float(stats.get("estimated_impervious_coverage_ratio"), 0.0)


def _warning_count(plan: Dict[str, Any]) -> int:
    meta = _safe_dict(plan.get("meta"))
    qa = _safe_dict(meta.get("qa"))
    return _safe_int(qa.get("warning_count"), 0)


def _error_count(plan: Dict[str, Any]) -> int:
    meta = _safe_dict(plan.get("meta"))
    qa = _safe_dict(meta.get("qa"))
    return _safe_int(qa.get("error_count"), 0)


def _qa_issues(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = _safe_dict(plan.get("meta"))
    qa = _safe_dict(meta.get("qa"))
    return _safe_list(qa.get("issues"))


def _planner_score_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("planner_score"))


def _optimization_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("optimization_summary"))


def _manager_export_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("manager_export"))


def _project_manager_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("project_manager"))


def _field_source(payload: Dict[str, Any], path: str, default: str = "infer") -> str:
    field_states = _safe_dict(_safe_dict(payload.get("meta")).get("field_states"))
    return _lower(_safe_dict(field_states.get(path)).get("source") or default)


def _is_omitted(payload: Dict[str, Any], path: str) -> bool:
    return _field_source(payload, path) == "omit"


def _component_label(name: str) -> str:
    labels = {
        "program_fit": "program fit",
        "parking": "parking",
        "circulation": "circulation",
        "grading": "grading",
        "drainage": "drainage",
        "pipes": "pipe efficiency",
        "utilities": "utility efficiency",
        "compliance": "compliance",
        "constructability": "constructability",
        "completeness": "completeness",
        "confidence": "confidence",
    }
    return labels.get(name, name.replace("_", " "))


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CandidateLineage:
    candidate_id: str
    parent_candidate_id: Optional[str] = None
    generation: int = 0
    source_family: str = ""
    source_strategy: str = ""


@dataclass
class CandidateConflict:
    code: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateDecision:
    category: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateScore:
    total: float = 0.0

    program_fit: float = 0.0
    parking: float = 0.0
    circulation: float = 0.0
    grading: float = 0.0
    drainage: float = 0.0
    pipes: float = 0.0
    utilities: float = 0.0
    compliance: float = 0.0
    constructability: float = 0.0
    completeness: float = 0.0
    confidence: float = 0.0

    weighted_components: Dict[str, float] = field(default_factory=dict)
    penalties: Dict[str, float] = field(default_factory=dict)
    bonuses: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


@dataclass
class CandidateRefinementStep:
    pass_index: int
    title: str
    description: str
    payload_changes: Dict[str, Any] = field(default_factory=dict)
    conflict_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    score_after_pass: Optional[float] = None


@dataclass
class EvolutionRoundRecord:
    round_index: int
    title: str
    selected_parent_ids: List[str] = field(default_factory=list)
    generated_candidate_ids: List[str] = field(default_factory=list)
    top_score_after_round: Optional[float] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class CandidatePlan:
    candidate_id: str
    option_name: str
    strategy: Dict[str, Any]
    payload: Dict[str, Any]
    lineage: CandidateLineage

    plan: Dict[str, Any] = field(default_factory=dict)
    preview_payload: Dict[str, Any] = field(default_factory=dict)

    score: CandidateScore = field(default_factory=CandidateScore)
    conflicts: List[CandidateConflict] = field(default_factory=list)
    decisions: List[CandidateDecision] = field(default_factory=list)
    refinements: List[CandidateRefinementStep] = field(default_factory=list)

    assumptions: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)

    option_family: str = ""
    is_saved: bool = False


@dataclass
class IntelligenceQuestion:
    question_id: str
    question_type: str
    prompt: str
    options: List[str] = field(default_factory=list)
    field_name: Optional[str] = None
    importance: str = "medium"


@dataclass
class IntelligenceAction:
    action_id: str
    action_type: str
    title: str
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerIntelligenceResult:
    success: bool
    message: str = ""

    recommended: Optional[CandidatePlan] = None
    top_options: List[CandidatePlan] = field(default_factory=list)
    saved_options: List[CandidatePlan] = field(default_factory=list)
    rejected_summary: List[Dict[str, Any]] = field(default_factory=list)

    option_groups: List[Dict[str, Any]] = field(default_factory=list)
    questions: List[IntelligenceQuestion] = field(default_factory=list)
    actions: List[IntelligenceAction] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# INTELLIGENCE ENGINE
# =============================================================================

class PlannerIntelligence:
    """
    Deep planning-intelligence engine.

    Responsibilities:
    - generate discipline-aware candidate strategies
    - run planner execution for each candidate
    - detect conflicts across disciplines
    - refine candidates across several passes
    - score and rank options
    - produce UI-ready explanations/actions/questions
    - run a GLOBAL EVOLUTION LOOP so later candidates can learn from stronger ones
    """

    def __init__(self) -> None:
        self.planner = importlib.import_module("planner")
        self.saved_options: Dict[str, CandidatePlan] = {}

    # -------------------------------------------------------------------------
    # Public entry points
    # -------------------------------------------------------------------------

    def generate_options(
        self,
        parsed_payload: Dict[str, Any],
        *,
        max_candidates: int = MAX_DEFAULT_CANDIDATES,
        top_k: int = DEFAULT_TOP_OPTIONS,
        extra_preferences: Optional[Dict[str, Any]] = None,
        evolution_rounds: int = DEFAULT_GLOBAL_EVOLUTION_ROUNDS,
    ) -> PlannerIntelligenceResult:
        payload = deepcopy(parsed_payload)
        preferences = deepcopy(extra_preferences) if isinstance(extra_preferences, dict) else {}

        initial_payloads = self._build_candidate_payloads(
            payload,
            max_candidates=max_candidates,
            preferences=preferences,
        )

        evaluated: List[CandidatePlan] = []
        round_records: List[EvolutionRoundRecord] = []

        initial_candidates = self._instantiate_candidates(initial_payloads)
        for candidate in initial_candidates:
            self._evaluate_candidate(candidate, preferences)
            evaluated.append(candidate)

        evaluated.sort(key=lambda c: c.score.total, reverse=True)
        round_records.append(
            EvolutionRoundRecord(
                round_index=0,
                title="Initial Candidate Generation",
                generated_candidate_ids=[c.candidate_id for c in initial_candidates],
                top_score_after_round=evaluated[0].score.total if evaluated else None,
                notes=["Initial candidate strategies evaluated through planner + refinement + scoring."],
            )
        )

        for round_index in range(1, max(1, evolution_rounds) + 1):
            parent_pool = self._select_parent_pool(evaluated, max_parents=2)
            evolved_payloads = self._evolve_from_parents(
                base_payload=payload,
                parents=parent_pool,
                preferences=preferences,
                round_index=round_index,
                max_children=max_candidates,
            )
            if not evolved_payloads:
                round_records.append(
                    EvolutionRoundRecord(
                        round_index=round_index,
                        title=f"Evolution Round {round_index}",
                        selected_parent_ids=[p.candidate_id for p in parent_pool],
                        generated_candidate_ids=[],
                        top_score_after_round=evaluated[0].score.total if evaluated else None,
                        notes=["No useful evolved payloads were generated."],
                    )
                )
                continue

            evolved_candidates = self._instantiate_candidates(evolved_payloads)
            for candidate in evolved_candidates:
                self._evaluate_candidate(candidate, preferences)
                evaluated.append(candidate)

            evaluated.sort(key=lambda c: c.score.total, reverse=True)

            round_records.append(
                EvolutionRoundRecord(
                    round_index=round_index,
                    title=f"Evolution Round {round_index}",
                    selected_parent_ids=[p.candidate_id for p in parent_pool],
                    generated_candidate_ids=[c.candidate_id for c in evolved_candidates],
                    top_score_after_round=evaluated[0].score.total if evaluated else None,
                    notes=["Generated children from best candidates and re-ranked the search pool."],
                )
            )

        evaluated.sort(key=lambda c: c.score.total, reverse=True)
        recommended = evaluated[0] if evaluated else None
        top_options = evaluated[: max(1, min(top_k, len(evaluated)))]
        rejected = evaluated[len(top_options):]

        result = PlannerIntelligenceResult(
            success=bool(top_options),
            message="Generated ranked planning options." if top_options else "No viable planning options were generated.",
            recommended=recommended,
            top_options=top_options,
            rejected_summary=self._build_rejected_summary(rejected),
            option_groups=self._build_option_groups(top_options),
            questions=self._build_questions(payload, recommended, top_options),
            actions=self._build_actions(payload, recommended, top_options, preferences),
            saved_options=self.list_saved_options(),
            metadata={
                "mode": _mode(payload),
                "project_type": _project_type(payload),
                "candidate_count_total": len(evaluated),
                "candidate_count": len(evaluated),
                "requested_top_k": top_k,
                "preferences": deepcopy(preferences),
                "evolution_rounds": evolution_rounds,
                "comparison_summary": self._build_comparison_summary(recommended, top_options),
                "round_records": [
                    {
                        "round_index": r.round_index,
                        "title": r.title,
                        "selected_parent_ids": list(r.selected_parent_ids),
                        "generated_candidate_ids": list(r.generated_candidate_ids),
                        "top_score_after_round": r.top_score_after_round,
                        "notes": list(r.notes),
                    }
                    for r in round_records
                ],
            },
        )
        return result

    def _candidate_component_scores(self, candidate: CandidatePlan) -> Dict[str, float]:
        return {
            "program_fit": _safe_float(candidate.score.program_fit),
            "parking": _safe_float(candidate.score.parking),
            "circulation": _safe_float(candidate.score.circulation),
            "grading": _safe_float(candidate.score.grading),
            "drainage": _safe_float(candidate.score.drainage),
            "pipes": _safe_float(candidate.score.pipes),
            "utilities": _safe_float(candidate.score.utilities),
            "compliance": _safe_float(candidate.score.compliance),
            "constructability": _safe_float(candidate.score.constructability),
            "completeness": _safe_float(candidate.score.completeness),
            "confidence": _safe_float(candidate.score.confidence),
        }

    def _build_comparison_summary(
        self,
        recommended: Optional[CandidatePlan],
        top_options: Sequence[CandidatePlan],
    ) -> Dict[str, Any]:
        if recommended is None:
            return {}

        runner_up = next((option for option in top_options if option.candidate_id != recommended.candidate_id), None)
        if runner_up is None:
            return {
                "recommended_option_name": recommended.option_name,
                "runner_up_option_name": "",
                "score_gap": 0.0,
                "what_got_better": [],
                "what_got_worse": [],
                "why_it_won": list(recommended.pros[:3]),
                "tradeoff_summary": f"{recommended.option_name} is currently the only viable high-ranked option.",
            }

        recommended_scores = self._candidate_component_scores(recommended)
        runner_up_scores = self._candidate_component_scores(runner_up)
        deltas: List[Tuple[str, float, float, float]] = []
        for name, value in recommended_scores.items():
            baseline = _safe_float(runner_up_scores.get(name), 0.0)
            deltas.append((name, round(value - baseline, 2), value, baseline))

        better = [
            {
                "dimension": name,
                "label": _component_label(name),
                "delta": delta,
                "recommended_score": current,
                "runner_up_score": baseline,
            }
            for name, delta, current, baseline in sorted(deltas, key=lambda item: item[1], reverse=True)
            if delta >= 4.0
        ][:3]
        worse = [
            {
                "dimension": name,
                "label": _component_label(name),
                "delta": delta,
                "recommended_score": current,
                "runner_up_score": baseline,
            }
            for name, delta, current, baseline in sorted(deltas, key=lambda item: item[1])
            if delta <= -4.0
        ][:2]

        why_it_won: List[str] = []
        if better:
            why_it_won.append(
                f"It led on {better[0]['label']} by {abs(_safe_float(better[0]['delta'])):.1f} points."
            )
        why_it_won.extend(item for item in recommended.pros[:3] if item and item not in why_it_won)

        better_labels = ", ".join(item["label"] for item in better) if better else "overall balance"
        worse_labels = ", ".join(item["label"] for item in worse) if worse else "no major tradeoff"
        tradeoff_summary = (
            f"{recommended.option_name} beat {runner_up.option_name} by "
            f"{_safe_float(recommended.score.total - runner_up.score.total):.1f} points. "
            f"It was stronger in {better_labels}, while the main tradeoff was {worse_labels}."
        )

        return {
            "recommended_option_name": recommended.option_name,
            "runner_up_option_name": runner_up.option_name,
            "recommended_candidate_id": recommended.candidate_id,
            "runner_up_candidate_id": runner_up.candidate_id,
            "score_gap": round(_safe_float(recommended.score.total - runner_up.score.total), 2),
            "what_got_better": better,
            "what_got_worse": worse,
            "why_it_won": why_it_won,
            "tradeoff_summary": tradeoff_summary,
        }

    def generate_more_options(
        self,
        parsed_payload: Dict[str, Any],
        *,
        existing_option_names: Optional[Sequence[str]] = None,
        max_candidates: int = MAX_DEFAULT_CANDIDATES,
        top_k: int = DEFAULT_TOP_OPTIONS,
        extra_preferences: Optional[Dict[str, Any]] = None,
        evolution_rounds: int = DEFAULT_GLOBAL_EVOLUTION_ROUNDS,
    ) -> PlannerIntelligenceResult:
        preferences = deepcopy(extra_preferences) if isinstance(extra_preferences, dict) else {}
        preferences["prefer_exploration"] = True
        preferences["exclude_option_names"] = list(existing_option_names or [])
        return self.generate_options(
            parsed_payload,
            max_candidates=max_candidates,
            top_k=top_k,
            extra_preferences=preferences,
            evolution_rounds=evolution_rounds,
        )

    def save_option(self, candidate: CandidatePlan) -> CandidatePlan:
        saved = deepcopy(candidate)
        saved.is_saved = True
        if len(self.saved_options) >= DEFAULT_MAX_SAVED_OPTIONS:
            oldest = next(iter(self.saved_options.keys()))
            self.saved_options.pop(oldest, None)
        self.saved_options[saved.candidate_id] = saved
        return deepcopy(saved)

    def list_saved_options(self) -> List[CandidatePlan]:
        return [deepcopy(c) for c in self.saved_options.values()]

    # -------------------------------------------------------------------------
    # Candidate generation
    # -------------------------------------------------------------------------

    def _instantiate_candidates(self, candidate_payloads: Sequence[Dict[str, Any]]) -> List[CandidatePlan]:
        out: List[CandidatePlan] = []
        for idx, candidate_payload in enumerate(candidate_payloads, start=1):
            working = deepcopy(candidate_payload)
            strategy = _safe_dict(working.pop("__strategy__", {}))
            lineage = CandidateLineage(
                candidate_id=_new_id("cand"),
                parent_candidate_id=_safe_str(strategy.get("parent_candidate_id"), "") or None,
                generation=_safe_int(strategy.get("generation"), 0),
                source_family=_safe_str(strategy.get("strategy_family"), "generic"),
                source_strategy=_safe_str(strategy.get("strategy_name"), "generic"),
            )
            option_name = _safe_str(strategy.get("option_name"), f"Option {idx}")
            out.append(
                CandidatePlan(
                    candidate_id=lineage.candidate_id,
                    option_name=option_name,
                    strategy=strategy,
                    payload=deepcopy(working),
                    lineage=lineage,
                    option_family=_safe_str(strategy.get("strategy_family"), "generic"),
                )
            )
        return out

    def _build_candidate_payloads(
        self,
        payload: Dict[str, Any],
        *,
        max_candidates: int,
        preferences: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        mode = _mode(payload)

        if mode == "site_plan":
            strategies = self._site_plan_strategies(payload, preferences)
        elif mode == "drainage":
            strategies = self._drainage_strategies(payload, preferences)
        elif mode == "road":
            strategies = self._road_strategies(payload, preferences)
        elif mode == "subdivision":
            strategies = self._subdivision_strategies(payload, preferences)
        elif mode == "bridge":
            strategies = self._bridge_strategies(payload, preferences)
        elif mode == "pool":
            strategies = self._pool_strategies(payload, preferences)
        else:
            strategies = self._generic_strategies(payload, preferences)

        exclude_names = {_safe_str(x) for x in _safe_list(preferences.get("exclude_option_names"))}
        out: List[Dict[str, Any]] = []
        for strategy in strategies:
            option_name = _safe_str(strategy.get("option_name"), "Option")
            if option_name in exclude_names:
                continue
            candidate_payload = deepcopy(payload)
            candidate_payload = _deep_merge(candidate_payload, deepcopy(_safe_dict(strategy.get("payload_overrides"))))
            candidate_payload["__strategy__"] = deepcopy(strategy)
            out.append(candidate_payload)
            if len(out) >= max_candidates:
                break
        return out

    def _site_plan_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        project_type = _project_type(payload)
        existing_strategy = _lower(payload.get("layout_strategy") or "")
        site_plan = deepcopy(_safe_dict(payload.get("site_plan")))
        parking_target = _safe_int(site_plan.get("parking_count"), 0)
        omit_parking = _is_omitted(payload, "site_plan.parking_count")
        omit_drainage = _is_omitted(payload, "drainage")
        omit_utilities = _is_omitted(payload, "utility_network")
        lot = _lot(payload)
        lot_area = lot["w"] * lot["h"]

        base: List[Tuple[str, str, str, Dict[str, Any]]] = [
            (
                "front_parking",
                "Best Front Parking",
                "Strong default access and familiar frontage behavior.",
                {
                    "layout_intent": "front_loaded",
                    "parking_intent": "maximize_front_access",
                    "circulation_intent": "simple",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "balanced",
                },
            ),
            (
                "rear_parking",
                "Balanced Rear Parking",
                "Cleaner frontage and stronger building presence.",
                {
                    "layout_intent": "rear_loaded",
                    "parking_intent": "rear_oriented",
                    "circulation_intent": "balanced",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "balanced",
                },
            ),
            (
                "side_parking",
                "Side Parking Efficiency",
                "Preserves frontage while keeping parking compact.",
                {
                    "layout_intent": "side_loaded",
                    "parking_intent": "compact_efficiency",
                    "circulation_intent": "short_walk_paths",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "balanced",
                },
            ),
            (
                "street_building",
                "Street-Oriented Layout",
                "Pushes the building toward frontage and de-emphasizes front pavement.",
                {
                    "layout_intent": "street_edge",
                    "parking_intent": "defer_front_parking",
                    "circulation_intent": "building_first",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "balanced",
                },
            ),
            (
                "yield_max",
                "Yield Max Option",
                "Biases the concept toward program fit and parking quantity.",
                {
                    "layout_intent": "yield_max",
                    "parking_intent": "maximize_count",
                    "circulation_intent": "aggressive",
                    "grading_intent": "acceptable_tradeoff",
                    "drainage_intent": "acceptable_tradeoff",
                    "utility_intent": "acceptable_tradeoff",
                },
            ),
            (
                "grading_friendly",
                "Grading-Friendly Option",
                "Biases toward lower grading burden and cleaner surfaces.",
                {
                    "layout_intent": "grading_friendly",
                    "parking_intent": "balanced",
                    "circulation_intent": "balanced",
                    "grading_intent": "minimize_regrade",
                    "drainage_intent": "supportive",
                    "utility_intent": "balanced",
                },
            ),
            (
                "drainage_friendly",
                "Drainage-Friendly Option",
                "Biases toward clearer outfall organization and basin support.",
                {
                    "layout_intent": "drainage_friendly",
                    "parking_intent": "balanced",
                    "circulation_intent": "balanced",
                    "grading_intent": "supportive",
                    "drainage_intent": "maximize_clarity",
                    "utility_intent": "balanced",
                },
            ),
            (
                "utility_efficient",
                "Utility-Efficient Option",
                "Biases toward shorter utility and coordinated service runs.",
                {
                    "layout_intent": "utility_efficient",
                    "parking_intent": "balanced",
                    "circulation_intent": "balanced",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "shorter_runs",
                },
            ),
            (
                "balanced",
                "Balanced Option",
                "Attempts the best overall tradeoff between program, grading, drainage, utilities, and compliance.",
                {
                    "layout_intent": "balanced",
                    "parking_intent": "balanced",
                    "circulation_intent": "balanced",
                    "grading_intent": "balanced",
                    "drainage_intent": "balanced",
                    "utility_intent": "balanced",
                },
            ),
        ]

        if project_type in {"multifamily_site", "strip_center"} or lot_area > 100000.0:
            base.extend(
                [
                    (
                        "building_courts",
                        "Courtyard Option",
                        "Tests richer building/parking relationships and internal organization.",
                        {
                            "layout_intent": "courtyard",
                            "parking_intent": "distributed",
                            "circulation_intent": "internalized",
                            "grading_intent": "balanced",
                            "drainage_intent": "balanced",
                            "utility_intent": "balanced",
                        },
                    ),
                    (
                        "double_loaded_court",
                        "Double-Loaded Court",
                        "Tests denser parking and a more compact internal circulation pattern.",
                        {
                            "layout_intent": "double_loaded",
                            "parking_intent": "dense",
                            "circulation_intent": "court",
                            "grading_intent": "balanced",
                            "drainage_intent": "balanced",
                            "utility_intent": "balanced",
                        },
                    ),
                ]
            )

        if omit_parking:
            base = [x for x in base if x[0] not in {"front_parking", "rear_parking", "side_parking", "yield_max", "double_loaded_court"}]
        if omit_drainage:
            base = [x for x in base if x[0] != "drainage_friendly"]
        if omit_utilities:
            base = [x for x in base if x[0] != "utility_efficient"]

        if existing_strategy and existing_strategy in SITE_LAYOUT_STRATEGIES:
            base.insert(
                0,
                (
                    existing_strategy,
                    f"User-Hinted {existing_strategy.replace('_', ' ').title()}",
                    "Respects the user’s hinted layout strategy.",
                    {
                        "layout_intent": existing_strategy,
                        "parking_intent": "user_hint",
                        "circulation_intent": "user_hint",
                        "grading_intent": "balanced",
                        "drainage_intent": "balanced",
                        "utility_intent": "balanced",
                    },
                ),
            )

        prefer_goal = _lower(preferences.get("goal"))
        if prefer_goal in {"maximize_parking", "more_parking"}:
            base.insert(
                0,
                (
                    "yield_max",
                    "Parking-Optimized Option",
                    "Exploration biased toward higher parking yield.",
                    {
                        "layout_intent": "yield_max",
                        "parking_intent": "maximize_count",
                        "circulation_intent": "acceptable_tradeoff",
                        "grading_intent": "acceptable_tradeoff",
                        "drainage_intent": "acceptable_tradeoff",
                        "utility_intent": "acceptable_tradeoff",
                    },
                ),
            )
        elif prefer_goal in {"reduce_grading", "less_grading"}:
            base.insert(
                0,
                (
                    "grading_friendly",
                    "Low-Grading Option",
                    "Exploration biased toward lower grading burden.",
                    {
                        "layout_intent": "grading_friendly",
                        "parking_intent": "balanced",
                        "circulation_intent": "balanced",
                        "grading_intent": "minimize_regrade",
                        "drainage_intent": "supportive",
                        "utility_intent": "balanced",
                    },
                ),
            )
        elif prefer_goal in {"improve_drainage", "better_drainage"}:
            base.insert(
                0,
                (
                    "drainage_friendly",
                    "Drainage-Optimized Option",
                    "Exploration biased toward cleaner drainage/outfall organization.",
                    {
                        "layout_intent": "drainage_friendly",
                        "parking_intent": "balanced",
                        "circulation_intent": "balanced",
                        "grading_intent": "supportive",
                        "drainage_intent": "maximize_clarity",
                        "utility_intent": "balanced",
                    },
                ),
            )
        elif prefer_goal in {"reduce_pipe_length", "shorter_pipe", "pipe_efficiency"}:
            base.insert(
                0,
                (
                    "utility_efficient",
                    "Pipe-Efficient Option",
                    "Exploration biased toward shorter combined pipe and utility runs.",
                    {
                        "layout_intent": "utility_efficient",
                        "parking_intent": "balanced",
                        "circulation_intent": "balanced",
                        "grading_intent": "balanced",
                        "drainage_intent": "balanced",
                        "utility_intent": "shorter_runs",
                    },
                ),
            )
        elif prefer_goal in {"balance_earthwork", "balance_cut_fill", "reduce_earthwork"}:
            base.insert(
                0,
                (
                    "grading_friendly",
                    "Earthwork-Balanced Option",
                    "Exploration biased toward smoother grading and lower net cut/fill imbalance.",
                    {
                        "layout_intent": "grading_friendly",
                        "parking_intent": "balanced",
                        "circulation_intent": "balanced",
                        "grading_intent": "minimize_regrade",
                        "drainage_intent": "supportive",
                        "utility_intent": "balanced",
                    },
                ),
            )

        out: List[Dict[str, Any]] = []
        for idx, (layout_strategy, option_name, summary, strategy_pack) in enumerate(_dedupe_keep_order(base), start=1):
            site_plan_override = deepcopy(site_plan)
            if parking_target > 0:
                if layout_strategy in {"yield_max", "front_parking", "double_loaded_court"}:
                    site_plan_override["parking_count"] = max(parking_target, int(round(parking_target * 1.08)))
                elif layout_strategy in {"street_building", "grading_friendly"}:
                    site_plan_override["parking_count"] = max(1, int(round(parking_target * 0.95)))

            out.append(
                {
                    "option_name": option_name,
                    "summary": summary,
                    "strategy_family": "site_layout",
                    "strategy_name": layout_strategy,
                    "payload_overrides": {
                        "layout_strategy": layout_strategy,
                        "site_plan": site_plan_override,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "site_layout",
                            "strategy_name": layout_strategy,
                            "strategy_pack": strategy_pack,
                        },
                    },
                }
            )
        return out

    def _drainage_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        drainage = deepcopy(_safe_dict(payload.get("drainage")))
        hint = _lower(drainage.get("outfall_side") or payload.get("street_edge") or "bottom")
        sides = _dedupe_keep_order([hint, "bottom", "top", "left", "right"])

        out: List[Dict[str, Any]] = []
        for idx, side in enumerate(sides, start=1):
            d = deepcopy(drainage)
            d["outfall_side"] = side
            out.append(
                {
                    "option_name": f"Drainage to {side.title()}",
                    "summary": f"Routes concept drainage toward the {side} outfall side.",
                    "strategy_family": "drainage",
                    "strategy_name": f"outfall_{side}",
                    "payload_overrides": {
                        "drainage": d,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "drainage",
                            "strategy_name": f"outfall_{side}",
                            "strategy_pack": {
                                "drainage_intent": "clear_outfall",
                                "outfall_side": side,
                            },
                        },
                    },
                }
            )
        return out

    def _road_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        road = deepcopy(_safe_dict(payload.get("road")))
        widths = _dedupe_keep_order([road.get("lane_width") or 12.0, 11.0, 12.0, 13.0])

        out: List[Dict[str, Any]] = []
        for idx, lane_width in enumerate(widths, start=1):
            rd = deepcopy(road)
            rd["lane_width"] = lane_width
            out.append(
                {
                    "option_name": f"Roadway Lane {lane_width:.1f}",
                    "summary": "Tests corridor proportion and lane sizing assumptions.",
                    "strategy_family": "road",
                    "strategy_name": f"lane_{lane_width:.1f}",
                    "payload_overrides": {
                        "road": rd,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "road",
                            "strategy_name": f"lane_{lane_width:.1f}",
                            "strategy_pack": {
                                "road_intent": "balanced_corridor",
                                "lane_width": lane_width,
                            },
                        },
                    },
                }
            )
        return out

    def _subdivision_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        subdivision = deepcopy(_safe_dict(payload.get("subdivision")))
        road_width = _safe_float(subdivision.get("road_width"), 28.0)
        lot_count = _safe_int(subdivision.get("lot_count"), 20)

        candidates = [
            (road_width, lot_count, "Balanced Subdivision", "Balanced roadway and lot yield assumptions."),
            (road_width + 2.0, max(8, lot_count - 2), "Wider Roadway", "Trades some yield for broader roadway section."),
            (max(24.0, road_width - 2.0), lot_count + 2, "Yield Leaning", "Tests slightly tighter roadway for more lots."),
        ]

        out: List[Dict[str, Any]] = []
        for idx, (rw, lc, name, summary) in enumerate(candidates, start=1):
            sd = deepcopy(subdivision)
            sd["road_width"] = rw
            sd["lot_count"] = lc
            out.append(
                {
                    "option_name": name,
                    "summary": summary,
                    "strategy_family": "subdivision",
                    "strategy_name": name.lower().replace(" ", "_"),
                    "payload_overrides": {
                        "subdivision": sd,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "subdivision",
                            "strategy_name": name.lower().replace(" ", "_"),
                            "strategy_pack": {
                                "subdivision_intent": name.lower().replace(" ", "_"),
                                "road_width": rw,
                                "lot_count": lc,
                            },
                        },
                    },
                }
            )
        return out

    def _bridge_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        bridge = deepcopy(_safe_dict(payload.get("bridge")))
        span_count = _safe_int(bridge.get("span_count"), 2)
        deck_width = _safe_float(bridge.get("deck_width"), 30.0)

        variants = [
            (span_count, deck_width, "Balanced Bridge", "Balanced bridge geometry assumptions."),
            (max(1, span_count + 1), deck_width, "More Spans", "Tests shorter spans with more supports."),
            (span_count, deck_width + 4.0, "Wider Deck", "Tests increased deck width."),
        ]

        out: List[Dict[str, Any]] = []
        for idx, (sc, dw, name, summary) in enumerate(variants, start=1):
            bg = deepcopy(bridge)
            bg["span_count"] = sc
            bg["deck_width"] = dw
            out.append(
                {
                    "option_name": name,
                    "summary": summary,
                    "strategy_family": "bridge",
                    "strategy_name": name.lower().replace(" ", "_"),
                    "payload_overrides": {
                        "bridge": bg,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "bridge",
                            "strategy_name": name.lower().replace(" ", "_"),
                            "strategy_pack": {
                                "bridge_intent": name.lower().replace(" ", "_"),
                                "span_count": sc,
                                "deck_width": dw,
                            },
                        },
                    },
                }
            )
        return out

    def _pool_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        pool = deepcopy(_safe_dict(payload.get("pool")))
        pool_length = _safe_float(pool.get("pool_length"), 40.0)
        pool_width = _safe_float(pool.get("pool_width"), 20.0)

        variants = [
            (pool_length, pool_width, "Balanced Pool", "Balanced recreational pool geometry."),
            (pool_length + 10.0, pool_width, "Longer Pool", "Tests a longer lap-friendly pool."),
            (pool_length, pool_width + 6.0, "Wider Pool", "Tests a wider amenity-focused pool."),
        ]

        out: List[Dict[str, Any]] = []
        for idx, (pl, pw, name, summary) in enumerate(variants, start=1):
            p = deepcopy(pool)
            p["pool_length"] = pl
            p["pool_width"] = pw
            out.append(
                {
                    "option_name": name,
                    "summary": summary,
                    "strategy_family": "pool",
                    "strategy_name": name.lower().replace(" ", "_"),
                    "payload_overrides": {
                        "pool": p,
                        "meta": {
                            "intelligence_candidate": idx,
                            "strategy_family": "pool",
                            "strategy_name": name.lower().replace(" ", "_"),
                            "strategy_pack": {
                                "pool_intent": name.lower().replace(" ", "_"),
                                "pool_length": pl,
                                "pool_width": pw,
                            },
                        },
                    },
                }
            )
        return out

    def _generic_strategies(self, payload: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "option_name": "Balanced Generic Option",
                "summary": "General balanced strategy for non-specialized requests.",
                "strategy_family": "generic",
                "strategy_name": "balanced_generic",
                "payload_overrides": {
                    "meta": {
                        "intelligence_candidate": 1,
                        "strategy_family": "generic",
                        "strategy_name": "balanced_generic",
                        "strategy_pack": {"generic_intent": "balanced"},
                    },
                },
            }
        ]

    # -------------------------------------------------------------------------
    # Global evolution
    # -------------------------------------------------------------------------

    def _select_parent_pool(self, candidates: Sequence[CandidatePlan], max_parents: int = 2) -> List[CandidatePlan]:
        ranked = sorted(candidates, key=lambda c: c.score.total, reverse=True)
        return [deepcopy(c) for c in ranked[:max(1, min(max_parents, len(ranked)))]]

    def _evolve_from_parents(
        self,
        base_payload: Dict[str, Any],
        parents: Sequence[CandidatePlan],
        preferences: Dict[str, Any],
        round_index: int,
        max_children: int,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for parent_idx, parent in enumerate(parents, start=1):
            child_specs = self._build_child_strategies_from_parent(parent, preferences, round_index)
            for child_idx, child_patch in enumerate(child_specs, start=1):
                child_payload = _deep_merge(deepcopy(base_payload), deepcopy(parent.payload))
                child_payload = _deep_merge(child_payload, deepcopy(child_patch))
                strategy_name = _safe_str(_safe_dict(child_patch.get("__strategy__")).get("strategy_name"), f"evolved_{round_index}_{parent_idx}_{child_idx}")
                option_name = _safe_str(_safe_dict(child_patch.get("__strategy__")).get("option_name"), f"Evolved {round_index}.{parent_idx}.{child_idx}")
                child_payload["__strategy__"] = _deep_merge(
                    {
                        "option_name": option_name,
                        "summary": f"Evolved from '{parent.option_name}' in global round {round_index}.",
                        "strategy_family": parent.option_family or "evolved",
                        "strategy_name": strategy_name,
                        "generation": parent.lineage.generation + 1,
                        "parent_candidate_id": parent.candidate_id,
                    },
                    _safe_dict(child_patch.get("__strategy__")),
                )
                out.append(child_payload)
                if len(out) >= max_children:
                    return out
        return out

    def _build_child_strategies_from_parent(
        self,
        parent: CandidatePlan,
        preferences: Dict[str, Any],
        round_index: int,
    ) -> List[Dict[str, Any]]:
        mode = _mode(parent.payload)
        strategy = _safe_str(parent.strategy.get("strategy_name"), "")
        children: List[Dict[str, Any]] = []

        if mode == "site_plan":
            next_layouts = _dedupe_keep_order([
                strategy,
                "balanced",
                "utility_efficient",
                "drainage_friendly",
                "grading_friendly",
                "yield_max",
                "rear_parking",
                "front_parking",
            ])
            for layout in next_layouts[:4]:
                patch: Dict[str, Any] = {
                    "layout_strategy": layout,
                    "__strategy__": {
                        "option_name": f"{parent.option_name} → {layout.replace('_', ' ').title()}",
                        "strategy_family": parent.option_family or "site_layout",
                        "strategy_name": f"evolved_{layout}",
                    },
                }
                site_plan = deepcopy(_safe_dict(parent.payload.get("site_plan")))
                current_parking = _safe_int(site_plan.get("parking_count"), 0)
                if _lower(preferences.get("goal")) in {"maximize_parking", "more_parking"}:
                    site_plan["parking_count"] = max(current_parking, int(round(current_parking * 1.05)) or 8)
                elif _lower(preferences.get("goal")) in {"reduce_grading", "less_grading"} and current_parking > 0:
                    site_plan["parking_count"] = max(1, int(round(current_parking * 0.98)))
                if site_plan:
                    patch["site_plan"] = site_plan
                children.append(patch)

        elif mode == "drainage":
            current_side = _lower(_safe_dict(parent.payload.get("drainage")).get("outfall_side") or "bottom")
            sides = ["bottom", "top", "left", "right"]
            if current_side in sides:
                idx = sides.index(current_side)
                evolved_sides = [current_side, sides[(idx + 1) % 4], sides[(idx + 2) % 4]]
            else:
                evolved_sides = sides[:3]
            for side in evolved_sides:
                children.append({
                    "drainage": _deep_merge(_safe_dict(parent.payload.get("drainage")), {"outfall_side": side}),
                    "__strategy__": {
                        "option_name": f"{parent.option_name} → {side.title()} Outfall",
                        "strategy_family": "drainage",
                        "strategy_name": f"evolved_outfall_{side}",
                    },
                })

        else:
            children.append({
                "__strategy__": {
                    "option_name": f"{parent.option_name} → Refined",
                    "strategy_family": parent.option_family or "generic",
                    "strategy_name": f"evolved_round_{round_index}",
                }
            })

        return children

    # -------------------------------------------------------------------------
    # Evaluation / refinement
    # -------------------------------------------------------------------------

    def _evaluate_candidate(self, candidate: CandidatePlan, preferences: Dict[str, Any]) -> None:
        self._execute_candidate(candidate)
        self._detect_conflicts(candidate)
        self._refine_candidate(candidate, preferences)
        self._score_candidate(candidate, preferences)
        self._explain_candidate(candidate)

    def _execute_candidate(self, candidate: CandidatePlan) -> None:
        payload = deepcopy(candidate.payload)

        try:
            if hasattr(self.planner, "build_plan"):
                finalized = self.planner.build_plan(payload)
            else:
                raise RuntimeError("Planner does not expose build_plan().")

            candidate.plan = deepcopy(finalized)
            candidate.preview_payload = self._build_preview_payload(finalized)
            candidate.assumptions = _safe_list(finalized.get("assumptions"))
            candidate.issues = _qa_issues(finalized)

        except Exception as exc:
            candidate.plan = {
                "project_name": candidate.payload.get("project_name") or candidate.option_name,
                "units": candidate.payload.get("units") or "ft",
                "actions": [],
                "assumptions": list(candidate.assumptions),
                "meta": {
                    "intelligence_layer": True,
                    "candidate_id": candidate.candidate_id,
                    "execution_failed": True,
                    "execution_error": str(exc),
                    "qa": {
                        "warning_count": 0,
                        "error_count": 1,
                        "issues": [
                            {
                                "code": "CANDIDATE_EXECUTION_FAILED",
                                "severity": "error",
                                "message": str(exc),
                                "context": {},
                            }
                        ],
                    },
                },
            }
            candidate.preview_payload = self._build_preview_payload(candidate.plan)
            candidate.issues = _qa_issues(candidate.plan)
            candidate.cons.append(f"Execution failed: {exc}")

    def _detect_conflicts(self, candidate: CandidatePlan) -> None:
        conflicts: List[CandidateConflict] = []

        plan = candidate.plan
        meta = _safe_dict(plan.get("meta"))
        qa_issues = _qa_issues(plan)

        error_count = _error_count(plan)
        warning_count = _warning_count(plan)

        if error_count > 0:
            conflicts.append(
                CandidateConflict(
                    code="QA_ERRORS_PRESENT",
                    severity="critical",
                    message=f"Planner QA reported {error_count} error(s).",
                    details={"error_count": error_count},
                )
            )

        if warning_count >= 5:
            conflicts.append(
                CandidateConflict(
                    code="HEAVY_WARNING_LOAD",
                    severity="warning",
                    message=f"Planner QA reported a heavy warning load ({warning_count}).",
                    details={"warning_count": warning_count},
                )
            )

        coverage = _coverage_ratio(meta)
        if coverage > 1.0:
            conflicts.append(
                CandidateConflict(
                    code="OVERCOVERAGE",
                    severity="critical",
                    message="Estimated developed coverage exceeds lot area.",
                    details={"coverage_ratio": coverage},
                )
            )
        elif coverage > 0.92:
            conflicts.append(
                CandidateConflict(
                    code="TIGHT_COVERAGE",
                    severity="warning",
                    message="Estimated developed coverage is very high for the lot.",
                    details={"coverage_ratio": coverage},
                )
            )

        mode = _mode(candidate.payload)
        if mode in {"site_plan", "drainage", "subdivision"}:
            has_drain = self._has_layer(plan, "DRAIN_FLOW") or self._has_text_containing(plan, "INLET")
            has_pond = self._has_text_containing(plan, "POND") or self._has_layer(plan, "BASIN_BOUNDARY")
            if not has_drain:
                conflicts.append(
                    CandidateConflict(
                        code="DRAINAGE_SIGNAL_WEAK",
                        severity="warning",
                        message="Drainage representation is weak or missing.",
                        details={},
                    )
                )
            if mode in {"drainage", "subdivision"} and not has_pond:
                conflicts.append(
                    CandidateConflict(
                        code="NO_OUTFALL_OR_POND",
                        severity="warning",
                        message="No clear outfall or pond geometry detected.",
                        details={},
                    )
                )

        if mode == "site_plan":
            desired = _safe_int(_safe_dict(candidate.payload.get("site_plan")).get("parking_count"), 0)
            actual = self._infer_parking_count_from_plan(plan)
            if desired > 0 and actual < desired:
                conflicts.append(
                    CandidateConflict(
                        code="PARKING_SHORTFALL",
                        severity="warning",
                        message="Estimated parking appears below target.",
                        details={"desired": desired, "actual": actual},
                    )
                )

        manager_export = _manager_export_meta(plan)
        conflict_counts = _safe_dict(manager_export.get("conflict_counts"))
        if _safe_float(conflict_counts.get("error"), 0.0) > 0:
            conflicts.append(
                CandidateConflict(
                    code="MANAGER_CONFLICT_ERRORS",
                    severity="critical",
                    message="ProjectManager exported unresolved error-level conflicts.",
                    details=deepcopy(conflict_counts),
                )
            )
        elif _safe_float(conflict_counts.get("warning"), 0.0) > 0:
            conflicts.append(
                CandidateConflict(
                    code="MANAGER_CONFLICT_WARNINGS",
                    severity="warning",
                    message="ProjectManager exported warning-level conflicts.",
                    details=deepcopy(conflict_counts),
                )
            )

        pipe_ratio = self._pipe_capacity_ratio(plan)
        if pipe_ratio > 1.0:
            conflicts.append(
                CandidateConflict(
                    code="PIPE_CAPACITY_EXCEEDED",
                    severity="critical",
                    message="Pipe capacity ratio exceeded full-flow capacity.",
                    details={"pipe_max_capacity_ratio": pipe_ratio},
                )
            )
        elif pipe_ratio > 0.95:
            conflicts.append(
                CandidateConflict(
                    code="PIPE_CAPACITY_TIGHT",
                    severity="warning",
                    message="Pipe capacity ratio is near the preferred maximum.",
                    details={"pipe_max_capacity_ratio": pipe_ratio},
                )
            )

        for issue in qa_issues:
            severity = _lower(issue.get("severity"))
            code = _safe_str(issue.get("code"), "QA_ISSUE")
            if severity == "error":
                conflicts.append(
                    CandidateConflict(
                        code=f"QA::{code}",
                        severity="critical",
                        message=_safe_str(issue.get("message"), "Planner QA error."),
                        details=deepcopy(_safe_dict(issue.get("context"))),
                    )
                )

        candidate.conflicts = conflicts

    def _refine_candidate(self, candidate: CandidatePlan, preferences: Dict[str, Any]) -> None:
        best_plan = deepcopy(candidate.plan)
        best_conflicts = deepcopy(candidate.conflicts)
        best_issues = deepcopy(candidate.issues)
        best_assumptions = deepcopy(candidate.assumptions)
        best_preview = deepcopy(candidate.preview_payload)

        baseline_score = self._quick_pre_score(candidate)
        best_score_hint = baseline_score

        for pass_index in range(1, DEFAULT_REFINEMENT_PASSES + 1):
            patch, title, description = self._build_refinement_patch(candidate, preferences, pass_index)
            if not patch:
                break

            original_payload = deepcopy(candidate.payload)
            candidate.payload = _deep_merge(candidate.payload, patch)

            self._execute_candidate(candidate)
            self._detect_conflicts(candidate)
            score_hint = self._quick_pre_score(candidate)

            step = CandidateRefinementStep(
                pass_index=pass_index,
                title=title,
                description=description,
                payload_changes=deepcopy(patch),
                conflict_snapshot=[
                    {
                        "code": c.code,
                        "severity": c.severity,
                        "message": c.message,
                        "details": deepcopy(c.details),
                    }
                    for c in candidate.conflicts
                ],
                score_after_pass=score_hint,
            )
            candidate.refinements.append(step)

            if score_hint >= best_score_hint:
                best_score_hint = score_hint
                best_plan = deepcopy(candidate.plan)
                best_conflicts = deepcopy(candidate.conflicts)
                best_issues = deepcopy(candidate.issues)
                best_assumptions = deepcopy(candidate.assumptions)
                best_preview = deepcopy(candidate.preview_payload)
            else:
                candidate.payload = original_payload
                candidate.plan = deepcopy(best_plan)
                candidate.conflicts = deepcopy(best_conflicts)
                candidate.issues = deepcopy(best_issues)
                candidate.assumptions = deepcopy(best_assumptions)
                candidate.preview_payload = deepcopy(best_preview)

        candidate.plan = deepcopy(best_plan)
        candidate.conflicts = deepcopy(best_conflicts)
        candidate.issues = deepcopy(best_issues)
        candidate.assumptions = deepcopy(best_assumptions)
        candidate.preview_payload = deepcopy(best_preview)

    def _build_refinement_patch(
        self,
        candidate: CandidatePlan,
        preferences: Dict[str, Any],
        pass_index: int,
    ) -> Tuple[Dict[str, Any], str, str]:
        mode = _mode(candidate.payload)
        conflicts = {c.code: c for c in candidate.conflicts}
        strategy_name = _safe_str(candidate.strategy.get("strategy_name"), "")

        patch: Dict[str, Any] = {}
        omit_parking = _is_omitted(candidate.payload, "site_plan.parking_count")
        omit_drainage = _is_omitted(candidate.payload, "drainage")
        omit_utilities = _is_omitted(candidate.payload, "utility_network")

        if pass_index == 1:
            if (not omit_parking) and mode == "site_plan" and "PARKING_SHORTFALL" in conflicts:
                site_plan = deepcopy(_safe_dict(candidate.payload.get("site_plan")))
                current = _safe_int(site_plan.get("parking_count"), 0)
                if current > 0:
                    site_plan["parking_count"] = max(current, int(round(current * 1.08)))
                patch["site_plan"] = site_plan
                if strategy_name in {"street_building", "grading_friendly"}:
                    patch["layout_strategy"] = "front_parking"
                return patch, "Program Fit Adjustment", "Adjusted parking target/strategy to improve program fit."

            if "OVERCOVERAGE" in conflicts:
                if mode == "site_plan":
                    patch["layout_strategy"] = "grading_friendly" if strategy_name != "grading_friendly" else "rear_parking"
                    return patch, "Coverage Relief", "Shifted toward a lower-coverage strategy."
                if mode == "subdivision":
                    sd = deepcopy(_safe_dict(candidate.payload.get("subdivision")))
                    lc = _safe_int(sd.get("lot_count"), 0)
                    if lc > 0:
                        sd["lot_count"] = max(1, lc - 1)
                    patch["subdivision"] = sd
                    return patch, "Subdivision Relief", "Reduced lot intensity slightly to relieve overcoverage."

        if pass_index == 2:
            if (not omit_drainage) and mode in {"site_plan", "drainage", "subdivision"} and ("DRAINAGE_SIGNAL_WEAK" in conflicts or "NO_OUTFALL_OR_POND" in conflicts):
                drainage = deepcopy(_safe_dict(candidate.payload.get("drainage")))
                current_inlets = _safe_int(drainage.get("inlet_count"), 0)
                current_ponds = _safe_int(drainage.get("pond_count"), 0)
                drainage["inlet_count"] = max(4, current_inlets + 2)
                drainage["pond_count"] = max(1, current_ponds)
                patch["drainage"] = drainage
                return patch, "Drainage Reinforcement", "Increased concept drainage structure support."

            if mode == "site_plan":
                patch["meta"] = {
                    "intelligence_refinement": {
                        "grading_bias": "reduced_regrade",
                        "drainage_bias": "clearer_outfall",
                        "utility_bias": "shorter_runs",
                    }
                }
                if omit_utilities:
                    patch.setdefault("meta", {}).setdefault("intelligence_refinement", {}).pop("utility_bias", None)
                if omit_drainage:
                    patch.setdefault("meta", {}).setdefault("intelligence_refinement", {}).pop("drainage_bias", None)
                return patch, "Surface Coordination", "Added stronger grading/drainage/utility refinement bias."

        if pass_index == 3:
            goal = _lower(preferences.get("goal"))
            if goal in {"maximize_parking", "more_parking"} and mode == "site_plan":
                patch["layout_strategy"] = "yield_max"
                return patch, "Goal Bias: More Parking", "Shifted candidate toward parking-heavy exploration."
            if goal in {"reduce_grading", "less_grading"} and mode == "site_plan":
                patch["layout_strategy"] = "grading_friendly"
                return patch, "Goal Bias: Less Grading", "Shifted candidate toward grading-friendly exploration."
            if goal in {"improve_drainage", "better_drainage"} and mode == "site_plan":
                patch["layout_strategy"] = "drainage_friendly"
                return patch, "Goal Bias: Better Drainage", "Shifted candidate toward drainage-friendly exploration."
            if mode == "drainage":
                drainage = deepcopy(_safe_dict(candidate.payload.get("drainage")))
                outfall = _lower(drainage.get("outfall_side") or "bottom")
                sides = ["bottom", "top", "left", "right"]
                next_side = sides[(sides.index(outfall) + 1) % len(sides)] if outfall in sides else "bottom"
                drainage["outfall_side"] = next_side
                patch["drainage"] = drainage
                return patch, "Outfall Alternative", "Explored an alternate outfall direction."

        return {}, "", ""

    def _quick_pre_score(self, candidate: CandidatePlan) -> float:
        warning_penalty = _warning_count(candidate.plan) * 10.0
        error_penalty = _error_count(candidate.plan) * 60.0
        conflict_penalty = 0.0
        for conflict in candidate.conflicts:
            if conflict.severity == "critical":
                conflict_penalty += 75.0
            elif conflict.severity == "warning":
                conflict_penalty += 20.0
        action_bonus = len(_safe_list(candidate.plan.get("actions"))) * 0.02
        planner_score = _safe_float(_planner_score_meta(candidate.plan).get("total"), 0.0)
        return action_bonus + planner_score * 0.05 - warning_penalty - error_penalty - conflict_penalty

    # -------------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------------

    def _score_candidate(self, candidate: CandidatePlan, preferences: Dict[str, Any]) -> None:
        score = CandidateScore()
        plan = candidate.plan
        mode = _mode(candidate.payload)

        warnings = _warning_count(plan)
        errors = _error_count(plan)
        conflicts = candidate.conflicts
        omit_parking = _is_omitted(candidate.payload, "site_plan.parking_count")
        omit_drainage = _is_omitted(candidate.payload, "drainage")
        omit_utilities = _is_omitted(candidate.payload, "utility_network")

        score.program_fit = self._score_program_fit(candidate)
        score.parking = self._score_parking(candidate)
        score.circulation = self._score_circulation(candidate)
        score.grading = self._score_grading(candidate)
        score.drainage = self._score_drainage(candidate)
        score.pipes = self._score_pipes(candidate)
        score.utilities = self._score_utilities(candidate)

        score.compliance = max(0.0, 100.0 - (warnings * 6.0 + errors * 30.0))
        critical_conflicts = sum(1 for c in conflicts if c.severity == "critical")
        warning_conflicts = sum(1 for c in conflicts if c.severity == "warning")
        if critical_conflicts:
            score.compliance = max(0.0, score.compliance - critical_conflicts * 18.0)
        if warning_conflicts:
            score.compliance = max(0.0, score.compliance - warning_conflicts * 3.0)

        score.constructability = self._score_constructability(candidate)
        score.completeness = self._score_completeness(candidate)
        score.confidence = self._score_confidence(candidate)

        if errors > 0:
            score.penalties["planner_errors"] = errors * 200.0
        if warnings > 0:
            score.penalties["planner_warnings"] = warnings * 18.0
        if omit_parking:
            score.bonuses["omit_respected_parking"] = 8.0
        if omit_drainage:
            score.bonuses["omit_respected_drainage"] = 8.0
        if omit_utilities:
            score.bonuses["omit_respected_utilities"] = 8.0

        for conflict in conflicts:
            if conflict.severity == "critical":
                score.penalties[f"critical::{conflict.code}"] = score.penalties.get(f"critical::{conflict.code}", 0.0) + 65.0
            elif conflict.severity == "warning":
                score.penalties[f"warning::{conflict.code}"] = score.penalties.get(f"warning::{conflict.code}", 0.0) + 15.0

        planner_score_total = _safe_float(_planner_score_meta(plan).get("total"), 0.0)
        if planner_score_total > 0:
            score.bonuses["planner_score_alignment"] = planner_score_total * 0.15

        optimization = _optimization_meta(plan)
        optimization_scores = _safe_dict(optimization.get("component_scores"))
        optimization_metrics = _safe_dict(optimization.get("metrics"))
        optimization_overall = _safe_float(optimization.get("overall_score"), 0.0)
        if optimization_overall > 0:
            score.bonuses["optimization_alignment"] = optimization_overall * 0.08

        if len(candidate.refinements) >= 2:
            score.bonuses["refinement_depth"] = 6.0
        if warnings == 0 and errors == 0:
            score.bonuses["clean_qa"] = 12.0

        goal = _lower(preferences.get("goal"))
        if goal in {"maximize_parking", "more_parking"}:
            score.bonuses["goal_match"] = max(
                score.parking * 0.10,
                _safe_float(optimization_scores.get("parking_fit"), 0.0) * 0.10,
            )
        elif goal in {"reduce_grading", "less_grading"}:
            score.bonuses["goal_match"] = max(
                score.grading * 0.10,
                _safe_float(optimization_scores.get("earthwork_balance"), 0.0) * 0.10,
            )
        elif goal in {"improve_drainage", "better_drainage"}:
            score.bonuses["goal_match"] = max(
                score.drainage * 0.10,
                _safe_float(optimization_scores.get("drainage_capacity"), 0.0) * 0.10,
            )
        elif goal in {"reduce_pipe_length", "shorter_pipe", "pipe_efficiency"}:
            score.bonuses["goal_match"] = _safe_float(optimization_scores.get("pipe_efficiency"), 0.0) * 0.12
        elif goal in {"balance_earthwork", "balance_cut_fill", "reduce_earthwork"}:
            score.bonuses["goal_match"] = _safe_float(optimization_scores.get("earthwork_balance"), 0.0) * 0.12
        elif goal in {"improve_utilities", "utility_efficiency", "reduce_utility_conflicts"}:
            score.bonuses["goal_match"] = _safe_float(optimization_scores.get("utility_efficiency"), 0.0) * 0.12

        max_capacity_ratio = _safe_float(optimization_metrics.get("max_capacity_ratio"), 0.0)
        if max_capacity_ratio > 1.0:
            score.penalties["optimization_capacity_overflow"] = (max_capacity_ratio - 1.0) * 45.0
        linear_density = _safe_float(optimization_metrics.get("normalized_linear_density"), 0.0)
        if linear_density > 18.0:
            score.penalties["optimization_linear_density"] = min((linear_density - 18.0) * 1.8, 30.0)

        weighted_positive = 0.0
        component_map = {
            "program_fit": score.program_fit,
            "parking": score.parking,
            "circulation": score.circulation,
            "grading": score.grading,
            "drainage": score.drainage,
            "pipes": score.pipes,
            "utilities": score.utilities,
            "compliance": score.compliance,
            "constructability": score.constructability,
            "completeness": score.completeness,
            "confidence": score.confidence,
        }

        for name, value in component_map.items():
            weighted = value * DEFAULT_SCORE_WEIGHTS.get(name, 1.0)
            score.weighted_components[name] = round(weighted, 3)
            weighted_positive += weighted

        total_penalty = sum(score.penalties.values())
        total_bonus = sum(score.bonuses.values())

        score.total = round(weighted_positive + total_bonus - total_penalty, 2)

        if score.total < MIN_ACCEPTABLE_SCORE:
            score.notes.append("Candidate fell well below acceptable score threshold.")
        if mode == "site_plan" and score.parking >= 80:
            score.notes.append("Strong site-program alignment for parking.")
        if score.drainage >= 60:
            score.notes.append("Drainage representation and support are comparatively strong.")
        if score.grading >= 50:
            score.notes.append("Grading/surface signal is stronger than a minimal concept.")
        if score.utilities >= 50:
            score.notes.append("Utility coordination signal is stronger than a minimal concept.")
        if candidate.refinements:
            score.notes.append(f"Refined across {len(candidate.refinements)} pass(es).")

        candidate.score = score

    def _score_program_fit(self, candidate: CandidatePlan) -> float:
        payload = candidate.payload
        mode = _mode(payload)

        if mode == "site_plan":
            lot_area = _lot_area(payload)
            if lot_area <= 0.0:
                return 20.0
            building_area = self._estimate_building_area(candidate.plan)
            if building_area <= 0.0:
                return 20.0
            ratio = building_area / max(lot_area, 1.0)
            if 0.08 <= ratio <= 0.45:
                return 80.0
            if ratio <= 0.60:
                return 60.0
            return 35.0

        if mode in {"bridge", "pool", "road", "subdivision", "drainage"}:
            return 65.0

        return 50.0

    def _score_parking(self, candidate: CandidatePlan) -> float:
        payload = candidate.payload
        if _mode(payload) != "site_plan":
            return 0.0

        desired = _safe_int(_safe_dict(payload.get("site_plan")).get("parking_count"), 0)
        actual = self._infer_parking_count_from_plan(candidate.plan)

        if desired > 0:
            ratio = min(actual / max(desired, 1), 1.10)
            return max(0.0, min(100.0, ratio * 100.0))
        if actual > 0:
            return min(85.0, actual * 2.0)
        return 10.0

    def _score_circulation(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        coverage = _coverage_ratio(_safe_dict(plan.get("meta")))
        strategy_name = _safe_str(candidate.strategy.get("strategy_name"), "")

        score = 35.0
        if 0.35 <= coverage <= 0.88:
            score += 25.0
        elif coverage <= 1.0:
            score += 10.0

        if strategy_name in {"front_parking", "rear_parking", "side_parking", "street_building"}:
            score += 12.0
        if self._has_layer(plan, "ROAD"):
            score += 8.0
        if self._has_layer(plan, "WALK"):
            score += 10.0

        return max(0.0, min(100.0, score))

    def _score_grading(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        score = 10.0
        if self._has_layer(plan, "FG_CONTOUR") or self._has_layer(plan, "SURFACE"):
            score += 35.0
        if self._has_layer(plan, "SPOT_FG") or self._has_text_containing(plan, "FG "):
            score += 15.0
        manager_metrics = _safe_dict(_manager_export_meta(plan).get("metrics"))
        earthwork_net = _safe_float(_safe_dict(manager_metrics.get("earthwork_net_cf")).get("value"), 0.0)
        if earthwork_net != 0.0:
            score += max(0.0, 15.0 - min(abs(earthwork_net) / 1500.0, 15.0))
        if any(c.code == "OVERCOVERAGE" for c in candidate.conflicts):
            score -= 10.0
        if any(c.code == "HEAVY_WARNING_LOAD" for c in candidate.conflicts):
            score -= 8.0
        return max(0.0, min(100.0, score))

    def _score_drainage(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        mode = _mode(candidate.payload)
        if mode not in {"site_plan", "drainage", "subdivision"}:
            return 0.0

        score = 10.0
        has_drain = self._has_layer(plan, "DRAIN_FLOW") or self._has_text_containing(plan, "INLET")
        has_pond = self._has_text_containing(plan, "POND") or self._has_layer(plan, "BASIN_BOUNDARY")
        if has_drain:
            score += 35.0
        if has_pond:
            score += 20.0
        if has_drain and has_pond:
            score += 10.0
        manager_metrics = _safe_dict(_manager_export_meta(plan).get("metrics"))
        low_points = _safe_float(_safe_dict(manager_metrics.get("drainage_low_point_count")).get("value"), 0.0)
        if low_points > 0:
            score += min(15.0, low_points * 1.5)
        if any(c.code == "DRAINAGE_SIGNAL_WEAK" for c in candidate.conflicts):
            score -= 15.0
        return max(0.0, min(100.0, score))

    def _score_pipes(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        score = 0.0
        meta = _safe_dict(plan.get("meta"))
        qa = _safe_dict(meta.get("qa"))
        stats = _safe_dict(qa.get("stats"))
        pipe_length = _safe_float(stats.get("estimated_pipe_length_ft"), 0.0)
        if self._has_layer(plan, "PIPE"):
            score += 30.0
        if pipe_length > 0:
            score += min(25.0, pipe_length / 30.0)
        if self._has_text_containing(plan, '"') or self._has_text_containing(plan, "P-"):
            score += 10.0
        pipe_ratio = self._pipe_capacity_ratio(plan)
        if 0.0 < pipe_ratio <= 0.95:
            score += 20.0
        elif pipe_ratio <= 1.0:
            score += 8.0
        return max(0.0, min(100.0, score))

    def _score_utilities(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        meta = _safe_dict(plan.get("meta"))
        qa = _safe_dict(meta.get("qa"))
        stats = _safe_dict(qa.get("stats"))

        utility_length = _safe_float(stats.get("estimated_utility_length_ft"), 0.0)
        score = 5.0
        if self._has_layer(plan, "UTILITY") or self._has_layer(plan, "WATER") or self._has_layer(plan, "SAN"):
            score += 35.0
        if utility_length > 0:
            score += min(20.0, utility_length / 40.0)
        if self._has_text_containing(plan, "UTILITY") or self._has_text_containing(plan, "WATER") or self._has_text_containing(plan, "SAN"):
            score += 10.0
        manager_metrics = _safe_dict(_manager_export_meta(plan).get("metrics"))
        route_count = _safe_float(_safe_dict(manager_metrics.get("utility_route_count")).get("value"), 0.0)
        if route_count > 0:
            score += min(15.0, route_count * 4.0)
        return max(0.0, min(100.0, score))

    def _score_constructability(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        score = 25.0
        if len(_safe_list(plan.get("actions"))) > 10:
            score += 10.0
        if self._has_layer(plan, "BUILDING") or self._has_layer(plan, "STRUCTURE"):
            score += 12.0
        if self._has_layer(plan, "ROAD") or self._has_layer(plan, "PAVEMENT"):
            score += 10.0
        if len(candidate.conflicts) <= 2:
            score += 10.0
        if _safe_float(_safe_dict(_planner_score_meta(plan)).get("total"), 0.0) > 0:
            score += 5.0
        return max(0.0, min(100.0, score))

    def _score_completeness(self, candidate: CandidatePlan) -> float:
        plan = candidate.plan
        mode = _mode(candidate.payload)
        score = 15.0

        if len(_safe_list(plan.get("actions"))) > 0:
            score += 15.0

        if mode == "site_plan":
            if self._has_layer(plan, "BUILDING"):
                score += 20.0
            if self._has_layer(plan, "PAVEMENT") or self._has_text_containing(plan, "STALLS"):
                score += 15.0
            if self._has_layer(plan, "WALK"):
                score += 8.0
            if self._has_layer(plan, "UTILITY") or self._has_layer(plan, "WATER") or self._has_layer(plan, "SAN"):
                score += 8.0

        elif mode == "drainage":
            if self._has_layer(plan, "DRAIN_FLOW"):
                score += 18.0
            if self._has_layer(plan, "PIPE"):
                score += 12.0
            if self._has_layer(plan, "BASIN_BOUNDARY"):
                score += 12.0

        elif mode == "road":
            if self._has_layer(plan, "ROAD"):
                score += 25.0
            if self._has_layer(plan, "WALK"):
                score += 8.0

        elif mode == "subdivision":
            if self._has_layer(plan, "ROAD"):
                score += 18.0
            if self._has_layer(plan, "LOT"):
                score += 15.0

        elif mode == "bridge":
            if self._has_layer(plan, "STRUCTURE"):
                score += 30.0

        elif mode == "pool":
            if self._has_text_containing(plan, "POOL") or self._has_layer(plan, "SITE"):
                score += 20.0

        if _safe_dict(_manager_export_meta(plan).get("metrics")):
            score += 5.0

        return max(0.0, min(100.0, score))

    def _score_confidence(self, candidate: CandidatePlan) -> float:
        assumption_count = len(candidate.assumptions)
        conflict_count = len(candidate.conflicts)
        issue_count = len(candidate.issues)

        score = 85.0
        score -= assumption_count * 2.5
        score -= conflict_count * 4.0
        score -= issue_count * 0.8

        if _safe_float(_safe_dict(_planner_score_meta(candidate.plan)).get("total"), 0.0) > 0:
            score += 5.0

        return max(0.0, min(100.0, score))

    # -------------------------------------------------------------------------
    # Explanation
    # -------------------------------------------------------------------------

    def _explain_candidate(self, candidate: CandidatePlan) -> None:
        payload = candidate.payload
        mode = _mode(payload)
        strategy_name = _safe_str(candidate.strategy.get("strategy_name"), _safe_str(payload.get("layout_strategy"), "default"))
        summary = _safe_str(candidate.strategy.get("summary"))

        if summary:
            candidate.decisions.append(
                CandidateDecision(
                    category="strategy_summary",
                    message=summary,
                    details={"strategy_name": strategy_name},
                )
            )

        candidate.decisions.append(
            CandidateDecision(
                category="strategy",
                message=f"Used strategy '{strategy_name}' for mode '{mode}'.",
                details={"mode": mode, "strategy": strategy_name},
            )
        )

        if candidate.refinements:
            candidate.decisions.append(
                CandidateDecision(
                    category="refinement",
                    message=f"Candidate refined through {len(candidate.refinements)} pass(es).",
                    details={"refinement_titles": [r.title for r in candidate.refinements]},
                )
            )

        if candidate.lineage.parent_candidate_id:
            candidate.decisions.append(
                CandidateDecision(
                    category="lineage",
                    message=f"Evolved from parent candidate '{candidate.lineage.parent_candidate_id}'.",
                    details={"generation": candidate.lineage.generation},
                )
            )

        if candidate.score.parking >= 75:
            candidate.pros.append("Strong parking performance relative to the requested or inferred program.")
        if candidate.score.drainage >= 60:
            candidate.pros.append("Drainage organization is stronger than lower-ranked alternatives.")
        if candidate.score.grading >= 50:
            candidate.pros.append("Grading/surface support is stronger than minimal concept output.")
        if candidate.score.utilities >= 50:
            candidate.pros.append("Utility coordination is stronger than minimal concept output.")
        if candidate.score.pipes >= 55:
            candidate.pros.append("Pipe-network signal is stronger and more coordinated than weaker alternatives.")
        if candidate.score.compliance >= 85:
            candidate.pros.append("Cleaner QA/compliance profile than weaker alternatives.")
        if candidate.score.constructability >= 60:
            candidate.pros.append("Constructability appears more realistic than a purely diagrammatic option.")
        if candidate.score.confidence >= 70:
            candidate.pros.append("Confidence burden is acceptable relative to assumptions and conflicts.")

        if candidate.score.parking < 45 and _mode(candidate.payload) == "site_plan":
            candidate.cons.append("Parking performance is weak for a site-plan candidate.")
        if candidate.score.drainage < 35 and _mode(candidate.payload) in {"site_plan", "drainage", "subdivision"}:
            candidate.cons.append("Drainage support or clarity is weaker than desired.")
        if candidate.score.grading < 25 and _mode(candidate.payload) == "site_plan":
            candidate.cons.append("Grading/surface support is limited in this option.")
        if candidate.score.utilities < 25 and _mode(candidate.payload) == "site_plan":
            candidate.cons.append("Utility coordination signal is weak in this option.")
        if candidate.score.pipes < 20 and self._has_layer(candidate.plan, "PIPE"):
            candidate.cons.append("Pipe performance/capacity confidence is weaker than preferred.")
        if candidate.score.compliance < 60:
            candidate.cons.append("QA/conflict burden is heavier than preferred.")
        if candidate.score.confidence < 55:
            candidate.cons.append("This option relies on more assumptions or unresolved concerns than preferred.")

        for conflict in candidate.conflicts:
            if conflict.severity == "critical":
                candidate.decisions.append(
                    CandidateDecision(
                        category="critical_conflict",
                        message=conflict.message,
                        details=deepcopy(conflict.details),
                    )
                )

        if not candidate.pros:
            candidate.pros.append("This option remains viable as an alternate concept for comparison.")
        if not candidate.cons:
            candidate.cons.append("No single weakness dominated this option, but higher-ranked options scored better overall.")

    # -------------------------------------------------------------------------
    # Preview / grouping
    # -------------------------------------------------------------------------

    def _build_preview_payload(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        actions = _safe_list(plan.get("actions"))
        bbox = self._plan_bbox(actions)
        discipline_layers = self._layer_counts(actions)
        return {
            "project_name": _safe_str(plan.get("project_name"), "Generated Plan"),
            "units": _safe_str(plan.get("units"), "ft"),
            "actions": deepcopy(actions),
            "bbox": bbox,
            "summary": {
                "action_count": len(actions),
                "layers": discipline_layers,
                "discipline_groups": self._discipline_groups_from_layers(discipline_layers),
            },
        }

    def _plan_bbox(self, actions: Sequence[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        xs: List[float] = []
        ys: List[float] = []

        for action in actions:
            task = _lower(action.get("task"))
            if task == "rectangle":
                x, y = self._safe_origin(action)
                w = _safe_float(action.get("width"), 0.0)
                h = _safe_float(action.get("height"), 0.0)
                if w > 0 and h > 0:
                    xs.extend([x, x + w])
                    ys.extend([y, y + h])

            elif task in {"polyline", "polygon"}:
                for p in _safe_list(action.get("points")):
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        xs.append(_safe_float(p[0], 0.0))
                        ys.append(_safe_float(p[1], 0.0))

            elif task in {"circle", "arc"}:
                center = _safe_list(action.get("center"))
                r = _safe_float(action.get("radius"), 0.0)
                if len(center) >= 2 and r > 0:
                    cx = _safe_float(center[0], 0.0)
                    cy = _safe_float(center[1], 0.0)
                    xs.extend([cx - r, cx + r])
                    ys.extend([cy - r, cy + r])

            elif task in {"text_note", "point", "north_arrow"}:
                x, y = self._safe_origin(action)
                xs.append(x)
                ys.append(y)

        if not xs or not ys:
            return None

        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
        }

    def _safe_origin(self, action: Dict[str, Any]) -> Tuple[float, float]:
        origin = _safe_list(action.get("origin"))
        if len(origin) >= 2:
            return _safe_float(origin[0], 0.0), _safe_float(origin[1], 0.0)
        return 0.0, 0.0

    def _layer_counts(self, actions: Sequence[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for action in actions:
            layer = _safe_str(action.get("layer"), "SITE")
            counts[layer] = counts.get(layer, 0) + 1
        return counts

    def _discipline_groups_from_layers(self, layers: Dict[str, int]) -> Dict[str, int]:
        groups = {
            "site": 0,
            "structures": 0,
            "circulation": 0,
            "grading": 0,
            "drainage": 0,
            "utilities": 0,
            "annotation": 0,
        }
        for layer, count in layers.items():
            upper = layer.upper()
            if upper in {"SITE", "LOT", "PAVEMENT"}:
                groups["site"] += count
            elif upper in {"BUILDING", "STRUCTURE"}:
                groups["structures"] += count
            elif upper in {"ROAD", "WALK"}:
                groups["circulation"] += count
            elif upper in {"FG_CONTOUR", "EG_CONTOUR", "SURFACE", "SPOT_FG", "SPOT_EG"}:
                groups["grading"] += count
            elif upper in {"DRAIN_FLOW", "PIPE", "BASIN_BOUNDARY", "DRAIN"}:
                groups["drainage"] += count
            elif upper in {"UTILITY", "WATER", "SAN", "STORM"}:
                groups["utilities"] += count
            else:
                groups["annotation"] += count
        return groups

    def _build_option_groups(self, options: Sequence[CandidatePlan]) -> List[Dict[str, Any]]:
        groups: Dict[str, List[CandidatePlan]] = {}
        for option in options:
            groups.setdefault(option.option_family or "generic", []).append(option)

        out: List[Dict[str, Any]] = []
        for family, family_options in groups.items():
            out.append(
                {
                    "family": family,
                    "count": len(family_options),
                    "option_names": [o.option_name for o in family_options],
                    "top_score": max((o.score.total for o in family_options), default=0.0),
                }
            )
        out.sort(key=lambda x: x["top_score"], reverse=True)
        return out

    # -------------------------------------------------------------------------
    # UI questions / actions
    # -------------------------------------------------------------------------

    def _build_questions(
        self,
        payload: Dict[str, Any],
        recommended: Optional[CandidatePlan],
        top_options: Sequence[CandidatePlan],
    ) -> List[IntelligenceQuestion]:
        questions: List[IntelligenceQuestion] = []
        mode = _mode(payload)

        if mode == "site_plan" and _safe_int(_safe_dict(payload.get("site_plan")).get("parking_count"), 0) <= 0:
            questions.append(
                IntelligenceQuestion(
                    question_id=_new_id("q"),
                    question_type="missing_input",
                    prompt="How important is parking count versus building prominence for this design?",
                    options=["Maximize parking", "Balanced", "Favor building/frontage"],
                    field_name="site_plan.parking_count",
                    importance="high",
                )
            )

        if recommended is not None and recommended.conflicts:
            questions.append(
                IntelligenceQuestion(
                    question_id=_new_id("q"),
                    question_type="refinement_goal",
                    prompt="What should the next round prioritize most?",
                    options=[
                        "More parking",
                        "Less grading",
                        "Better drainage",
                        "Shorter utilities",
                        "Cleaner compliance",
                        "Keep as-is",
                    ],
                    field_name="refinement_goal",
                    importance="high",
                )
            )

        questions.append(
            IntelligenceQuestion(
                question_id=_new_id("q"),
                question_type="option_selection",
                prompt="Which of the top options do you want to keep, save, or refine further?",
                options=[c.option_name for c in top_options],
                field_name="selected_option",
                importance="high",
            )
        )

        return questions

    def _build_actions(
        self,
        payload: Dict[str, Any],
        recommended: Optional[CandidatePlan],
        top_options: Sequence[CandidatePlan],
        preferences: Dict[str, Any],
    ) -> List[IntelligenceAction]:
        actions: List[IntelligenceAction] = []

        if recommended is not None:
            actions.append(
                IntelligenceAction(
                    action_id=_new_id("act"),
                    action_type="save_recommended",
                    title="Save Recommended Option",
                    description="Save the highest-ranked option so it can be compared or exported later.",
                    payload={"candidate_id": recommended.candidate_id},
                )
            )
            actions.append(
                IntelligenceAction(
                    action_id=_new_id("act"),
                    action_type="refine_recommended",
                    title="Refine Recommended Option",
                    description="Run another round around the current recommendation rather than starting from scratch.",
                    payload={"candidate_id": recommended.candidate_id, "goal": "refine_recommended"},
                )
            )

        actions.append(
            IntelligenceAction(
                action_id=_new_id("act"),
                action_type="generate_more",
                title="Generate More Options",
                description="Explore additional alternatives beyond the current best few.",
                payload={"exclude_option_names": [c.option_name for c in top_options]},
            )
        )
        actions.append(
            IntelligenceAction(
                action_id=_new_id("act"),
                action_type="optimize_more_parking",
                title="Optimize for More Parking",
                description="Generate another round biased toward higher parking yield.",
                payload={"goal": "maximize_parking"},
            )
        )
        actions.append(
            IntelligenceAction(
                action_id=_new_id("act"),
                action_type="optimize_less_grading",
                title="Optimize for Less Grading",
                description="Generate another round biased toward reduced grading burden.",
                payload={"goal": "reduce_grading"},
            )
        )
        actions.append(
            IntelligenceAction(
                action_id=_new_id("act"),
                action_type="optimize_better_drainage",
                title="Optimize for Better Drainage",
                description="Generate another round biased toward stronger drainage/outfall organization.",
                payload={"goal": "improve_drainage"},
            )
        )

        if self.saved_options:
            actions.append(
                IntelligenceAction(
                    action_id=_new_id("act"),
                    action_type="branch_from_saved",
                    title="Generate Variants from Saved Option",
                    description="Use a saved option as the parent for the next exploration round.",
                    payload={"saved_candidate_ids": list(self.saved_options.keys())},
                )
            )

        return actions

    # -------------------------------------------------------------------------
    # Summaries / helpers
    # -------------------------------------------------------------------------

    def _build_rejected_summary(self, candidates: Sequence[CandidatePlan]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for candidate in candidates:
            out.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "option_name": candidate.option_name,
                    "score": candidate.score.total,
                    "option_family": candidate.option_family,
                    "top_cons": candidate.cons[:2],
                    "critical_conflicts": [c.message for c in candidate.conflicts if c.severity == "critical"][:2],
                }
            )
        return out

    def _estimate_building_area(self, plan: Dict[str, Any]) -> float:
        total = 0.0
        for action in _safe_list(plan.get("actions")):
            task = _lower(action.get("task"))
            layer = _safe_str(action.get("layer"), "").upper()
            label = _lower(action.get("label"))
            if task == "rectangle":
                if layer in {"BUILDING", "STRUCTURE"} or "bldg" in label or "building" in label:
                    total += _safe_float(action.get("width"), 0.0) * _safe_float(action.get("height"), 0.0)
        return total

    def _has_layer(self, plan: Dict[str, Any], layer: str) -> bool:
        target = layer.upper()
        for action in _safe_list(plan.get("actions")):
            if _safe_str(action.get("layer"), "").upper() == target:
                return True
        return False

    def _has_text_containing(self, plan: Dict[str, Any], fragment: str) -> bool:
        needle = fragment.lower()
        for action in _safe_list(plan.get("actions")):
            if needle in _lower(action.get("label")):
                return True
            if needle in _lower(action.get("text")):
                return True
        return False

    def _pipe_capacity_ratio(self, plan: Dict[str, Any]) -> float:
        manager_metrics = _safe_dict(_manager_export_meta(plan).get("metrics"))
        return _safe_float(_safe_dict(manager_metrics.get("pipe_max_capacity_ratio")).get("value"), 0.0)

    def _infer_parking_count_from_plan(self, plan: Dict[str, Any]) -> int:
        count = 0
        for action in _safe_list(plan.get("actions")):
            text = _safe_str(action.get("text"), "")
            if "STALLS" in text.upper():
                numbers = "".join(ch if ch.isdigit() else " " for ch in text)
                for token in numbers.split():
                    try:
                        count = max(count, int(token))
                    except Exception:
                        pass
        if count > 0:
            return count

        meta = _safe_dict(plan.get("meta"))
        qa = _safe_dict(meta.get("qa"))
        stats = _safe_dict(qa.get("stats"))
        parking_area = _safe_float(stats.get("estimated_parking_area_sf"), 0.0)
        if parking_area > 0:
            return max(0, int(round(parking_area / 325.0)))
        return 0


# =============================================================================
# CONVENIENCE API
# =============================================================================

def generate_intelligent_options(
    parsed_payload: Dict[str, Any],
    *,
    max_candidates: int = MAX_DEFAULT_CANDIDATES,
    top_k: int = DEFAULT_TOP_OPTIONS,
    extra_preferences: Optional[Dict[str, Any]] = None,
    evolution_rounds: int = DEFAULT_GLOBAL_EVOLUTION_ROUNDS,
) -> PlannerIntelligenceResult:
    engine = PlannerIntelligence()
    return engine.generate_options(
        parsed_payload,
        max_candidates=max_candidates,
        top_k=top_k,
        extra_preferences=extra_preferences,
        evolution_rounds=evolution_rounds,
    )
