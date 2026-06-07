
from __future__ import annotations

"""
report_builder.py (TRUE MAX MERGED CIVIL-GRADE VERSION)

Purpose
-------
Backend reporting / summarization layer for the AI civil / CAD platform.

This file converts planner/orchestrator/coordination outputs into:
- executive summaries
- engineering summaries
- metrics tables
- issue / warning / assumption sections
- alternative comparison summaries
- UI-ready report payloads

Design goals
------------
- no placeholder "demo" reports
- preserve real backend metadata and structure
- produce stable output for UI, API, exports, and beta review
- be flexible enough to work even if some optional sections are unavailable
"""

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from backend.planning.common import blocker_explanations, construction_package_record
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)
from backend.planning.smart_fix import build_smart_fix_recommendations


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ReportSection:
    section_id: str
    title: str
    content: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportPayload:
    success: bool
    message: str
    summary: Dict[str, Any] = field(default_factory=dict)
    executive: Dict[str, Any] = field(default_factory=dict)
    engineering: Dict[str, Any] = field(default_factory=dict)
    qa: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[Dict[str, Any]] = field(default_factory=list)
    exports: Dict[str, Any] = field(default_factory=dict)
    release: Dict[str, Any] = field(default_factory=dict)
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


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


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _coerce_assumptions(items: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            out.append({
                "field_name": _safe_str(item.get("field_name"), "assumption"),
                "assumed_value": item.get("assumed_value"),
                "reason": _safe_str(item.get("reason"), ""),
            })
        else:
            out.append({
                "field_name": "assumption",
                "assumed_value": item,
                "reason": "",
            })
    return out


def _coerce_issues(items: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            out.append({
                "code": _safe_str(item.get("code"), "ISSUE"),
                "severity": _safe_str(item.get("severity"), "warning"),
                "message": _safe_str(item.get("message"), ""),
                "context": deepcopy(_safe_dict(item.get("context"))),
            })
        else:
            out.append({
                "code": "ISSUE",
                "severity": "warning",
                "message": _safe_str(item),
                "context": {},
            })
    return out


def _estimate_action_count(final_plan: Dict[str, Any]) -> int:
    return len(_safe_list(final_plan.get("actions")))


def _extract_plan_meta(final_plan: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(_safe_dict(final_plan.get("meta")))


def _planner_score(final_plan: Dict[str, Any]) -> float:
    meta = _extract_plan_meta(final_plan)
    return _safe_float(_safe_dict(meta.get("planner_score")).get("total"), 0.0)


def _qa_block(final_plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _extract_plan_meta(final_plan)
    qa = _safe_dict(meta.get("qa"))
    return {
        "warning_count": _safe_int(qa.get("warning_count"), 0),
        "error_count": _safe_int(qa.get("error_count"), 0),
        "issues": _coerce_issues(_safe_list(qa.get("issues"))),
        "checks_run": list(_safe_list(qa.get("checks_run"))),
        "stats": deepcopy(_safe_dict(qa.get("stats"))),
    }


def _manager_conflict_counts(manager_conflicts: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"info": 0, "warning": 0, "error": 0, "resolved": 0, "unresolved": 0}
    for item in manager_conflicts or []:
        sev = _lower(_safe_dict(item).get("severity"))
        if sev in counts:
            counts[sev] += 1
        if bool(_safe_dict(item).get("resolved", False)):
            counts["resolved"] += 1
        else:
            counts["unresolved"] += 1
    return counts


def _build_executive_summary(
    final_plan: Dict[str, Any],
    orchestrator_metadata: Dict[str, Any],
    qa: Dict[str, Any],
    manager_score: float,
) -> Dict[str, Any]:
    action_count = _estimate_action_count(final_plan)
    planner_total = _planner_score(final_plan)

    bullets: List[str] = []

    if planner_total:
        bullets.append(f"Planner score: {planner_total:.2f}.")
    if manager_score:
        bullets.append(f"Coordination/manager score: {manager_score:.2f}.")
    bullets.append(f"Generated {action_count} drawing action(s).")

    warnings = _safe_int(qa.get("warning_count"), 0)
    errors = _safe_int(qa.get("error_count"), 0)
    if errors > 0:
        bullets.append(f"{errors} QA error(s) remain and should be addressed before production use.")
    elif warnings > 0:
        bullets.append(f"{warnings} QA warning(s) remain for review.")
    else:
        bullets.append("No QA issues were reported in the final plan payload.")

    recommended_option = _safe_str(orchestrator_metadata.get("recommended_option_name"))
    if recommended_option:
        bullets.append(f"Recommended option: {recommended_option}.")

    workflow = _safe_str(orchestrator_metadata.get("workflow"))
    if workflow:
        bullets.append(f"Workflow: {workflow}.")

    return {
        "headline": "AI civil design run completed.",
        "bullets": bullets,
    }


def _build_engineering_summary(
    final_plan: Dict[str, Any],
    manager_metrics: Dict[str, Any],
    manager_conflicts: Sequence[Dict[str, Any]],
    coordination_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    meta = _extract_plan_meta(final_plan)
    explanation = _safe_dict(meta.get("explanation"))
    quantities = _safe_dict(meta.get("quantities"))
    planner_score = _safe_dict(meta.get("planner_score"))
    qa = _safe_dict(meta.get("qa"))

    return {
        "planner_score": deepcopy(planner_score),
        "explanation": deepcopy(explanation),
        "quantities": deepcopy(quantities),
        "qa_stats": deepcopy(_safe_dict(qa.get("stats"))),
        "manager_metrics": deepcopy(manager_metrics),
        "manager_conflicts": list(manager_conflicts or []),
        "manager_conflict_counts": _manager_conflict_counts(manager_conflicts),
        "coordination": deepcopy(coordination_metadata),
    }


def _build_alternative_summary(alternatives: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for alt in alternatives or []:
        d = _safe_dict(alt)
        out.append({
            "candidate_id": d.get("candidate_id"),
            "option_name": _safe_str(d.get("option_name"), "Alternative"),
            "option_family": _safe_str(d.get("option_family"), ""),
            "score": _safe_float(d.get("score"), 0.0),
            "pros": list(_safe_list(d.get("pros"))),
            "cons": list(_safe_list(d.get("cons"))),
            "metadata": deepcopy(_safe_dict(d.get("metadata"))),
        })
    return out


def _top_metric_rows(manager_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name, rec in manager_metrics.items():
        d = _safe_dict(rec)
        rows.append({
            "name": name,
            "value": d.get("value"),
            "units": _safe_str(d.get("units"), ""),
            "category": _safe_str(d.get("category"), ""),
            "weight": _safe_float(d.get("weight"), 1.0),
        })
    rows.sort(key=lambda x: (x["category"], x["name"]))
    return rows


def _release_review_block(
    final_plan: Dict[str, Any],
    request_metadata: Dict[str, Any],
    *,
    runtime_error_count: int = 0,
) -> Dict[str, Any]:
    meta = _extract_plan_meta(final_plan)
    review = deepcopy(_safe_dict(request_metadata.get("release_review")) or _safe_dict(meta.get("release_review")))
    construction_release_required = final_plan_requires_construction_release(final_plan)
    blockers = [
        _safe_str(item)
        for item in list(_safe_list(review.get("blocked_reasons")) + _safe_list(review.get("blocked_exports")))
        if _safe_str(item)
    ]
    for blocker in construction_release_blockers_from_meta(
        meta,
        requires_construction_release=construction_release_required,
    ):
        if blocker not in blockers:
            blockers.append(blocker)
    if review.get("release_ready") is False and "release_review_not_ready" not in blockers:
        blockers.append("release_review_not_ready")
    if meta.get("release_ready") is False and "final_plan_release_blocked" not in blockers:
        blockers.append("final_plan_release_blocked")
    if runtime_error_count > 0 and "report_errors_present" not in blockers:
        blockers.append("report_errors_present")
    reactive_report = _safe_dict(meta.get("reactive_update_report"))
    if reactive_report.get("post_rerun_production_ready") is False and "reactive_post_rerun_not_ready" not in blockers:
        blockers.append("reactive_post_rerun_not_ready")
    for reactive_blocker in _safe_list(reactive_report.get("post_rerun_release_blockers")):
        reactive_blocker_name = _safe_str(reactive_blocker)
        if reactive_blocker_name and reactive_blocker_name not in blockers:
            blockers.append(reactive_blocker_name)
    export_audit = _safe_dict(meta.get("export_audit"))
    export_report = _safe_dict(meta.get("export_package_report_v1"))
    if export_audit.get("export_blocked") is True and "export_audit_blocked" not in blockers:
        blockers.append("export_audit_blocked")
    if _safe_list(export_report.get("stale_outputs_detected")) and "stale_exports_block_report" not in blockers:
        blockers.append("stale_exports_block_report")
    deliverables = _safe_dict(meta.get("deliverables"))

    def _merged_deliverables(*values: Any) -> List[str]:
        merged: List[str] = []
        for value in values:
            for item in _safe_list(value):
                name = _safe_str(item)
                if name and name not in merged:
                    merged.append(name)
        return merged

    requested_deliverables = _merged_deliverables(
        deliverables.get("requested"),
        review.get("requested_deliverables"),
    )
    produced_deliverable_list = _merged_deliverables(
        deliverables.get("produced"),
        review.get("produced_deliverables"),
    )
    failed_deliverable_list = _merged_deliverables(
        deliverables.get("failed"),
        review.get("failed_deliverables"),
    )
    explicit_missing_deliverables = _merged_deliverables(
        deliverables.get("missing"),
        review.get("missing_deliverables"),
    )

    for failed_deliverable in failed_deliverable_list:
        failed_blocker = f"failed_deliverable_{_safe_str(failed_deliverable).lower().replace(' ', '_')}"
        if failed_blocker.strip() and failed_blocker not in blockers:
            blockers.append(failed_blocker)
    produced_deliverables = {_safe_str(item) for item in produced_deliverable_list if _safe_str(item)}
    failed_deliverables = {_safe_str(item) for item in failed_deliverable_list if _safe_str(item)}
    missing_deliverables = explicit_missing_deliverables + [
        item
        for item in requested_deliverables
        if _safe_str(item) and _safe_str(item) not in produced_deliverables and _safe_str(item) not in failed_deliverables
    ]
    for missing_deliverable in missing_deliverables:
        missing_blocker = f"missing_deliverable_{_safe_str(missing_deliverable).lower().replace(' ', '_')}"
        if missing_blocker.strip() and missing_blocker not in blockers:
            blockers.append(missing_blocker)
    manual_validation = _safe_dict(meta.get("manual_validation"))
    manual_failures = [
        failure
        for failure in _safe_list(manual_validation.get("failures"))
        if isinstance(failure, dict)
    ]
    for failure in manual_failures:
        failure_key = _safe_str(
            failure.get("code")
            or failure.get("rule")
            or failure.get("system")
            or failure.get("message"),
            "manual_validation_failure",
        )
        if not failure_key:
            failure_key = "manual_validation_failure"
        blocker = f"manual_validation_{failure_key.lower().replace(' ', '_')}"
        if blocker not in blockers:
            blockers.append(blocker)
    release_status = _safe_str(review.get("release_status") or meta.get("release_status"), "unknown")
    if release_status.lower() == "blocked" and "release_status_blocked" not in blockers:
        blockers.append("release_status_blocked")
    release_ready = release_status == "ready" and not blockers
    if "release_ready" in review:
        release_ready = bool(review.get("release_ready")) and not blockers
    elif "release_ready" in meta:
        release_ready = bool(meta.get("release_ready")) and not blockers
    package = construction_package_record(meta)
    package_id = _safe_str(
        package.get("id")
        or package.get("package_id")
        or package.get("manifest_id")
        or package.get("construction_package_id")
    )
    model_reference = {
        key: value
        for key, value in {
            "canonical_model_id": meta.get("canonical_model_id") or meta.get("model_id"),
            "canonical_model_hash": meta.get("canonical_model_hash") or meta.get("model_hash"),
            "source_model_id": meta.get("source_model_id"),
            "source_model_hash": meta.get("source_model_hash"),
            "final_model_id": meta.get("final_model_id"),
            "final_model_hash": meta.get("final_model_hash"),
        }.items()
        if value not in (None, "")
    }
    return {
        "release_status": release_status,
        "release_ready": release_ready,
        "release_note": _safe_str(review.get("release_note"), ""),
        "blocked_reasons": list(dict.fromkeys(_safe_str(item) for item in _safe_list(review.get("blocked_reasons")) if _safe_str(item))),
        "blocked_exports": list(dict.fromkeys(_safe_str(item) for item in _safe_list(review.get("blocked_exports")) if _safe_str(item))),
        "release_blockers": list(dict.fromkeys(blockers)),
        "release_blocker_details": blocker_explanations(blockers),
        "smart_fix_recommendations_v1": build_smart_fix_recommendations(final_plan, meta=meta),
        "construction_release_required": construction_release_required,
        "construction_readiness": deepcopy(_safe_dict(meta.get("construction_readiness"))),
        "construction_package_id": package_id,
        "construction_package_artifact_status": deepcopy(_safe_dict(package.get("construction_package_artifact_status"))),
        "professional_package_release_status": deepcopy(_safe_dict(package.get("professional_package_release_status"))),
        "canonical_model_reference": model_reference,
    }


def _report_export_trace(final_plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _extract_plan_meta(final_plan)
    report = deepcopy(_safe_dict(meta.get("export_package_report_v1")))
    if not report:
        report = build_export_package_report_v1(final_plan, export_type="report")
    quantity_rows = deepcopy(_safe_list(report.get("quantity_line_items")))
    profile_packages = deepcopy(_safe_list(report.get("profile_packages")))
    section_packages = deepcopy(_safe_list(report.get("section_packages")))
    stale_outputs = deepcopy(_safe_list(report.get("stale_outputs_detected")))
    return {
        "source": "report_export_trace_v1",
        "export_package_report": report,
        "quantity_report": {
            "line_items": quantity_rows,
            "line_item_count": len(quantity_rows),
            "canonical_ids": list(
                dict.fromkeys(
                    _safe_str(canonical_id)
                    for row in quantity_rows
                    for canonical_id in _safe_list(_safe_dict(row).get("canonical_ids"))
                    if _safe_str(canonical_id)
                )
            ),
            "review_package_only": True,
            "engineer_review_required": True,
            "construction_release_allowed": False,
        },
        "profile_section_export": {
            "profiles": profile_packages,
            "sections": section_packages,
            "profile_count": len(profile_packages),
            "section_count": len(section_packages),
            "review_package_only": True,
            "engineer_review_required": True,
            "construction_release_allowed": False,
        },
        "stale_outputs_detected": stale_outputs,
        "stale_export_blocked": bool(stale_outputs),
        "civil3d_external_verification_status": "not_verified",
        "dwg_support_status": "unsupported_no_writer",
        "truth_label": (
            "Report exports carry traceable review metadata only; Civil3D is not verified "
            "and DWG is unsupported unless a real writer and verification record are attached."
        ),
    }


# =============================================================================
# REPORT BUILDER
# =============================================================================

class ReportBuilder:
    """
    Product-level reporting layer.

    This class turns backend outputs into a consistent report payload that the
    UI, API, exports, and beta reviewers can consume without digging through
    internal nested metadata.
    """

    def build_report(
        self,
        *,
        final_plan: Dict[str, Any],
        orchestrator_metadata: Optional[Dict[str, Any]] = None,
        manager_metrics: Optional[Dict[str, Any]] = None,
        manager_conflicts: Optional[Sequence[Dict[str, Any]]] = None,
        coordination_metadata: Optional[Dict[str, Any]] = None,
        alternatives: Optional[Sequence[Dict[str, Any]]] = None,
        assumptions: Optional[Sequence[Any]] = None,
        warnings: Optional[Sequence[str]] = None,
        errors: Optional[Sequence[str]] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
    ) -> ReportPayload:
        final_plan = deepcopy(final_plan)
        orchestrator_metadata = deepcopy(orchestrator_metadata) if isinstance(orchestrator_metadata, dict) else {}
        manager_metrics = deepcopy(manager_metrics) if isinstance(manager_metrics, dict) else {}
        manager_conflicts = deepcopy(list(manager_conflicts)) if manager_conflicts is not None else []
        coordination_metadata = deepcopy(coordination_metadata) if isinstance(coordination_metadata, dict) else {}
        alternatives = deepcopy(list(alternatives)) if alternatives is not None else []
        assumptions_list = _coerce_assumptions(list(assumptions) if assumptions is not None else list(final_plan.get("assumptions") or []))
        warning_list = list(warnings or [])
        error_list = list(errors or [])
        request_meta = deepcopy(request_metadata) if isinstance(request_metadata, dict) else {}

        qa = _qa_block(final_plan)
        manager_score = self._manager_score(manager_metrics)
        release = _release_review_block(
            final_plan,
            request_meta,
            runtime_error_count=len(error_list),
        )

        summary = {
            "project_name": _safe_str(final_plan.get("project_name"), "Generated Plan"),
            "units": _safe_str(final_plan.get("units"), "ft"),
            "action_count": _estimate_action_count(final_plan),
            "planner_score": _planner_score(final_plan),
            "manager_score": manager_score,
            "warning_count": _safe_int(qa.get("warning_count"), 0),
            "error_count": _safe_int(qa.get("error_count"), 0) + len(error_list),
            "workflow": _safe_str(orchestrator_metadata.get("workflow"), ""),
            "recommended_option_name": _safe_str(orchestrator_metadata.get("recommended_option_name"), ""),
            "release_status": release["release_status"],
            "release_ready": release["release_ready"],
            "release_blocker_count": len(release["release_blockers"]),
        }

        executive = _build_executive_summary(
            final_plan=final_plan,
            orchestrator_metadata=orchestrator_metadata,
            qa=qa,
            manager_score=manager_score,
        )

        engineering = _build_engineering_summary(
            final_plan=final_plan,
            manager_metrics=manager_metrics,
            manager_conflicts=manager_conflicts,
            coordination_metadata=coordination_metadata,
        )
        export_trace = _report_export_trace(final_plan)

        alternatives_summary = _build_alternative_summary(alternatives)

        sections = [
            ReportSection(
                section_id="summary",
                title="Summary",
                content=deepcopy(summary),
            ),
            ReportSection(
                section_id="executive",
                title="Executive Summary",
                content=deepcopy(executive),
            ),
            ReportSection(
                section_id="engineering",
                title="Engineering Summary",
                content=deepcopy(engineering),
            ),
            ReportSection(
                section_id="qa",
                title="QA / Issues",
                content={
                    "qa": deepcopy(qa),
                    "warnings": list(warning_list),
                    "errors": list(error_list),
                },
            ),
            ReportSection(
                section_id="release",
                title="Release Review",
                content=deepcopy(release),
            ),
            ReportSection(
                section_id="alternatives",
                title="Alternatives",
                content={"alternatives": deepcopy(alternatives_summary)},
            ),
            ReportSection(
                section_id="assumptions",
                title="Assumptions",
                content={"assumptions": deepcopy(assumptions_list)},
            ),
        ]

        return ReportPayload(
            success=True,
            message="Built report payload.",
            summary=summary,
            executive=executive,
            engineering=engineering,
            qa={
                "qa": deepcopy(qa),
                "warnings": warning_list,
                "errors": error_list,
            },
            alternatives=alternatives_summary,
            assumptions=assumptions_list,
            exports={
                "report_sections": [s.section_id for s in sections],
                "top_metric_rows": _top_metric_rows(manager_metrics),
                "export_trace": deepcopy(export_trace),
                "quantity_report": deepcopy(export_trace["quantity_report"]),
                "profile_section_export": deepcopy(export_trace["profile_section_export"]),
            },
            release=release,
            sections=sections,
            metadata={
                "orchestrator_metadata": deepcopy(orchestrator_metadata),
                "coordination_metadata": deepcopy(coordination_metadata),
                "request_metadata": deepcopy(request_meta),
            },
        )

    def _manager_score(self, manager_metrics: Dict[str, Any]) -> float:
        total = 0.0
        weight_sum = 0.0
        for _, rec in manager_metrics.items():
            d = _safe_dict(rec)
            value = d.get("value")
            weight = _safe_float(d.get("weight"), 1.0)
            if isinstance(value, (int, float)):
                total += float(value) * weight
                weight_sum += weight
        return total / weight_sum if weight_sum else 0.0


# =============================================================================
# PUBLIC API
# =============================================================================

def build_report(
    *,
    final_plan: Dict[str, Any],
    orchestrator_metadata: Optional[Dict[str, Any]] = None,
    manager_metrics: Optional[Dict[str, Any]] = None,
    manager_conflicts: Optional[Sequence[Dict[str, Any]]] = None,
    coordination_metadata: Optional[Dict[str, Any]] = None,
    alternatives: Optional[Sequence[Dict[str, Any]]] = None,
    assumptions: Optional[Sequence[Any]] = None,
    warnings: Optional[Sequence[str]] = None,
    errors: Optional[Sequence[str]] = None,
    request_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    report = ReportBuilder().build_report(
        final_plan=final_plan,
        orchestrator_metadata=orchestrator_metadata,
        manager_metrics=manager_metrics,
        manager_conflicts=manager_conflicts,
        coordination_metadata=coordination_metadata,
        alternatives=alternatives,
        assumptions=assumptions,
        warnings=warnings,
        errors=errors,
        request_metadata=request_metadata,
    )
    return {
        "success": report.success,
        "message": report.message,
        "summary": deepcopy(report.summary),
        "executive": deepcopy(report.executive),
        "engineering": deepcopy(report.engineering),
        "qa": deepcopy(report.qa),
        "alternatives": deepcopy(report.alternatives),
        "assumptions": deepcopy(report.assumptions),
        "exports": deepcopy(report.exports),
        "release": deepcopy(report.release),
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "content": deepcopy(s.content),
            }
            for s in report.sections
        ],
        "metadata": deepcopy(report.metadata),
    }
