from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, Iterable, List, Sequence


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def construction_package_record(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return the active construction package record from supported metadata aliases."""

    package = safe_dict(
        meta.get("construction_package_manifest")
        or meta.get("construction_package")
        or meta.get("construction_deliverable_package")
        or meta.get("deliverable_package")
    )
    if package:
        return dict(package)
    packages = safe_list(meta.get("deliverable_packages"))
    if packages:
        return dict(safe_dict(packages[-1]))
    return {}


def _humanize_blocker_code(value: Any) -> str:
    text = safe_str(value, "unknown blocker")
    return text.replace("_", " ").replace("-", " ").strip() or "unknown blocker"


def _blocker_detail(
    code: str,
    *,
    what_failed: str,
    why_it_matters: str,
    missing_data: Iterable[str] = (),
    next_action: str,
    engineer_review_required: bool = True,
) -> Dict[str, Any]:
    return {
        "code": code,
        "what_failed": what_failed,
        "why_it_matters": why_it_matters,
        "missing_data": [safe_str(item) for item in missing_data if safe_str(item)],
        "next_action": next_action,
        "engineer_review_required": bool(engineer_review_required),
    }


_STATIC_BLOCKER_EXPLANATIONS: Dict[str, Dict[str, Any]] = {
    "release_status_blocked": {
        "what_failed": "The release review explicitly marked this result as blocked.",
        "why_it_matters": "A blocked release status must win over any optimistic ready flag so Civora cannot publish a false-ready design.",
        "missing_data": ["release review approval or resolved blocking issue list"],
        "next_action": "Resolve the listed release blockers, rerun validation, and only then mark the release ready.",
        "engineer_review_required": True,
    },
    "release_review_not_ready": {
        "what_failed": "The release review did not approve the engineering result.",
        "why_it_matters": "The package may contain usable intermediate outputs, but it is not approved for export or construction-level reliance.",
        "missing_data": ["approved release review"],
        "next_action": "Run or complete the release review after all discipline blockers are resolved.",
        "engineer_review_required": True,
    },
    "final_plan_release_blocked": {
        "what_failed": "The final plan metadata says release readiness is false.",
        "why_it_matters": "Final plan metadata is part of the canonical truth used by exports, reports, and project summaries.",
        "missing_data": ["final plan release-ready flag with supporting evidence"],
        "next_action": "Regenerate the final plan after resolving blockers so release metadata matches the validated state.",
        "engineer_review_required": True,
    },
    "construction_readiness_missing": {
        "what_failed": "Construction readiness evidence is missing.",
        "why_it_matters": "Construction release cannot be trusted without a recorded readiness assessment across engineering systems.",
        "missing_data": ["construction_readiness assessment"],
        "next_action": "Run construction readiness validation and attach the result to the canonical model metadata.",
        "engineer_review_required": True,
    },
    "construction_readiness_blocked": {
        "what_failed": "Construction readiness validation found unresolved blockers.",
        "why_it_matters": "The design may still be useful for planning, but it is not safe to treat as construction-ready.",
        "missing_data": ["passing construction readiness blockers list"],
        "next_action": "Resolve the readiness blockers, rerun the affected engines, and rerun construction validation.",
        "engineer_review_required": True,
    },
    "construction_package_blocked": {
        "what_failed": "The construction package is not allowed for release.",
        "why_it_matters": "Reports, DXF, sheets, quantities, and review records must agree before Civora can claim a usable release package.",
        "missing_data": ["release_allowed construction package status"],
        "next_action": "Complete package assembly, artifact trace checks, and professional package review.",
        "engineer_review_required": True,
    },
    "construction_package_manifest_missing": {
        "what_failed": "The construction package manifest is missing.",
        "why_it_matters": "Without a manifest, deliverables cannot be tied back to a single canonical model and release audit.",
        "missing_data": ["construction package manifest"],
        "next_action": "Build the construction package manifest from the validated final model.",
        "engineer_review_required": True,
    },
    "construction_package_artifact_status_missing": {
        "what_failed": "Construction package artifact status is missing.",
        "why_it_matters": "Civora cannot prove which deliverables are present, stale, anonymous, or traceable.",
        "missing_data": ["construction_package_artifact_status"],
        "next_action": "Audit package artifacts and attach artifact status before release.",
        "engineer_review_required": True,
    },
    "construction_package_missing_artifacts": {
        "what_failed": "Required construction package artifacts are missing.",
        "why_it_matters": "A partial package can hide missing sheets, reports, profiles, quantities, or CAD output.",
        "missing_data": ["complete required construction artifacts"],
        "next_action": "Generate missing artifacts and rerun the construction package audit.",
        "engineer_review_required": True,
    },
    "construction_package_anonymous_artifacts": {
        "what_failed": "One or more package artifacts lack identity metadata.",
        "why_it_matters": "Anonymous deliverables cannot be safely traced, revised, or reviewed against the canonical model.",
        "missing_data": ["artifact IDs and canonical source references"],
        "next_action": "Rebuild artifacts with stable IDs and canonical model references.",
        "engineer_review_required": True,
    },
    "construction_package_stale_artifacts": {
        "what_failed": "One or more package artifacts are stale relative to the current model.",
        "why_it_matters": "Stale exports can show older geometry, quantities, or QA than the current canonical state.",
        "missing_data": ["fresh artifacts generated from the current model hash"],
        "next_action": "Regenerate stale artifacts after all downstream systems rerun.",
        "engineer_review_required": True,
    },
    "construction_package_model_reference_missing": {
        "what_failed": "The construction package lacks a canonical model reference.",
        "why_it_matters": "Deliverables must be tied to a known model ID/hash to prevent accidental release of mismatched outputs.",
        "missing_data": ["canonical model ID and model hash"],
        "next_action": "Attach canonical model references to the package and artifacts, then rerun package validation.",
        "engineer_review_required": True,
    },
    "construction_package_model_mismatch": {
        "what_failed": "The construction package model reference does not match the expected canonical model.",
        "why_it_matters": "A model mismatch means the package may represent the wrong design revision.",
        "missing_data": ["matching canonical model ID/hash across package and final model"],
        "next_action": "Regenerate the package from the current canonical model.",
        "engineer_review_required": True,
    },
    "construction_package_release_not_marked_ready": {
        "what_failed": "The package artifact audit is not marked release-ready.",
        "why_it_matters": "Every required artifact must pass package release gates before Civora can export a release package.",
        "missing_data": ["release_ready_flag true"],
        "next_action": "Resolve artifact status issues and rerun package audit until release_ready_flag is true.",
        "engineer_review_required": True,
    },
    "construction_package_production_not_marked_ready": {
        "what_failed": "The package artifact audit is not marked production-ready.",
        "why_it_matters": "Production readiness is stricter than preview readiness and protects against concept-only deliverables.",
        "missing_data": ["production_ready_flag true"],
        "next_action": "Replace concept/default outputs with production-traceable artifacts, then rerun the package audit.",
        "engineer_review_required": True,
    },
    "construction_package_incomplete_release": {
        "what_failed": "The construction package is incomplete for release.",
        "why_it_matters": "A release package must include all required deliverables and audits as one consistent package.",
        "missing_data": ["complete_for_release true"],
        "next_action": "Complete missing package sections and rerun construction package validation.",
        "engineer_review_required": True,
    },
    "construction_package_untraced_artifacts": {
        "what_failed": "One or more package artifacts are not traced to canonical IDs.",
        "why_it_matters": "Untraced artifacts cannot be proven to come from the validated engineering model.",
        "missing_data": ["canonical source IDs for every artifact"],
        "next_action": "Re-export untraced artifacts with canonical source mapping.",
        "engineer_review_required": True,
    },
    "construction_package_mismatched_artifacts": {
        "what_failed": "One or more package artifacts do not match the expected model reference.",
        "why_it_matters": "Mismatched artifacts can mix revisions and create incorrect drawings, quantities, or reports.",
        "missing_data": ["artifact model hash matching package model hash"],
        "next_action": "Regenerate mismatched artifacts from the current package model.",
        "engineer_review_required": True,
    },
    "construction_package_cost_untraced": {
        "what_failed": "Cost output is not fully traced to canonical quantities.",
        "why_it_matters": "Cost estimates are not reliable unless priced items tie back to model quantities and source IDs.",
        "missing_data": ["cost item source IDs"],
        "next_action": "Regenerate cost estimates from traceable quantity takeoff rows.",
        "engineer_review_required": True,
    },
    "construction_package_cost_mismatched": {
        "what_failed": "Cost output does not match the package model reference.",
        "why_it_matters": "A cost estimate from another revision can mislead pricing and construction decisions.",
        "missing_data": ["cost model hash matching package model hash"],
        "next_action": "Reprice the current package quantities and rerun cost trace validation.",
        "engineer_review_required": True,
    },
    "construction_professional_release_missing": {
        "what_failed": "Professional package release review is missing.",
        "why_it_matters": "Construction release requires a review record, not only generated artifacts.",
        "missing_data": ["professional package release status"],
        "next_action": "Attach professional package review status after engineer review.",
        "engineer_review_required": True,
    },
    "construction_professional_release_invalid": {
        "what_failed": "Professional package release review is invalid.",
        "why_it_matters": "The package cannot be treated as released if the professional review failed or is untrusted.",
        "missing_data": ["valid professional release status"],
        "next_action": "Resolve professional review failures and rerun package release validation.",
        "engineer_review_required": True,
    },
    "construction_professional_release_untraced": {
        "what_failed": "Professional package release review is not traced to the reviewed package/model.",
        "why_it_matters": "A review record must prove it applies to the exact package and model being released.",
        "missing_data": ["reviewed package ID and matching model/package trace"],
        "next_action": "Attach reviewed_package_id and matching model references to the professional review.",
        "engineer_review_required": True,
    },
    "reactive_post_rerun_not_ready": {
        "what_failed": "Reactive downstream validation is not ready after rerun.",
        "why_it_matters": "A change may have left grading, drainage, utilities, quantities, or exports stale.",
        "missing_data": ["passing post-rerun production readiness"],
        "next_action": "Rerun dirty downstream systems and block exports until post-rerun validation passes.",
        "engineer_review_required": True,
    },
    "planner_run_failed": {
        "what_failed": "The planner run failed.",
        "why_it_matters": "Failed orchestration can leave incomplete model state or missing discipline outputs.",
        "missing_data": ["successful planner execution"],
        "next_action": "Fix planner/runtime errors, rerun the workflow, and verify canonical outputs were produced.",
        "engineer_review_required": False,
    },
    "planner_errors_present": {
        "what_failed": "Planner errors were recorded during the run.",
        "why_it_matters": "Errors may mean some systems skipped, partially ran, or produced untrusted outputs.",
        "missing_data": ["zero planner errors"],
        "next_action": "Review planner errors, fix the failing stage, and rerun validation.",
        "engineer_review_required": False,
    },
    "report_errors_present": {
        "what_failed": "Report assembly recorded errors.",
        "why_it_matters": "A report with assembly errors may omit key QA, quantity, or release evidence.",
        "missing_data": ["error-free report build"],
        "next_action": "Fix report generation errors and rebuild the report from the current model.",
        "engineer_review_required": False,
    },
    "blocked_exports": {
        "what_failed": "One or more exports are blocked.",
        "why_it_matters": "Blocked exports indicate the deliverable would not truthfully represent the validated model.",
        "missing_data": ["passing export audit"],
        "next_action": "Resolve export blockers and rerun export validation before download or release.",
        "engineer_review_required": True,
    },
    "unresolved_conflicts": {
        "what_failed": "Unresolved engineering conflicts remain.",
        "why_it_matters": "Unresolved conflicts can represent physical clashes, invalid slopes, missing cover, or coordination failures.",
        "missing_data": ["resolved coordination conflicts"],
        "next_action": "Run conflict resolution or manually revise the design, then rerun coordination QA.",
        "engineer_review_required": True,
    },
    "failed_deliverables": {
        "what_failed": "One or more deliverables failed.",
        "why_it_matters": "The package cannot be considered complete if requested deliverables failed generation.",
        "missing_data": ["successful requested deliverables"],
        "next_action": "Regenerate failed deliverables and rerun package validation.",
        "engineer_review_required": False,
    },
    "missing_deliverables": {
        "what_failed": "One or more requested deliverables are missing.",
        "why_it_matters": "Missing deliverables can hide incomplete profiles, reports, sheets, CAD, or quantities.",
        "missing_data": ["all requested deliverables produced"],
        "next_action": "Generate missing deliverables and rerun the release audit.",
        "engineer_review_required": False,
    },
    "manual_validation_failures": {
        "what_failed": "Manual validation gates failed.",
        "why_it_matters": "Manual validation failures represent checks Civora cannot safely auto-clear.",
        "missing_data": ["passing manual validation gates"],
        "next_action": "Review the manual validation failures, revise the model, and rerun the validation gates.",
        "engineer_review_required": True,
    },
}


def blocker_explanation(code: Any) -> Dict[str, Any]:
    """Return a stable, user-facing explanation for a release/readiness blocker."""

    blocker_code = safe_str(code, "unknown_blocker").lower().replace(" ", "_")
    static = _STATIC_BLOCKER_EXPLANATIONS.get(blocker_code)
    if static:
        return _blocker_detail(blocker_code, **static)

    if blocker_code.startswith("failed_deliverable_"):
        deliverable = _humanize_blocker_code(blocker_code.removeprefix("failed_deliverable_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"The requested {deliverable} deliverable failed to generate.",
            why_it_matters="Failed deliverables cannot be included in a truthful release package.",
            missing_data=[f"successful {deliverable} deliverable"],
            next_action=f"Fix the {deliverable} generation path and regenerate the deliverable.",
            engineer_review_required=False,
        )

    if blocker_code.startswith("missing_deliverable_"):
        deliverable = _humanize_blocker_code(blocker_code.removeprefix("missing_deliverable_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"The requested {deliverable} deliverable is missing.",
            why_it_matters="The release package is incomplete until every requested deliverable is produced or explicitly removed from scope.",
            missing_data=[f"{deliverable} deliverable"],
            next_action=f"Generate the {deliverable} deliverable or remove it from the requested release scope.",
            engineer_review_required=False,
        )

    if blocker_code.startswith("manual_validation_"):
        check = _humanize_blocker_code(blocker_code.removeprefix("manual_validation_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"Manual validation failed for {check}.",
            why_it_matters="Manual validation failures are explicit engineering review gates and cannot be auto-cleared by optimistic metadata.",
            missing_data=[f"passing manual validation for {check}"],
            next_action="Review the failed manual gate, correct the model or assumptions, and rerun validation.",
            engineer_review_required=True,
        )

    if blocker_code.startswith("construction_package_"):
        package_issue = _humanize_blocker_code(blocker_code.removeprefix("construction_package_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"Construction package validation failed: {package_issue}.",
            why_it_matters="Construction package gates prove that deliverables, model references, quantities, and release flags all match.",
            missing_data=[f"resolved construction package {package_issue}"],
            next_action="Fix the construction package audit issue and rebuild the package from the current canonical model.",
            engineer_review_required=True,
        )

    if blocker_code.startswith("construction_professional_release_"):
        release_issue = _humanize_blocker_code(blocker_code.removeprefix("construction_professional_release_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"Professional release validation failed: {release_issue}.",
            why_it_matters="Professional release records must be valid and tied to the exact package before construction claims are allowed.",
            missing_data=[f"valid professional release {release_issue} evidence"],
            next_action="Correct the professional release record and rerun release validation.",
            engineer_review_required=True,
        )

    if blocker_code.startswith("latest_"):
        issue = _humanize_blocker_code(blocker_code.removeprefix("latest_"))
        return _blocker_detail(
            blocker_code,
            what_failed=f"The latest workflow state is blocked: {issue}.",
            why_it_matters="Project summaries use the latest run/artifact state to decide whether the workspace is safe to rely on.",
            missing_data=[f"resolved latest {issue} state"],
            next_action="Resolve the latest run or artifact blocker and save a fresh validated result.",
            engineer_review_required=True,
        )

    issue = _humanize_blocker_code(blocker_code)
    return _blocker_detail(
        blocker_code,
        what_failed=f"Readiness is blocked by {issue}.",
        why_it_matters="Unknown blockers are preserved rather than hidden so Civora does not silently claim readiness.",
        missing_data=[f"resolved {issue} evidence"],
        next_action="Inspect the source blocker, resolve the underlying issue, and rerun validation.",
        engineer_review_required=True,
    )


def blocker_explanations(codes: Iterable[Any]) -> List[Dict[str, Any]]:
    """Return de-duplicated explanations for blocker codes in first-seen order."""

    details: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for code in codes:
        detail = blocker_explanation(code)
        detail_code = safe_str(detail.get("code"))
        if not detail_code or detail_code in seen:
            continue
        seen.add(detail_code)
        details.append(detail)
    return details


def _readiness_issue_code(record: Dict[str, Any]) -> str:
    area = safe_str(record.get("area") or record.get("system") or record.get("engine"))
    field = safe_str(record.get("field") or record.get("code") or record.get("blocker"))
    if area and field:
        return f"{area}_{field}".lower().replace(" ", "_")
    if field:
        return field.lower().replace(" ", "_")
    message = safe_str(record.get("message") or record.get("reason") or record.get("why_needed"))
    if message:
        return message[:80].lower().replace(" ", "_")
    return "readiness_issue"


def readiness_issue_explanation(issue: Any) -> Dict[str, Any]:
    """Explain a structured readiness blocker without losing area/field context."""

    record = safe_dict(issue)
    if not record:
        return blocker_explanation(issue)
    code = _readiness_issue_code(record)
    area = safe_str(record.get("area") or record.get("system") or record.get("engine"))
    field = safe_str(record.get("field") or record.get("code") or record.get("blocker"))
    message = safe_str(record.get("message") or record.get("reason") or record.get("why_needed"))
    human = _humanize_blocker_code(field or area or code)
    what_failed = message or f"{human} is incomplete or blocked."
    why_it_matters = safe_str(record.get("why_it_matters") or record.get("why_needed"))
    if not why_it_matters:
        scope = _humanize_blocker_code(area or "engineering")
        why_it_matters = (
            f"{scope} cannot be treated as production-ready until this evidence is resolved and tied to canonical state."
        )
    raw_missing = (
        safe_list(record.get("missing_data"))
        or safe_list(record.get("missing"))
        or safe_list(record.get("required"))
    )
    missing_data = [safe_str(item) for item in raw_missing if safe_str(item)]
    if not missing_data:
        missing_data = [human]
    next_action = safe_str(
        record.get("next_action")
        or record.get("suggested_next_action")
        or record.get("action")
        or record.get("fix")
    )
    if not next_action:
        next_action = f"Provide or regenerate {human} evidence, then rerun the affected validation gates."
    severity = safe_str(record.get("severity"), "blocker").lower()
    detail = _blocker_detail(
        code,
        what_failed=what_failed,
        why_it_matters=why_it_matters,
        missing_data=missing_data,
        next_action=next_action,
        engineer_review_required=severity != "warning",
    )
    if area:
        detail["area"] = area
    if field:
        detail["field"] = field
    if severity:
        detail["severity"] = severity
    return detail


def readiness_issue_explanations(issues: Iterable[Any]) -> List[Dict[str, Any]]:
    """Return de-duplicated explanations for structured readiness blocker records."""

    details: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        detail = readiness_issue_explanation(issue)
        code = safe_str(detail.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        details.append(detail)
    return details


_CANONICAL_STAGE_KEYS: Dict[str, tuple[str, str]] = {
    "grading": ("grading_summary", "grading"),
    "drainage": ("drainage_canonical", "drainage"),
    "storm": ("storm_pipe_summary", "storm_pipe_summary"),
    "storm_pipes": ("storm_pipe_summary", "storm_pipe_summary"),
    "storm_pipe_summary": ("storm_pipe_summary", "storm_pipe_summary"),
    "sanitary": ("sanitary_summary", "sanitary"),
    "utilities": ("utility_summary", "utilities"),
    "utility_network": ("utility_summary", "utilities"),
    "coordination": ("coordination_summary", "coordination"),
    "parking_program": ("parking_program", "parking_program"),
    "profiles": ("profiles", "profiles"),
    "cross_sections": ("cross_sections", "cross_sections"),
    "alignments": ("alignments", "alignments"),
}


_INTEGRITY_STAGE_ALIASES: Dict[str, str] = {
    "storm": "storm_pipes",
    "storm_pipe": "storm_pipes",
    "storm_pipe_summary": "storm_pipes",
    "storm_pipe_gate": "storm_pipes",
    "utility": "utilities",
    "utility_network": "utilities",
    "utility_gate": "utilities",
    "coordination_resolution": "coordination",
    "coordination_gate": "coordination",
    "quantities": "qa",
    "quantity": "qa",
    "export": "sheets",
    "export_cad": "sheets",
    "profile_section": "sheets",
}


def canonical_stage_name(stage: Any) -> str:
    key = safe_str(stage).strip().lower()
    return _INTEGRITY_STAGE_ALIASES.get(key, key)


def bounded_copy(value: Any, *, max_depth: int = 8, max_items: int = 600) -> Any:
    """Copy JSON-like stage payloads without chasing huge/cyclic graphs.

    Canonical stage summaries can include rich engine metadata. During
    coordination solving these summaries are read repeatedly for candidate
    snapshots, so an unbounded ``deepcopy`` can become the bottleneck or hang on
    accidental cycles. This helper preserves normal scalar/list/dict payloads
    while placing a hard ceiling on traversal.
    """

    seen: set[int] = set()

    def _copy(item: Any, depth: int) -> Any:
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        if depth <= 0:
            return "<truncated>"
        item_id = id(item)
        if item_id in seen:
            return "<cycle>"
        if isinstance(item, dict):
            seen.add(item_id)
            out: Dict[Any, Any] = {}
            for index, (key, nested) in enumerate(item.items()):
                if index >= max_items:
                    out["__truncated__"] = True
                    out["__truncated_count__"] = max(0, len(item) - max_items)
                    break
                out[key] = _copy(nested, depth - 1)
            seen.discard(item_id)
            return out
        if isinstance(item, (list, tuple)):
            seen.add(item_id)
            out = [_copy(nested, depth - 1) for nested in list(item)[:max_items]]
            if len(item) > max_items:
                out.append({"__truncated__": True, "__truncated_count__": len(item) - max_items})
            seen.discard(item_id)
            return out
        return str(item)

    return _copy(value, max_depth)


def _bounded_differs(left: Any, right: Any) -> bool:
    return bounded_copy(left, max_depth=3, max_items=80) != bounded_copy(right, max_depth=3, max_items=80)


def canonical_stage_output(project: Any, manager: Any, stage: str) -> Any:
    """Return accepted canonical stage state.

    ProjectModel.meta is authoritative. ProjectManager.latest_outputs is a
    convenience cache and is only used when project.meta does not contain an
    accepted value yet.
    """

    stage_key = safe_str(stage)
    meta_key, cache_key = _CANONICAL_STAGE_KEYS.get(stage_key, (stage_key, stage_key))
    project_meta = safe_dict(getattr(project, "meta", {}))
    latest_outputs = safe_dict(getattr(manager, "latest_outputs", {}))
    has_meta_value = meta_key in project_meta and project_meta.get(meta_key) is not None
    has_cache_value = cache_key in latest_outputs and latest_outputs.get(cache_key) is not None

    if has_meta_value:
        canonical_value = project_meta.get(meta_key)
        if has_cache_value and _bounded_differs(latest_outputs.get(cache_key), canonical_value):
            warnings = project_meta.setdefault("canonical_state_warnings", {})
            warnings[stage_key] = {
                "stage": stage_key,
                "canonical_meta_key": meta_key,
                "cache_key": cache_key,
                "cache_differs": True,
                "message": "manager.latest_outputs differs from project.meta; using project.meta as canonical accepted state.",
            }
        else:
            safe_dict(project_meta.get("canonical_state_warnings")).pop(stage_key, None)
        return bounded_copy(canonical_value)

    if has_cache_value:
        warnings = project_meta.setdefault("canonical_state_warnings", {})
        warnings[stage_key] = {
            "stage": stage_key,
            "canonical_meta_key": meta_key,
            "cache_key": cache_key,
            "cache_only": True,
            "message": "project.meta has no accepted stage summary; using manager.latest_outputs cache fallback.",
        }
        return bounded_copy(latest_outputs.get(cache_key))

    return [] if stage_key in {"profiles", "cross_sections", "alignments"} else {}


def canonical_state_integrity(
    project: Any,
    manager: Any = None,
    *,
    required_stages: Sequence[str] | None = None,
    completed_stages: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Summarize whether canonical state is export/signoff safe.

    ``project.meta`` remains the accepted source of truth. This helper does not
    replace canonical values with cache data; it only reports cases that should
    block production claims, such as cache-only stage output or dirty downstream
    systems.
    """

    project_meta = safe_dict(getattr(project, "meta", {}))
    latest_outputs = safe_dict(getattr(manager, "latest_outputs", {}) if manager is not None else {})
    requested = dedupe_keep_order([canonical_stage_name(item) for item in safe_list(list(required_stages or [])) if safe_str(item)])
    completed = {
        canonical_stage_name(item)
        for item in safe_list(list(completed_stages or []))
        if safe_str(item)
    }
    warning_records: Dict[str, Any] = {
        safe_str(stage): safe_dict(record)
        for stage, record in safe_dict(project_meta.get("canonical_state_warnings")).items()
        if safe_str(stage)
    }

    for stage_key in requested:
        canonical_stage = canonical_stage_name(stage_key)
        meta_key, cache_key = _CANONICAL_STAGE_KEYS.get(canonical_stage, (canonical_stage, canonical_stage))
        has_meta_value = meta_key in project_meta and project_meta.get(meta_key) is not None
        has_cache_value = cache_key in latest_outputs and latest_outputs.get(cache_key) is not None
        if not has_meta_value and has_cache_value:
            warning_records.setdefault(
                canonical_stage,
                {
                    "stage": canonical_stage,
                    "canonical_meta_key": meta_key,
                    "cache_key": cache_key,
                    "cache_only": True,
                    "message": "project.meta has no accepted stage summary; manager cache cannot be treated as canonical truth.",
                },
            )

    cache_only_stages = sorted(
        stage for stage, record in warning_records.items() if bool(safe_dict(record).get("cache_only"))
    )
    cache_differs_stages = sorted(
        stage for stage, record in warning_records.items() if bool(safe_dict(record).get("cache_differs"))
    )

    dirty_rows: Dict[str, Any] = {}
    for source in (
        safe_dict(project_meta.get("system_dirty_state")),
        safe_dict(getattr(manager, "system_dirty_state", {}) if manager is not None else {}),
    ):
        for name, record in source.items():
            key = canonical_stage_name(name)
            if not key:
                continue
            if key in completed:
                continue
            row = safe_dict(record) if isinstance(record, dict) else {"state": record}
            state_value = safe_str(row.get("state"), row.get("status") or row.get("value") or "")
            if state_value.lower() in {"dirty", "stale", "invalid", "not_generated", "failed"}:
                dirty_rows[key] = {
                    "state": state_value.lower(),
                    "reasons": [safe_str(item) for item in safe_list(row.get("reasons")) if safe_str(item)],
                    "source": safe_str(row.get("source")),
                }

    invalid_targets: List[str] = []
    if manager is not None and hasattr(manager, "get_invalidated_targets"):
        try:
            invalid_targets = [safe_str(item) for item in manager.get_invalidated_targets() if safe_str(item)]
        except Exception:
            invalid_targets = []
    invalid_targets = sorted({target for target in invalid_targets if canonical_stage_name(target) not in completed})

    blocking_reasons: List[str] = []
    for stage in cache_only_stages:
        blocking_reasons.append(f"{stage}: accepted canonical summary missing; cache-only output cannot be trusted.")
    for stage in sorted(dirty_rows):
        reason = "; ".join(safe_list(safe_dict(dirty_rows.get(stage)).get("reasons")))
        blocking_reasons.append(f"{stage}: system is {safe_dict(dirty_rows.get(stage)).get('state')}{f' ({reason})' if reason else ''}.")
    for target in invalid_targets:
        blocking_reasons.append(f"{target}: dependency graph marks this target stale or invalid.")

    return {
        "version": "canonical_integrity_v1",
        "blocked": bool(cache_only_stages or dirty_rows or invalid_targets),
        "cache_only_stages": cache_only_stages,
        "cache_differs_stages": cache_differs_stages,
        "dirty_stages": sorted(dirty_rows.keys()),
        "dirty_state": dirty_rows,
        "invalidated_targets": invalid_targets,
        "warnings": warning_records,
        "blocking_reasons": dedupe_keep_order(blocking_reasons),
    }


def lower_text(value: Any) -> str:
    return safe_str(value).lower()


def dedupe_keep_order(items: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def polyline_length(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        x1, y1 = safe_float(points[i - 1][0]), safe_float(points[i - 1][1])
        x2, y2 = safe_float(points[i][0]), safe_float(points[i][1])
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def rect_area(width: Any, height: Any) -> float:
    return max(0.0, safe_float(width, 0.0)) * max(0.0, safe_float(height, 0.0))


def _call_with_compatible_kwargs(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(*args, **kwargs)
    filtered = {k: v for k, v in kwargs.items() if k in params}
    return fn(*args, **filtered)


def _install_rect_obstacle_compatibility() -> None:
    try:
        geom_mod = importlib.import_module("core.geometry_core")
        rect_obstacle = getattr(geom_mod, "rect_obstacle", None)
        if rect_obstacle is None:
            return

        sig = inspect.signature(rect_obstacle)
        if getattr(rect_obstacle, "_codex_compat_wrapped", False):
            return

        supported_kwargs = {name for name in sig.parameters if name not in {"x", "y", "width", "height", "w", "h"}}

        def rect_obstacle_compat(x: float, y: float, w: float, h: float, **kwargs: Any) -> Any:
            filtered = {key: value for key, value in kwargs.items() if key in supported_kwargs}
            try:
                return rect_obstacle(x, y, w, h, **filtered)
            except Exception:
                if not filtered:
                    raise
            return {
                "type": "rectangle",
                "x": float(x),
                "y": float(y),
                "w": float(w),
                "h": float(h),
                **filtered,
            }

        setattr(rect_obstacle_compat, "_codex_compat_wrapped", True)
        setattr(geom_mod, "rect_obstacle", rect_obstacle_compat)
    except Exception:
        return
