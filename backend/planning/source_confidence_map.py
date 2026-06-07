from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
from typing import Any, Dict, Iterable, List, Optional

from .candidate_review_inbox import build_candidate_review_inbox
from .common import safe_dict, safe_float, safe_list, safe_str


SOURCE_CONFIDENCE_MAP_VERSION = "source_confidence_map_v1"

CONFIDENCE_LABELS = {
    "survey-backed",
    "survey-unverified",
    "GIS candidate",
    "official GIS source",
    "map imagery candidate",
    "user-drawn",
    "imported CAD",
    "DEM-backed",
    "LiDAR-backed",
    "inferred",
    "metadata-only",
    "missing",
    "stale/dirty",
}


def _stable_id(*parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    if not seed:
        seed = "source-confidence"
    return f"scm_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"


def _dedupe(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _score(label: str, *, verified: bool = False, accepted: bool = False, stale: bool = False, dirty: bool = False) -> float:
    base = {
        "survey-backed": 0.92,
        "official GIS source": 0.76,
        "LiDAR-backed": 0.72,
        "DEM-backed": 0.64,
        "imported CAD": 0.55,
        "user-drawn": 0.48,
        "GIS candidate": 0.42,
        "map imagery candidate": 0.36,
        "survey-unverified": 0.34,
        "inferred": 0.28,
        "metadata-only": 0.18,
        "stale/dirty": 0.12,
        "missing": 0.0,
    }.get(label, 0.25)
    if accepted:
        base += 0.06
    if verified:
        base += 0.08
    if stale:
        base -= 0.18
    if dirty:
        base -= 0.22
    return round(max(0.0, min(1.0, base)), 3)


def _is_official_source(rec: Dict[str, Any]) -> bool:
    text = " ".join(
        safe_str(rec.get(key)).lower()
        for key in ("source", "provider", "source_type", "source_url", "authority", "agency", "source_name")
    )
    return any(token in text for token in ("official", ".gov", "fema", "usgs", "usfws", "county", "city", "dot"))


def _entry(
    *,
    entry_id: str,
    label: str,
    category: str,
    source_type: str,
    source_name: str = "",
    object_id: str = "",
    layer: str = "",
    status: str = "review",
    evidence: Optional[Dict[str, Any]] = None,
    reasons: Optional[Iterable[Any]] = None,
    next_action: str = "",
    needs_survey_control: bool = False,
    needs_verification: bool = True,
    accepted: bool = False,
    verified: bool = False,
    stale: bool = False,
    dirty: bool = False,
    missing: bool = False,
) -> Dict[str, Any]:
    normalized = source_type if source_type in CONFIDENCE_LABELS else "inferred"
    reason_list = _dedupe(reasons or [])
    if missing and "Source evidence is missing." not in reason_list:
        reason_list.append("Source evidence is missing.")
    if needs_survey_control and "Survey/control verification is required before this can be trusted for engineering decisions." not in reason_list:
        reason_list.append("Survey/control verification is required before this can be trusted for engineering decisions.")
    if normalized in {"GIS candidate", "map imagery candidate"} and "Candidate evidence must be reviewed before it can become project draft evidence." not in reason_list:
        reason_list.append("Candidate evidence must be reviewed before it can become project draft evidence.")
    if normalized == "user-drawn" and "User-drawn geometry is visible draft evidence, not survey/control truth." not in reason_list:
        reason_list.append("User-drawn geometry is visible draft evidence, not survey/control truth.")
    if stale and "Source evidence is stale and needs refresh before reliance." not in reason_list:
        reason_list.append("Source evidence is stale and needs refresh before reliance.")
    if dirty and "Generated state is stale/dirty and needs rerun before relying on outputs." not in reason_list:
        reason_list.append("Generated state is stale/dirty and needs rerun before relying on outputs.")
    score = _score(normalized, verified=verified, accepted=accepted, stale=stale, dirty=dirty)
    if score >= 0.75:
        trust = "higher"
    elif score >= 0.45:
        trust = "review"
    elif score > 0:
        trust = "low"
    else:
        trust = "missing"
    return {
        "entry_id": entry_id or _stable_id(label, category, source_name, object_id, layer),
        "label": label,
        "category": category,
        "object_id": object_id,
        "layer": layer,
        "source_type": normalized,
        "source_name": source_name or "unknown",
        "confidence_score": score,
        "confidence_band": trust,
        "visible_badge": f"{normalized} · {trust}",
        "status": "missing" if missing else "stale_dirty" if stale or dirty else status,
        "accepted": bool(accepted),
        "verified": bool(verified),
        "needs_verification": bool(needs_verification),
        "needs_survey_control": bool(needs_survey_control),
        "stale": bool(stale),
        "dirty": bool(dirty),
        "missing": bool(missing),
        "low_confidence_reasons": reason_list,
        "why_low_confidence": "; ".join(reason_list),
        "next_action": next_action or "Verify the source, attach evidence, or keep this item review-only.",
        "evidence": deepcopy(evidence or {}),
        "construction_release_allowed": False,
        "construction_readiness_implied": False,
        "truth_label": "Source confidence is transparency for review. It does not certify construction readiness or professional approval.",
    }


def _survey_control_verified(meta: Dict[str, Any]) -> bool:
    control = (
        safe_dict(meta.get("survey_control_package"))
        or safe_dict(safe_dict(meta.get("existing_conditions_package")).get("survey_control_package"))
        or safe_dict(
            safe_dict(safe_dict(meta.get("existing_conditions_summary")).get("survey")).get("survey_control_package")
        )
    )
    return bool(control.get("control_verified") or control.get("production_usable") is True or control.get("status") in {"verified", "ready"})


def _existing_condition_entries(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    verified_control = _survey_control_verified(meta)
    existing_package = safe_dict(meta.get("existing_conditions_package"))
    summary = safe_dict(existing_package.get("summary") or meta.get("existing_conditions_summary"))
    survey = safe_dict(summary.get("survey") or meta.get("survey"))
    if survey:
        label = "survey-backed" if verified_control else "survey-unverified"
        entries.append(
            _entry(
                entry_id=_stable_id("survey", survey.get("source")),
                label="Survey / topo",
                category="source",
                source_type=label,
                source_name=safe_str(survey.get("source") or safe_dict(meta.get("survey")).get("source"), "survey"),
                status="trusted_review" if verified_control else "low_confidence",
                evidence=survey,
                verified=verified_control,
                accepted=bool(existing_package.get("accepted")),
                needs_survey_control=not verified_control,
                needs_verification=not verified_control,
                reasons=[] if verified_control else ["Survey-like data exists but verified survey/control is not attached."],
                next_action="Attach verified survey/control with benchmark, datum, CRS, and control verification.",
            )
        )
    else:
        entries.append(
            _entry(
                entry_id="scm_missing_survey_control",
                label="Survey / topo",
                category="source",
                source_type="missing",
                source_name="missing",
                missing=True,
                needs_survey_control=True,
                reasons=["No survey/topo evidence is attached."],
                next_action="Upload survey/topo/control or explicitly keep outputs review-only.",
            )
        )

    terrain = safe_dict(existing_package.get("terrain_source_confidence"))
    terrain_label = safe_str(terrain.get("label"))
    if terrain_label:
        source_type = "DEM-backed"
        if "lidar" in terrain_label.lower():
            source_type = "LiDAR-backed"
        if terrain_label == "survey-backed" and verified_control:
            source_type = "survey-backed"
        elif terrain_label == "survey-backed":
            source_type = "survey-unverified"
        elif terrain_label in {"missing", "metadata_only", "metadata-only"}:
            source_type = "metadata-only" if "metadata" in terrain_label else "missing"
        entries.append(
            _entry(
                entry_id=_stable_id("terrain", terrain_label),
                label="Terrain surface",
                category="layer",
                layer="terrain",
                source_type=source_type,
                source_name=terrain_label,
                evidence=terrain,
                needs_survey_control=source_type != "survey-backed",
                needs_verification=source_type != "survey-backed",
                missing=source_type == "missing",
                reasons=[] if source_type == "survey-backed" else ["Terrain is not verified survey/control-backed."],
                next_action="Verify terrain against survey/control or attach accepted LiDAR/DEM evidence with limits.",
            )
        )
    for source in safe_list(existing_package.get("metadata_only_sources") or meta.get("metadata_only_sources")):
        rec = safe_dict(source)
        entries.append(
            _entry(
                entry_id=_stable_id("metadata", rec.get("source") or rec),
                label=safe_str(rec.get("label") or rec.get("source_type"), "Metadata-only source"),
                category="source",
                source_type="metadata-only",
                source_name=safe_str(rec.get("source") or rec.get("file_name"), "metadata-only"),
                evidence=rec,
                reasons=["The source records metadata but no parsed usable geometry/evidence."],
                next_action="Attach parsed survey/GIS/terrain data or remove this as evidence.",
            )
        )
    return entries


def _candidate_entries(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    inbox = safe_dict(meta.get("candidate_review_inbox_v1") or build_candidate_review_inbox(meta))
    entries: List[Dict[str, Any]] = []
    for candidate in safe_list(inbox.get("candidates")):
        rec = safe_dict(candidate)
        ctype = safe_str(rec.get("candidate_type"))
        if ctype == "standards":
            continue
        source_type = "official GIS source" if _is_official_source(rec) and rec.get("status") == "accepted" else "GIS candidate"
        if safe_str(rec.get("provider")).lower().find("imagery") >= 0 or safe_str(rec.get("source")).lower().find("imagery") >= 0:
            source_type = "map imagery candidate"
        entries.append(
            _entry(
                entry_id=safe_str(rec.get("candidate_id")) or _stable_id("candidate", rec.get("label")),
                label=safe_str(rec.get("label") or ctype, "Source candidate"),
                category="candidate",
                source_type=source_type,
                source_name=safe_str(rec.get("source") or rec.get("provider")),
                object_id=safe_str(rec.get("accepted_as") or rec.get("candidate_id")),
                status=safe_str(rec.get("status"), "pending"),
                accepted=rec.get("status") == "accepted",
                evidence=rec,
                reasons=[rec.get("blocker_review_reason")],
                next_action="Accept/reject the candidate, then verify it against survey/control before engineering reliance.",
                needs_survey_control=True,
            )
        )
    return entries


def _standards_entries(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    package = safe_dict(meta.get("standards_package"))
    if package:
        blockers = safe_list(package.get("blockers"))
        stale = any("stale" in safe_str(item).lower() for item in blockers) or bool(package.get("stale"))
        official = bool(safe_dict(package.get("selected_standards_source")).get("official_source") or package.get("production_usable"))
        entries.append(
            _entry(
                entry_id="scm_standards_package",
                label="Standards basis",
                category="standards",
                source_type="official GIS source" if official and not stale else "stale/dirty" if stale else "inferred",
                source_name=safe_str(safe_dict(package.get("selected_standards_source")).get("source_url") or package.get("source"), "standards package"),
                status=safe_str(package.get("status"), "review"),
                accepted=bool(package.get("accepted") or package.get("production_usable")),
                stale=stale,
                evidence=package,
                reasons=[safe_str(item.get("reason") or item.get("message")) if isinstance(item, dict) else item for item in blockers],
                next_action="Refresh stale standards and accept official-source rules before relying on standards QA.",
                needs_survey_control=False,
            )
        )
    inbox = safe_dict(meta.get("candidate_review_inbox_v1") or build_candidate_review_inbox(meta))
    for candidate in safe_list(inbox.get("candidates")):
        rec = safe_dict(candidate)
        if safe_str(rec.get("candidate_type")) != "standards":
            continue
        entries.append(
            _entry(
                entry_id=safe_str(rec.get("candidate_id")) or _stable_id("standards", rec.get("label")),
                label=safe_str(rec.get("label"), "Standards candidate"),
                category="standards",
                source_type="inferred" if rec.get("status") != "accepted" else "official GIS source",
                source_name=safe_str(rec.get("source") or rec.get("source_url"), "standards candidate"),
                status=safe_str(rec.get("status"), "pending"),
                accepted=rec.get("status") == "accepted",
                evidence=rec,
                reasons=[rec.get("blocker_review_reason")],
                next_action="Accept official-source standards rules or leave them visible as candidates.",
                needs_survey_control=False,
            )
        )
    return entries


def _drawn_imported_entries(meta: Dict[str, Any], project_input: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    project_input = safe_dict(project_input)
    manual = safe_dict(project_input.get("manual_fields"))
    handoffs = safe_list(manual.get("canonical_geometry_handoff_v1")) + safe_list(project_input.get("canonical_geometry_handoff_v1"))
    for source in (manual, project_input, meta):
        for item in safe_list(safe_dict(source).get("site_objects")) + safe_list(safe_dict(source).get("buildings")):
            rec = safe_dict(item)
            handoff = safe_dict(rec.get("canonical_geometry_handoff_v1"))
            if handoff:
                handoffs.append(handoff)
            elif rec:
                entries.append(
                    _entry(
                        entry_id=_stable_id("object", rec.get("id") or rec.get("name")),
                        label=safe_str(rec.get("label") or rec.get("name") or rec.get("type"), "Draft object"),
                        category="object",
                        object_id=safe_str(rec.get("id")),
                        source_type="user-drawn" if safe_str(rec.get("source")) in {"manual_drawn", "user", "user_drawn"} else "inferred",
                        source_name=safe_str(rec.get("source"), "user"),
                        evidence=rec,
                        needs_survey_control=True,
                        reasons=["Object has no verified source confidence handoff attached."],
                        next_action="Attach canonical geometry handoff and verify against survey/control before relying on location.",
                    )
                )
    seen = set()
    for handoff in handoffs:
        rec = safe_dict(handoff)
        key = safe_str(rec.get("object_id") or rec.get("geometry_id"))
        if not key or key in seen:
            continue
        seen.add(key)
        entries.append(
            _entry(
                entry_id=_stable_id("handoff", key),
                label=safe_str(rec.get("object_name") or rec.get("object_type"), "User drawn geometry"),
                category="object",
                object_id=safe_str(rec.get("object_id")),
                layer=safe_str(rec.get("object_type")),
                source_type="user-drawn",
                source_name="canvas_draw",
                status=safe_str(rec.get("engineering_status"), "draft_review_required"),
                evidence=rec,
                needs_survey_control=True,
                reasons=safe_list(rec.get("blockers")),
                next_action="Verify drawn geometry against survey/control or keep it as draft review-required geometry.",
            )
        )
    for source in safe_list(meta.get("imports") or meta.get("cad_imports") or safe_dict(meta.get("existing_conditions_import")).get("sources")):
        rec = safe_dict(source)
        source_text = safe_str(rec.get("source_type") or rec.get("file_name") or rec.get("source"))
        is_cad = any(token in source_text.lower() for token in ("cad", "dwg", "dxf"))
        if not is_cad:
            continue
        entries.append(
            _entry(
                entry_id=_stable_id("cad", source_text),
                label=safe_str(rec.get("label"), "Imported CAD"),
                category="source",
                source_type="imported CAD",
                source_name=source_text,
                evidence=rec,
                needs_survey_control=True,
                reasons=["Imported CAD needs source/control verification before location reliance."],
                next_action="Tie CAD import to verified project control and accepted layer standards.",
            )
        )
    return entries


def _production_entries(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    production = safe_dict(meta.get("production_evidence"))
    if production:
        blockers = safe_list(production.get("blockers"))
        entries.append(
            _entry(
                entry_id="scm_production_evidence",
                label="Production evidence assembly",
                category="production_evidence",
                source_type="stale/dirty" if blockers or production.get("production_evidence_ready") is False else "inferred",
                source_name="production_evidence_v1",
                status="blocked" if blockers or production.get("production_evidence_ready") is False else "review",
                evidence=production,
                dirty=bool(blockers or production.get("production_evidence_ready") is False),
                reasons=[safe_str(item.get("reason") or item.get("message")) if isinstance(item, dict) else item for item in blockers],
                next_action="Resolve production evidence blockers; keep outputs review-only until external approval.",
                needs_survey_control=not _survey_control_verified(meta),
            )
        )
    reactive = safe_dict(meta.get("reactive_update_report"))
    stale_outputs = safe_list(reactive.get("stale_outputs") or reactive.get("post_rerun_stale_outputs"))
    for name in stale_outputs:
        entries.append(
            _entry(
                entry_id=_stable_id("stale", name),
                label=f"Stale output: {safe_str(name)}",
                category="production_evidence",
                source_type="stale/dirty",
                source_name="reactive_update_report",
                dirty=True,
                stale=True,
                reasons=[f"{safe_str(name)} is marked stale by reactive update evidence."],
                next_action="Run the dependency-aware rerun before export/reliance.",
            )
        )
    return entries


def _summary(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts_by_type: Dict[str, int] = {}
    counts_by_band: Dict[str, int] = {}
    for entry in entries:
        counts_by_type[safe_str(entry.get("source_type"))] = counts_by_type.get(safe_str(entry.get("source_type")), 0) + 1
        counts_by_band[safe_str(entry.get("confidence_band"))] = counts_by_band.get(safe_str(entry.get("confidence_band")), 0) + 1
    low = [entry for entry in entries if entry.get("confidence_band") in {"low", "missing"} or entry.get("stale") or entry.get("dirty")]
    user_drawn = [entry for entry in entries if entry.get("source_type") == "user-drawn"]
    needs_control = [entry for entry in entries if entry.get("needs_survey_control")]
    stale_missing = [entry for entry in entries if entry.get("stale") or entry.get("dirty") or entry.get("missing")]
    trusted = [entry for entry in entries if entry.get("confidence_band") == "higher"]
    return {
        "entry_count": len(entries),
        "counts_by_source_type": counts_by_type,
        "counts_by_confidence_band": counts_by_band,
        "trusted_count": len(trusted),
        "low_confidence_count": len(low),
        "user_drawn_count": len(user_drawn),
        "needs_survey_control_count": len(needs_control),
        "stale_or_missing_count": len(stale_missing),
        "highest_confidence_labels": [safe_str(entry.get("label")) for entry in trusted[:6]],
        "low_confidence_labels": [safe_str(entry.get("label")) for entry in low[:8]],
        "user_drawn_labels": [safe_str(entry.get("label")) for entry in user_drawn[:8]],
        "needs_survey_control_labels": [safe_str(entry.get("label")) for entry in needs_control[:8]],
        "stale_or_missing_labels": [safe_str(entry.get("label")) for entry in stale_missing[:8]],
    }


def build_source_confidence_map(plan_or_meta: Dict[str, Any], *, project_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    entries: List[Dict[str, Any]] = []
    entries.extend(_existing_condition_entries(meta))
    entries.extend(_candidate_entries(meta))
    entries.extend(_standards_entries(meta))
    entries.extend(_drawn_imported_entries(meta, project_input))
    entries.extend(_production_entries(meta))
    by_id: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        entry_id = safe_str(entry.get("entry_id")) or _stable_id(entry.get("label"), entry.get("source_name"))
        by_id[entry_id] = entry
    ordered = sorted(by_id.values(), key=lambda item: (safe_float(item.get("confidence_score"), 0.0), safe_str(item.get("label"))))
    summary = _summary(ordered)
    return {
        "version": SOURCE_CONFIDENCE_MAP_VERSION,
        "generated_on": date.today().isoformat(),
        "entries": ordered,
        "summary": summary,
        "answer_cards": {
            "what_can_i_trust": summary["highest_confidence_labels"] or ["Nothing is marked high-confidence yet; verify survey/control and accepted official sources."],
            "why_low_confidence": summary["low_confidence_labels"],
            "what_is_user_drawn": summary["user_drawn_labels"],
            "what_needs_survey_control": summary["needs_survey_control_labels"],
            "show_stale_or_missing_sources": summary["stale_or_missing_labels"],
        },
        "construction_release_allowed": False,
        "construction_readiness_implied": False,
        "truth_label": "Every visible source remains review evidence unless verified survey/control, accepted official sources, current outputs, and external professional approval are present.",
    }


def attach_source_confidence_map(
    latest_result: Dict[str, Any],
    *,
    project_input: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = deepcopy(safe_dict(latest_result))
    final_plan = safe_dict(result.get("final_plan"))
    if not final_plan:
        return result
    meta = safe_dict(final_plan.get("meta"))
    meta["source_confidence_map_v1"] = build_source_confidence_map(meta, project_input=project_input)
    final_plan["meta"] = meta
    result["final_plan"] = final_plan
    return result


__all__ = [
    "SOURCE_CONFIDENCE_MAP_VERSION",
    "attach_source_confidence_map",
    "build_source_confidence_map",
]
