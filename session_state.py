
from __future__ import annotations

"""
session_state.py (TRUE MAX MERGED CIVIL-GRADE VERSION)

Purpose
-------
Session/state memory layer for the AI civil / CAD platform.

This module preserves active user-facing design state across requests so the
product can support flows like:
- "optimize this one"
- "go back to option 2"
- "generate more like this"
- "fix only drainage"
- "save this design"
- "branch from the current best option"

This is a product/session layer, not a replacement for ProjectManager snapshots.
ProjectManager manages engineering/model lifecycle inside a run.
session_state.py manages user/product workflow state across runs.

Design goals
------------
- stable, explicit session objects
- branch/save/restore behavior
- track active design, alternatives, reports, routing, and UI preferences
- support in-memory use today and easy persistence later
- no simplification of workflow depth
"""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any, Dict, List, Optional
import time
import uuid


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SessionOptionRecord:
    candidate_id: Optional[str] = None
    option_name: str = ""
    option_family: str = ""
    score: float = 0.0
    plan: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_saved: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class SessionRunRecord:
    run_id: str
    timestamp: float
    request_summary: Dict[str, Any] = field(default_factory=dict)
    routing: Dict[str, Any] = field(default_factory=dict)
    final_plan: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    assumptions: List[Dict[str, Any]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    exports: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStateRecord:
    session_id: str
    created_at: float
    updated_at: float

    active_plan: Dict[str, Any] = field(default_factory=dict)
    active_option: Optional[SessionOptionRecord] = None
    saved_options: List[SessionOptionRecord] = field(default_factory=list)
    alternatives: List[SessionOptionRecord] = field(default_factory=list)

    routing: Dict[str, Any] = field(default_factory=dict)
    latest_report: Dict[str, Any] = field(default_factory=dict)
    latest_metrics: Dict[str, Any] = field(default_factory=dict)
    latest_issues: List[Dict[str, Any]] = field(default_factory=list)
    latest_warnings: List[str] = field(default_factory=list)
    latest_errors: List[str] = field(default_factory=list)
    latest_assumptions: List[Dict[str, Any]] = field(default_factory=list)

    run_history: List[SessionRunRecord] = field(default_factory=list)
    ui_preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# HELPERS
# =============================================================================

def _now() -> float:
    return time.time()


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _coerce_option_record(option_like: Any) -> SessionOptionRecord:
    if isinstance(option_like, SessionOptionRecord):
        return deepcopy(option_like)

    d = _safe_dict(option_like)
    metadata = deepcopy(_safe_dict(d.get("metadata")))

    return SessionOptionRecord(
        candidate_id=d.get("candidate_id"),
        option_name=_safe_str(d.get("option_name"), "Option"),
        option_family=_safe_str(d.get("option_family"), ""),
        score=_safe_float(d.get("score"), 0.0),
        plan=deepcopy(_safe_dict(d.get("plan"))),
        metadata=metadata,
        is_saved=bool(d.get("is_saved", False)),
        created_at=_safe_float(d.get("created_at"), _now()),
    )


def _serialize_option_record(option: SessionOptionRecord) -> Dict[str, Any]:
    return {
        "candidate_id": option.candidate_id,
        "option_name": option.option_name,
        "option_family": option.option_family,
        "score": option.score,
        "plan": deepcopy(option.plan),
        "metadata": deepcopy(option.metadata),
        "is_saved": option.is_saved,
        "created_at": option.created_at,
    }


def _serialize_run_record(run: SessionRunRecord) -> Dict[str, Any]:
    return {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "request_summary": deepcopy(run.request_summary),
        "routing": deepcopy(run.routing),
        "final_plan": deepcopy(run.final_plan),
        "alternatives": deepcopy(run.alternatives),
        "metrics": deepcopy(run.metrics),
        "issues": deepcopy(run.issues),
        "warnings": list(run.warnings),
        "errors": list(run.errors),
        "assumptions": deepcopy(run.assumptions),
        "analysis": deepcopy(run.analysis),
        "iterations": deepcopy(run.iterations),
        "exports": deepcopy(run.exports),
        "metadata": deepcopy(run.metadata),
    }


def _serialize_session_record(state: SessionStateRecord) -> Dict[str, Any]:
    return {
        "session_id": state.session_id,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "active_plan": deepcopy(state.active_plan),
        "active_option": None if state.active_option is None else _serialize_option_record(state.active_option),
        "saved_options": [_serialize_option_record(x) for x in state.saved_options],
        "alternatives": [_serialize_option_record(x) for x in state.alternatives],
        "routing": deepcopy(state.routing),
        "latest_report": deepcopy(state.latest_report),
        "latest_metrics": deepcopy(state.latest_metrics),
        "latest_issues": deepcopy(state.latest_issues),
        "latest_warnings": list(state.latest_warnings),
        "latest_errors": list(state.latest_errors),
        "latest_assumptions": deepcopy(state.latest_assumptions),
        "run_history": [_serialize_run_record(x) for x in state.run_history],
        "ui_preferences": deepcopy(state.ui_preferences),
        "metadata": deepcopy(state.metadata),
    }


# =============================================================================
# SESSION STORE
# =============================================================================

class SessionStateStore:
    """
    In-memory session store.

    This is intentionally product-level and workflow-oriented:
    - tracks active design
    - tracks saved alternatives
    - supports branching from options
    - preserves run history
    - ready to be swapped for persistent storage later
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionStateRecord] = {}

    # ---------------------------------------------------------------------
    # Session lifecycle
    # ---------------------------------------------------------------------

    def create_session(self, session_id: Optional[str] = None, **metadata: Any) -> SessionStateRecord:
        sid = session_id or _new_id("session")
        now = _now()
        state = SessionStateRecord(
            session_id=sid,
            created_at=now,
            updated_at=now,
            metadata=deepcopy(metadata),
        )
        self._sessions[sid] = state
        return deepcopy(state)

    def get_session(self, session_id: str) -> Optional[SessionStateRecord]:
        state = self._sessions.get(session_id)
        return deepcopy(state) if state is not None else None

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for state in self._sessions.values():
            out.append({
                "session_id": state.session_id,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "has_active_plan": bool(state.active_plan),
                "saved_option_count": len(state.saved_options),
                "alternative_count": len(state.alternatives),
                "run_count": len(state.run_history),
            })
        out.sort(key=lambda x: x["updated_at"], reverse=True)
        return out

    # ---------------------------------------------------------------------
    # Main save/update workflow
    # ---------------------------------------------------------------------

    def save_session_state(
        self,
        *,
        session_id: Optional[str] = None,
        final_plan: Optional[Dict[str, Any]] = None,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        routing: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        issues: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        assumptions: Optional[List[Dict[str, Any]]] = None,
        analysis: Optional[Dict[str, Any]] = None,
        iterations: Optional[List[Dict[str, Any]]] = None,
        exports: Optional[List[Dict[str, Any]]] = None,
        report: Optional[Dict[str, Any]] = None,
        request_summary: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ui_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        state = self._sessions.get(session_id or "")
        if state is None:
            state = self.create_session(session_id=session_id).copy() if False else self._sessions[(session_id or list(self._sessions.keys())[-1]) if False else None]  # never used
        # simpler, explicit creation:
        if session_id is None or session_id not in self._sessions:
            sid = session_id or _new_id("session")
            now = _now()
            state = SessionStateRecord(session_id=sid, created_at=now, updated_at=now)
            self._sessions[sid] = state
        else:
            state = self._sessions[session_id]

        now = _now()
        state.updated_at = now

        final_plan = deepcopy(final_plan) if isinstance(final_plan, dict) else {}
        alternatives = deepcopy(alternatives) if isinstance(alternatives, list) else []
        routing = deepcopy(routing) if isinstance(routing, dict) else {}
        metrics = deepcopy(metrics) if isinstance(metrics, dict) else {}
        issues = deepcopy(issues) if isinstance(issues, list) else []
        warnings = list(warnings or [])
        errors = list(errors or [])
        assumptions = deepcopy(assumptions) if isinstance(assumptions, list) else []
        analysis = deepcopy(analysis) if isinstance(analysis, dict) else {}
        iterations = deepcopy(iterations) if isinstance(iterations, list) else []
        exports = deepcopy(exports) if isinstance(exports, list) else []
        report = deepcopy(report) if isinstance(report, dict) else {}
        request_summary = deepcopy(request_summary) if isinstance(request_summary, dict) else {}
        metadata = deepcopy(metadata) if isinstance(metadata, dict) else {}
        ui_preferences = deepcopy(ui_preferences) if isinstance(ui_preferences, dict) else {}

        if final_plan:
            state.active_plan = deepcopy(final_plan)
            state.active_option = SessionOptionRecord(
                candidate_id=_safe_dict(_safe_dict(routing).get("decision")).get("recommended_candidate_id"),
                option_name=_safe_str(_safe_dict(_safe_dict(routing).get("decision")).get("recommended_option_name"), _safe_str(final_plan.get("project_name"), "Active Plan")),
                option_family=_safe_str(_safe_dict(_safe_dict(routing).get("decision")).get("recommended_family"), ""),
                score=_safe_float(_safe_dict(metrics).get("planner_score"), 0.0),
                plan=deepcopy(final_plan),
                metadata={"source": "active_plan"},
                is_saved=False,
                created_at=now,
            )

        state.alternatives = [_coerce_option_record(x) for x in alternatives]
        state.routing = deepcopy(routing)
        state.latest_report = deepcopy(report)
        state.latest_metrics = deepcopy(metrics)
        state.latest_issues = deepcopy(issues)
        state.latest_warnings = list(warnings)
        state.latest_errors = list(errors)
        state.latest_assumptions = deepcopy(assumptions)
        state.ui_preferences = deepcopy(ui_preferences) if ui_preferences else state.ui_preferences
        state.metadata.update(metadata)

        run = SessionRunRecord(
            run_id=_new_id("run"),
            timestamp=now,
            request_summary=deepcopy(request_summary),
            routing=deepcopy(routing),
            final_plan=deepcopy(final_plan),
            alternatives=deepcopy(alternatives),
            metrics=deepcopy(metrics),
            issues=deepcopy(issues),
            warnings=list(warnings),
            errors=list(errors),
            assumptions=deepcopy(assumptions),
            analysis=deepcopy(analysis),
            iterations=deepcopy(iterations),
            exports=deepcopy(exports),
            metadata=deepcopy(metadata),
        )
        state.run_history.append(run)

        return {
            "success": True,
            "session_id": state.session_id,
            "saved_run_id": run.run_id,
            "run_count": len(state.run_history),
            "saved_option_count": len(state.saved_options),
            "alternative_count": len(state.alternatives),
            "updated_at": state.updated_at,
        }

    # ---------------------------------------------------------------------
    # Option management
    # ---------------------------------------------------------------------

    def save_option(
        self,
        *,
        session_id: str,
        option: Dict[str, Any],
        replace_if_same_name: bool = False,
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        record = _coerce_option_record(option)
        record.is_saved = True
        state.updated_at = _now()

        if replace_if_same_name:
            state.saved_options = [x for x in state.saved_options if x.option_name != record.option_name]

        state.saved_options.append(record)
        return {
            "success": True,
            "session_id": state.session_id,
            "option_name": record.option_name,
            "saved_option_count": len(state.saved_options),
        }

    def set_active_option(
        self,
        *,
        session_id: str,
        option_name: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        candidates = []
        if state.active_option is not None:
            candidates.append(state.active_option)
        candidates.extend(state.saved_options)
        candidates.extend(state.alternatives)

        chosen: Optional[SessionOptionRecord] = None
        for item in candidates:
            if candidate_id and item.candidate_id == candidate_id:
                chosen = deepcopy(item)
                break
            if option_name and item.option_name == option_name:
                chosen = deepcopy(item)
                break

        if chosen is None:
            return {
                "success": False,
                "session_id": session_id,
                "message": "Requested option was not found in session state.",
            }

        state.active_option = deepcopy(chosen)
        state.active_plan = deepcopy(chosen.plan)
        state.updated_at = _now()

        return {
            "success": True,
            "session_id": session_id,
            "active_option_name": chosen.option_name,
            "candidate_id": chosen.candidate_id,
        }

    def branch_from_option(
        self,
        *,
        session_id: str,
        option_name: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)

        target = None
        all_options = []
        if state.active_option is not None:
            all_options.append(state.active_option)
        all_options.extend(state.saved_options)
        all_options.extend(state.alternatives)

        for option in all_options:
            if candidate_id and option.candidate_id == candidate_id:
                target = deepcopy(option)
                break
            if option_name and option.option_name == option_name:
                target = deepcopy(option)
                break

        if target is None:
            return {
                "success": False,
                "session_id": session_id,
                "message": "Branch target not found.",
            }

        branch_name = f"{target.option_name} Branch"
        branched = deepcopy(target)
        branched.option_name = branch_name
        branched.is_saved = False
        branched.created_at = _now()
        branched.metadata = _safe_dict(branched.metadata)
        branched.metadata["branched_from"] = {
            "candidate_id": target.candidate_id,
            "option_name": target.option_name,
        }

        state.active_option = branched
        state.active_plan = deepcopy(branched.plan)
        state.updated_at = _now()

        return {
            "success": True,
            "session_id": session_id,
            "branch_name": branch_name,
            "source_option_name": target.option_name,
        }

    # ---------------------------------------------------------------------
    # Read helpers
    # ---------------------------------------------------------------------

    def get_active_plan(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        return deepcopy(state.active_plan)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        return {
            "session_id": state.session_id,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "active_option": None if state.active_option is None else _serialize_option_record(state.active_option),
            "saved_options": [_serialize_option_record(x) for x in state.saved_options],
            "alternatives": [_serialize_option_record(x) for x in state.alternatives],
            "routing": deepcopy(state.routing),
            "latest_metrics": deepcopy(state.latest_metrics),
            "latest_issue_count": len(state.latest_issues),
            "latest_warning_count": len(state.latest_warnings),
            "latest_error_count": len(state.latest_errors),
            "run_count": len(state.run_history),
            "ui_preferences": deepcopy(state.ui_preferences),
            "metadata": deepcopy(state.metadata),
        }

    def export_session_state(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        return _serialize_session_record(state)

    # ---------------------------------------------------------------------
    # UI preferences
    # ---------------------------------------------------------------------

    def update_ui_preferences(self, session_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        state = self._require_session(session_id)
        state.ui_preferences.update(deepcopy(_safe_dict(preferences)))
        state.updated_at = _now()
        return {
            "success": True,
            "session_id": session_id,
            "ui_preferences": deepcopy(state.ui_preferences),
        }

    # ---------------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------------

    def _require_session(self, session_id: str) -> SessionStateRecord:
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' does not exist.")
        return self._sessions[session_id]


# =============================================================================
# GLOBAL STORE
# =============================================================================

_GLOBAL_SESSION_STORE = SessionStateStore()


# =============================================================================
# PUBLIC API
# =============================================================================

def create_session(session_id: Optional[str] = None, **metadata: Any) -> Dict[str, Any]:
    state = _GLOBAL_SESSION_STORE.create_session(session_id=session_id, **metadata)
    return {
        "success": True,
        "session_id": state.session_id,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def save_session_state(
    *,
    session_id: Optional[str] = None,
    final_plan: Optional[Dict[str, Any]] = None,
    alternatives: Optional[List[Dict[str, Any]]] = None,
    routing: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    assumptions: Optional[List[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    iterations: Optional[List[Dict[str, Any]]] = None,
    exports: Optional[List[Dict[str, Any]]] = None,
    report: Optional[Dict[str, Any]] = None,
    request_summary: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ui_preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.save_session_state(
        session_id=session_id,
        final_plan=final_plan,
        alternatives=alternatives,
        routing=routing,
        metrics=metrics,
        issues=issues,
        warnings=warnings,
        errors=errors,
        assumptions=assumptions,
        analysis=analysis,
        iterations=iterations,
        exports=exports,
        report=report,
        request_summary=request_summary,
        metadata=metadata,
        ui_preferences=ui_preferences,
    )


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    state = _GLOBAL_SESSION_STORE.get_session(session_id)
    return None if state is None else _serialize_session_record(state)


def get_session_summary(session_id: str) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.get_session_summary(session_id)


def list_sessions() -> List[Dict[str, Any]]:
    return _GLOBAL_SESSION_STORE.list_sessions()


def save_option(*, session_id: str, option: Dict[str, Any], replace_if_same_name: bool = False) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.save_option(
        session_id=session_id,
        option=option,
        replace_if_same_name=replace_if_same_name,
    )


def set_active_option(*, session_id: str, option_name: Optional[str] = None, candidate_id: Optional[str] = None) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.set_active_option(
        session_id=session_id,
        option_name=option_name,
        candidate_id=candidate_id,
    )


def branch_from_option(*, session_id: str, option_name: Optional[str] = None, candidate_id: Optional[str] = None) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.branch_from_option(
        session_id=session_id,
        option_name=option_name,
        candidate_id=candidate_id,
    )


def update_ui_preferences(session_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.update_ui_preferences(session_id, preferences)


def delete_session(session_id: str) -> bool:
    return _GLOBAL_SESSION_STORE.delete_session(session_id)


def export_session_state(session_id: str) -> Dict[str, Any]:
    return _GLOBAL_SESSION_STORE.export_session_state(session_id)
