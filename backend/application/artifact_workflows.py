from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from fastapi import HTTPException

from backend.application.design_workflows import (
    build_run_summary,
    final_plan_from_result,
)
from backend.application.protocols import ArtifactServiceProtocol
from backend.application.project_workflows import artifact_summary, save_project_workflow_update
from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)
from geometry.layout_engine import _build_expanded_plan


class ProjectStoreProtocol(Protocol):
    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def save_project(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str,
        session_id: Optional[str],
        tags: list[str],
        project_input: Dict[str, Any],
        latest_result: Dict[str, Any],
        session_state: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...


DISPLAY_LAYOUT_LAYERS = {"BUILDING", "PARKING", "PAVEMENT", "ROAD", "WALK", "FIRE", "SITE", "SETBACK", "PAD"}


def _minimal_plan_from_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    lot = parsed.get("lot") if isinstance(parsed.get("lot"), dict) else {}
    actions: list[dict[str, Any]] = []
    meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else {}
    site_id = str(meta.get("site_object_id") or "").strip() or None
    if lot and lot.get("w") and lot.get("h"):
        actions.append(
            {
                "task": "rectangle",
                "layer": "C-BOUNDARY",
                "x": float(lot.get("x") or 0),
                "y": float(lot.get("y") or 0),
                "w": float(lot.get("w") or 0),
                "h": float(lot.get("h") or 0),
                "meta": {
                    "preview_role": "final",
                    "system": "layout",
                    "entity_id": site_id,
                    "entity_type": "site",
                },
                "canonical_source_id": site_id,
                "canonical_source_type": "site",
            }
        )
    buildings = parsed.get("buildings") if isinstance(parsed.get("buildings"), list) else []
    for building in buildings:
        if not isinstance(building, dict):
            continue
        x = building.get("x")
        y = building.get("y")
        w = building.get("w") or building.get("width")
        d = building.get("d") or building.get("depth")
        if x is None or y is None or w is None or d is None:
            continue
        entity_id = str(building.get("id") or building.get("name") or "").strip() or None
        actions.append(
            {
                "task": "rectangle",
                "layer": "C-BUILDING",
                "x": float(x),
                "y": float(y),
                "w": float(w),
                "h": float(d),
                "meta": {
                    "preview_role": "final",
                    "system": "layout",
                    "entity_id": entity_id,
                    "entity_type": str(building.get("type") or "building"),
                },
                "canonical_source_id": entity_id,
                "canonical_source_type": str(building.get("type") or "building"),
            }
        )
    return {
        "project_name": parsed.get("project_name") or "Civora Project",
        "units": parsed.get("units") or "ft",
        "actions": actions,
        "meta": {"source": "project_input_minimal"},
    }


def _count_building_shapes(actions: list[dict[str, Any]]) -> int:
    return sum(
        1
        for action in actions
        if isinstance(action, dict)
        and str(action.get("layer") or "").upper() == "BUILDING"
        and str(action.get("task") or "").lower() in {"rectangle", "polygon"}
    )


def _has_legacy_frontage_scene(actions: list[dict[str, Any]]) -> bool:
    for action in actions:
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or "").upper()
        text = str(action.get("text") or "").upper()
        if "FRONTAGE" in label or "FRONTAGE ACCESS" in text or "FRONTAGE" in text:
            return True
    return False


def _rect_payload_from_action(action: dict[str, Any]) -> Optional[Dict[str, float]]:
    if not isinstance(action, dict):
        return None
    task = str(action.get("task") or "").lower()
    if task == "rectangle":
        origin = action.get("origin")
        x = action.get("x")
        y = action.get("y")
        if x is None and isinstance(origin, (list, tuple)) and len(origin) >= 2:
            x = origin[0]
        if y is None and isinstance(origin, (list, tuple)) and len(origin) >= 2:
            y = origin[1]
        w = action.get("w", action.get("width"))
        h = action.get("h", action.get("height"))
        try:
            if x is None or y is None or w is None or h is None:
                return None
            return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}
        except (TypeError, ValueError):
            return None
    if task == "polygon":
        points = action.get("points")
        if not isinstance(points, list) or not points:
            return None
        coords: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                coords.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
        if not coords:
            return None
        xs = [point[0] for point in coords]
        ys = [point[1] for point in coords]
        return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}
    return None


def _candidate_display_payloads(result_data: Dict[str, Any]) -> list[Dict[str, Any]]:
    def _normalize_request_like_payload(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict) or not raw:
            return {}
        if isinstance(raw.get("lot"), dict) or isinstance(raw.get("buildings"), list):
            return dict(raw)
        manual_fields = dict(raw.get("manual_fields") or {})
        meta = dict(raw.get("meta") or {})
        if not manual_fields and not meta:
            return {}
        normalized = dict(manual_fields)
        if not normalized.get("project_type") and meta.get("project_type"):
            normalized["project_type"] = meta.get("project_type")
        if not normalized.get("site_type") and meta.get("site_type"):
            normalized["site_type"] = meta.get("site_type")
        if not normalized.get("street_edge") and meta.get("street_edge"):
            normalized["street_edge"] = meta.get("street_edge")
        if not normalized.get("lot") and isinstance((manual_fields.get("lot") or {}), dict):
            normalized["lot"] = dict(manual_fields.get("lot") or {})
        return normalized

    candidates: list[Dict[str, Any]] = []
    for raw in (
        result_data.get("parsed_payload"),
        dict(result_data.get("request_metadata") or {}).get("parsed_payload"),
        dict(result_data.get("metadata") or {}).get("parsed_payload"),
        result_data.get("project_input"),
        dict(result_data.get("request_metadata") or {}).get("project_input"),
        dict(result_data.get("metadata") or {}).get("project_input"),
        result_data.get("request_payload"),
        dict(result_data.get("request_metadata") or {}).get("request_payload"),
        dict(result_data.get("metadata") or {}).get("request_payload"),
    ):
        normalized = _normalize_request_like_payload(raw)
        if normalized:
            candidates.append(normalized)
    return candidates


def _payload_from_input_summary(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    buildings = [item for item in list(raw.get("buildings") or []) if isinstance(item, dict)]
    lot = dict(raw.get("lot") or {})
    if not buildings and not lot:
        return {}
    normalized: Dict[str, Any] = {}
    if lot:
        normalized["lot"] = lot
    if raw.get("project_type"):
        normalized["project_type"] = raw.get("project_type")
    if raw.get("site_type"):
        normalized["site_type"] = raw.get("site_type")
    if raw.get("street_edge"):
        normalized["street_edge"] = raw.get("street_edge")
    if buildings:
        normalized["buildings"] = [
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "width": item.get("width"),
                "depth": item.get("depth"),
            }
            for item in buildings
        ]
    return normalized


def _payload_from_saved_actions(
    actions: list[dict[str, Any]],
    *,
    project_type: Optional[str] = None,
    site_type: Optional[str] = None,
    street_edge: Optional[str] = None,
) -> Dict[str, Any]:
    buildings: list[Dict[str, Any]] = []
    parking_areas: list[Dict[str, float]] = []
    lot_candidate: Optional[Dict[str, float]] = None

    for action in actions:
        if not isinstance(action, dict):
            continue
        layer = str(action.get("layer") or "").upper()
        rect = _rect_payload_from_action(action)
        if rect is None:
            continue
        if layer == "SITE":
            if lot_candidate is None or (rect["w"] * rect["h"]) > (lot_candidate["w"] * lot_candidate["h"]):
                lot_candidate = rect
            continue
        if layer == "BUILDING":
            if rect["w"] <= 0 or rect["h"] <= 0:
                continue
            label = str(action.get("label") or "").strip() or f"BLDG-{len(buildings) + 1}"
            buildings.append(
                {
                    "name": label,
                    "type": "building",
                    "x": rect["x"],
                    "y": rect["y"],
                    "width": rect["w"],
                    "depth": rect["h"],
                }
            )
            continue
        if layer == "PARKING":
            if rect["w"] < 12 or rect["h"] < 12:
                continue
            parking_areas.append(rect)

    if len(buildings) < 2:
        return {}

    payload: Dict[str, Any] = {"buildings": buildings}
    if lot_candidate:
        payload["lot"] = {"w": lot_candidate["w"], "h": lot_candidate["h"]}
    if parking_areas:
        payload["parking_areas"] = parking_areas
    if project_type:
        payload["project_type"] = project_type
    if site_type:
        payload["site_type"] = site_type
    if street_edge:
        payload["street_edge"] = street_edge
    return payload


def _enrich_result_data_from_project(
    result_data: Dict[str, Any],
    *,
    project_store: Optional[ProjectStoreProtocol],
    user_id: Optional[str],
    project_id: Optional[str],
) -> Dict[str, Any]:
    if project_store is None or not user_id or not project_id:
        return dict(result_data or {})
    project = project_store.get_project(user_id=user_id, project_id=project_id)
    if not isinstance(project, dict):
        return dict(result_data or {})

    enriched = dict(result_data or {})
    current_best = _best_display_payload(enriched)
    current_building_count = _payload_building_count(current_best)
    current_actions = [
        action
        for action in list(dict(enriched.get("final_plan") or {}).get("actions") or [])
        if isinstance(action, dict)
    ]
    legacy_display = _should_rebuild_display_plan(current_actions, current_building_count)

    project_input = project.get("project_input")
    project_latest_result = dict(project.get("latest_result") or {})
    project_best = _best_display_payload(project_latest_result)
    project_best_count = _payload_building_count(project_best)
    workflow_runs = [
        item
        for item in list(dict(project.get("metadata") or {}).get("workflow", {}).get("runs") or [])
        if isinstance(item, dict)
    ]
    workflow_input_payload = _payload_from_input_summary(
        dict(workflow_runs[0]).get("input_summary") if workflow_runs else {}
    )
    project_input_meta = dict(dict(project_input or {}).get("meta") or {})
    project_best_meta = dict(project_best or {})
    workflow_input_meta = dict(workflow_input_payload or {})
    sparse_saved_actions_payload = _payload_from_saved_actions(
        current_actions,
        project_type=(
            project_input_meta.get("project_type")
            or project_best_meta.get("project_type")
            or workflow_input_meta.get("project_type")
        ),
        site_type=(
            project_input_meta.get("site_type")
            or project_best_meta.get("site_type")
            or workflow_input_meta.get("site_type")
        ),
        street_edge=(
            project_input_meta.get("street_edge")
            or project_best_meta.get("street_edge")
            or workflow_input_meta.get("street_edge")
        ),
    )
    request_payload = (
        dict(project_latest_result.get("request_metadata") or {}).get("request_payload")
        or dict(project_latest_result.get("metadata") or {}).get("request_payload")
        or project.get("request_payload")
    )

    if project_input and (current_building_count < 2 or legacy_display):
        enriched["project_input"] = project_input
        request_metadata = dict(enriched.get("request_metadata") or {})
        request_metadata["project_input"] = project_input
        enriched["request_metadata"] = request_metadata

    if request_payload and (current_building_count < 2 or legacy_display):
        enriched["request_payload"] = request_payload
        request_metadata = dict(enriched.get("request_metadata") or {})
        request_metadata["request_payload"] = request_payload
        enriched["request_metadata"] = request_metadata

    if workflow_input_payload and (
        current_building_count < 2
        or (legacy_display and _payload_display_richness(workflow_input_payload) > _payload_display_richness(current_best))
    ):
        request_metadata = dict(enriched.get("request_metadata") or {})
        request_metadata["workflow_input_summary"] = workflow_input_payload
        enriched["request_metadata"] = request_metadata

    if sparse_saved_actions_payload and (
        current_building_count < 2
        or (legacy_display and _payload_display_richness(sparse_saved_actions_payload) > _payload_display_richness(current_best))
    ):
        request_metadata = dict(enriched.get("request_metadata") or {})
        request_metadata["sparse_saved_actions"] = sparse_saved_actions_payload
        enriched["request_metadata"] = request_metadata

    if project_best and (
        project_best_count > current_building_count
        or (legacy_display and _payload_display_richness(project_best) > _payload_display_richness(current_best))
    ):
        if project_best:
            enriched["parsed_payload"] = project_best
            request_metadata = dict(enriched.get("request_metadata") or {})
            request_metadata["parsed_payload"] = project_best
            enriched["request_metadata"] = request_metadata

    return enriched


def _payload_building_count(payload: Dict[str, Any]) -> int:
    raw_buildings = payload.get("buildings")
    if not isinstance(raw_buildings, list):
        return 0
    return len([item for item in raw_buildings if isinstance(item, dict)])


def _payload_display_richness(payload: Dict[str, Any]) -> int:
    score = _payload_building_count(payload) * 100
    if isinstance(payload.get("lot"), dict) and payload.get("lot"):
        score += 20
    for key in (
        "parking_areas",
        "drive_aisles",
        "roads_network",
        "sidewalks",
        "fire_lanes",
        "drainage_structures",
        "pipe_network",
        "ponds",
        "utility_network",
    ):
        value = payload.get(key)
        if isinstance(value, list) and value:
            score += 12
    if isinstance(payload.get("grading"), dict) and payload.get("grading"):
        score += 8
    if payload.get("project_type"):
        score += 4
    if payload.get("site_type"):
        score += 4
    if payload.get("street_edge"):
        score += 2
    return score


def _best_display_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    candidates = _candidate_display_payloads(result_data)
    workflow_input = _payload_from_input_summary(
        dict(result_data.get("request_metadata") or {}).get("workflow_input_summary")
    )
    if workflow_input:
        candidates.append(workflow_input)
    sparse_saved_actions = dict(result_data.get("request_metadata") or {}).get("sparse_saved_actions")
    if isinstance(sparse_saved_actions, dict) and sparse_saved_actions:
        candidates.append(sparse_saved_actions)
    if not candidates:
        return {}
    best = max(
        candidates,
        key=lambda payload: (
            _payload_display_richness(payload),
            len(payload),
        ),
    )
    merged = dict(best)
    for candidate in candidates:
        if _payload_building_count(candidate) > _payload_building_count(merged):
            merged["buildings"] = list(candidate.get("buildings") or [])
        if not isinstance(merged.get("lot"), dict) and isinstance(candidate.get("lot"), dict):
            merged["lot"] = dict(candidate.get("lot") or {})
        if not merged.get("project_type") and candidate.get("project_type"):
            merged["project_type"] = candidate.get("project_type")
        if not merged.get("site_type") and candidate.get("site_type"):
            merged["site_type"] = candidate.get("site_type")
        if not merged.get("street_edge") and candidate.get("street_edge"):
            merged["street_edge"] = candidate.get("street_edge")
    return merged


def _layout_action_count(actions: list[dict[str, Any]]) -> int:
    return sum(
        1
        for action in actions
        if isinstance(action, dict)
        and str(action.get("layer") or "").upper() in DISPLAY_LAYOUT_LAYERS
    )


def _should_rebuild_display_plan(actions: list[dict[str, Any]], parsed_building_count: int) -> bool:
    building_count = _count_building_shapes(actions)
    if parsed_building_count >= 2 and building_count < parsed_building_count:
        return True
    if parsed_building_count >= 2 and _has_legacy_frontage_scene(actions):
        return True
    if parsed_building_count >= 2 and _layout_action_count(actions) <= max(4, parsed_building_count + 1):
        return True
    return False


def _display_plan_from_result(result_data: Dict[str, Any], *, enforce_export_guards: bool = False) -> Dict[str, Any]:
    final_plan = final_plan_from_result(result_data, enforce_export_guards=enforce_export_guards)
    parsed_payload = _best_display_payload(result_data)
    raw_buildings = parsed_payload.get("buildings")
    parsed_buildings = [item for item in raw_buildings if isinstance(item, dict)] if isinstance(raw_buildings, list) else []
    actions = [action for action in list(final_plan.get("actions") or []) if isinstance(action, dict)]
    if not actions and parsed_payload:
        minimal = _minimal_plan_from_payload(parsed_payload)
        if minimal.get("actions"):
            return minimal
    if len(parsed_buildings) < 2:
        return final_plan

    if not _should_rebuild_display_plan(actions, len(parsed_buildings)):
        return final_plan

    rebuilt = _build_expanded_plan(parsed_payload)
    rebuilt_actions = [action for action in list(rebuilt.get("actions") or []) if isinstance(action, dict)]
    rebuilt_building_count = _count_building_shapes(rebuilt_actions)
    if rebuilt_building_count < len(parsed_buildings):
        return final_plan

    preserved_actions = [
        dict(action)
        for action in actions
        if str(action.get("layer") or "").upper() not in DISPLAY_LAYOUT_LAYERS
    ]
    display_plan = dict(final_plan)
    display_plan["actions"] = [dict(action) for action in rebuilt_actions] + preserved_actions
    display_meta = dict(display_plan.get("meta") or {})
    display_meta["display_rebuilt_from_parsed_payload"] = True
    display_plan["meta"] = display_meta
    return display_plan


def _preview_review_summary(result_data: Dict[str, Any], final_plan: Dict[str, Any]) -> Dict[str, Any]:
    def _clean_review_categories(values: list[str], *, release_ready: bool) -> list[str]:
        cleaned: list[str] = []
        for item in values:
            name = str(item or "").strip()
            if not name or name in cleaned:
                continue
            cleaned.append(name)
        if release_ready:
            return []
        if len(cleaned) > 1:
            cleaned = [item for item in cleaned if item.lower() != "general"]
        return cleaned

    def _current_export_guard_state() -> tuple[list[str], list[str]]:
        meta = dict(final_plan.get("meta") or {})
        has_discipline_meta = any(
            bool(meta.get(key))
            for key in ("grading", "drainage", "storm_pipes", "utilities")
        )
        if not has_discipline_meta:
            return [], []
        try:
            final_plan_from_result(result_data, enforce_export_guards=True)
            return [], []
        except HTTPException as exc:
            detail = str(exc.detail or "")
            lowered = detail.lower()
            blocked_exports: list[str] = []
            if "grading design" in lowered:
                blocked_exports = ["grading"]
            elif "utility design" in lowered:
                blocked_exports = ["utilities"]
            elif "drainage/storm state" in lowered:
                blocked_exports = ["drainage", "storm"]
            reasons_text = detail.split(": ", 1)[1] if ": " in detail else ""
            blocked_reasons = [part.strip() for part in reasons_text.split(",") if part.strip()]
            return blocked_exports, blocked_reasons

    def _normalize_phase_checkpoints(
        phase_checkpoints: Dict[str, Any],
        *,
        release_status: str,
        release_ready: bool,
        blocked_exports: list[str],
        blocked_reasons: list[str],
        failed_deliverables: list[str],
        manual_failures: list[Dict[str, Any]],
        stage_statuses: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = {
            str(name): dict(value)
            for name, value in dict(phase_checkpoints or {}).items()
            if isinstance(value, dict)
        }
        if not normalized:
            return {}

        stage_to_phase = {
            "layout": "layout",
            "grading": "grading",
            "drainage": "drainage_storm",
            "storm_pipes": "drainage_storm",
            "sanitary": "utilities",
            "utility_network": "utilities",
            "coordination_resolution": "coordination_validation",
            "qa": "coordination_validation",
        }
        phase_to_stages = {
            "layout": ("layout",),
            "grading": ("grading",),
            "drainage_storm": ("drainage", "storm_pipes"),
            "utilities": ("sanitary", "utility_network"),
            "coordination_validation": ("coordination_resolution", "qa"),
        }
        phase_order = [
            "layout",
            "grading",
            "drainage_storm",
            "utilities",
            "coordination_validation",
        ]

        compact_stage_statuses = {
            str(name): str(status or "").strip().lower()
            for name, status in dict(stage_statuses or {}).items()
            if str(name).strip()
        }

        def _normalized_stage_state(stage_key: str) -> str:
            raw = compact_stage_statuses.get(stage_key, "")
            if raw == "complete":
                return "complete"
            if raw == "assumed":
                return "partial"
            if raw in {"running", "in_progress", "started"}:
                return "running"
            if raw == "failed":
                return "failed"
            return "pending"

        if compact_stage_statuses:
            running_stage = next((name for name, state in compact_stage_statuses.items() if state == "running"), "")
            for phase_name in phase_order:
                phase_entry = dict(normalized.get(phase_name) or {})
                phase_states = [_normalized_stage_state(stage_key) for stage_key in phase_to_stages.get(phase_name, ())]
                non_pending_states = [state for state in phase_states if state != "pending"]
                if not non_pending_states:
                    phase_status = "pending"
                elif any(state == "failed" for state in non_pending_states):
                    phase_status = "failed"
                elif all(state == "complete" for state in non_pending_states):
                    phase_status = "complete"
                elif any(state == "running" for state in non_pending_states):
                    phase_status = "running"
                else:
                    phase_status = "partial"
                phase_entry["status"] = phase_status
                phase_entry["ready"] = phase_status == "complete"
                if phase_name == stage_to_phase.get(running_stage, "") and running_stage:
                    phase_entry["current_stage"] = running_stage
                normalized[phase_name] = phase_entry

            completed_phase_count = sum(
                1 for phase_name in phase_order if bool(dict(normalized.get(phase_name) or {}).get("ready"))
            )
            combined = dict(normalized.get("combined_view") or {})
            total_phase_count = max(1, int(combined.get("total_phase_count") or 0), len(phase_order))
            if any(state == "failed" for state in compact_stage_statuses.values()):
                combined_status = "blocked"
            elif completed_phase_count >= len(phase_order):
                combined_status = "ready"
            elif any(state == "running" for state in compact_stage_statuses.values()):
                combined_status = "running"
            elif completed_phase_count > 0:
                combined_status = "partial"
            else:
                combined_status = "pending"
            combined["label"] = str(combined.get("label") or "Combined View")
            combined["status"] = combined_status
            combined["ready"] = combined_status == "ready"
            combined["completed_phase_count"] = completed_phase_count
            combined["total_phase_count"] = total_phase_count
            normalized["combined_view"] = combined

        if blocked_exports or blocked_reasons or failed_deliverables or manual_failures:
            combined = dict(normalized.get("combined_view") or {})
            blockers = list(
                dict.fromkeys(
                    list(blocked_reasons or [])
                    + list(blocked_exports or [])
                    + [
                        f"failed_deliverable_{str(item).strip().lower().replace(' ', '_')}"
                        for item in failed_deliverables
                        if str(item).strip()
                    ]
                    + [
                        f"manual_validation_{str(item.get('code') or 'manual_validation_failure').strip().lower().replace(' ', '_')}"
                        for item in manual_failures
                        if isinstance(item, dict)
                    ]
                )
            )
            combined["label"] = str(combined.get("label") or "Combined View")
            combined["status"] = "blocked" if blockers or release_status == "blocked" else "review"
            combined["ready"] = False
            combined["blocked_exports"] = list(blocked_exports or [])
            combined["blocked_reasons"] = blockers
            combined["note"] = "Combined engineering view is blocked by release gates." if blockers else "Combined engineering view needs engineering review."
            normalized["combined_view"] = combined
            return normalized

        if release_status != "ready":
            return normalized

        if release_status == "ready":
            for name, phase in normalized.items():
                if name == "combined_view":
                    continue
                if str(phase.get("status") or "").lower() == "running":
                    continue
                if list(phase.get("blockers") or []) or list(phase.get("blocked_reasons") or []):
                    continue
                if bool(phase.get("has_data")) or not list(phase.get("deliverables") or []):
                    phase["status"] = "complete"
                    phase["ready"] = True
            combined = dict(normalized.get("combined_view") or {})
            inferred_total_phase_count = len([name for name in normalized.keys() if name != "combined_view"])
            total_phase_count = max(
                1,
                int(combined.get("total_phase_count") or 0),
                inferred_total_phase_count,
            )
            combined["status"] = "ready"
            combined["ready"] = True
            combined["completed_phase_count"] = total_phase_count
            combined["total_phase_count"] = total_phase_count
            combined["blocked_exports"] = []
            combined["blocked_reasons"] = []
            combined["note"] = "Combined engineering view is release-ready."
            normalized["combined_view"] = combined
        return normalized

    stored_run_summary = dict(result_data.get("run_summary") or {})
    if not stored_run_summary:
        stored_run_summary = dict(dict(result_data.get("metadata") or {}).get("run_summary") or {})
    run_summary = stored_run_summary or build_run_summary(result_data, source="preview")
    convergence = dict(run_summary.get("convergence_summary") or {})
    final_meta = dict(final_plan.get("meta") or {})
    final_release_review = dict(final_meta.get("release_review") or {})
    engineering = dict(run_summary.get("engineering_status") or {})
    reliability = dict(run_summary.get("reliability_summary") or {})
    optimization = dict(run_summary.get("optimization_summary") or {})
    assumption_summary = dict(convergence.get("assumption_summary") or {})
    fix_summary = dict(convergence.get("fix_summary") or {})
    rerun_summary = dict(convergence.get("rerun_summary") or {})
    dominant_fix_targets = [
        str(item)
        for item in list(convergence.get("dominant_issue_categories") or [])
        if str(item)
    ]
    unresolved_issue_categories = [
        str(item)
        for item in list(convergence.get("unresolved_issue_categories") or [])
        if str(item)
    ]
    blocked_exports_source = (
        final_release_review.get("blocked_exports")
        if "blocked_exports" in final_release_review
        else convergence.get("blocked_exports")
    )
    blocked_exports = [
        str(item)
        for item in list(blocked_exports_source or [])
        if str(item)
    ]
    blocked_reasons_source = (
        final_release_review.get("blocked_reasons")
        if "blocked_reasons" in final_release_review
        else convergence.get("blocked_reasons")
    )
    blocked_reasons = [
        str(item)
        for item in list(blocked_reasons_source or [])
        if str(item)
    ]
    current_blocked_exports, current_blocked_reasons = _current_export_guard_state()
    if current_blocked_exports or current_blocked_reasons or (
        bool(final_meta.get("grading") or final_meta.get("drainage") or final_meta.get("storm_pipes") or final_meta.get("utilities"))
        and not current_blocked_exports
        and not current_blocked_reasons
    ):
        blocked_exports = current_blocked_exports
        blocked_reasons = current_blocked_reasons
    for construction_blocker in construction_release_blockers_from_meta(
        final_meta,
        requires_construction_release=final_plan_requires_construction_release(final_plan),
    ):
        if construction_blocker not in blocked_reasons:
            blocked_reasons.append(construction_blocker)
    final_release_status = str(final_release_review.get("release_status") or final_meta.get("release_status") or "").lower()
    if (
        final_release_status == "blocked"
        and not blocked_reasons
        and not blocked_exports
        and "release_status_blocked" not in blocked_reasons
    ):
        blocked_reasons.append("release_status_blocked")
    if final_release_review.get("release_ready") is False and "release_review_not_ready" not in blocked_reasons:
        blocked_reasons.append("release_review_not_ready")
    if final_meta.get("release_ready") is False and "final_plan_release_blocked" not in blocked_reasons:
        blocked_reasons.append("final_plan_release_blocked")
    reactive_report = dict(final_meta.get("reactive_update_report") or {})
    if reactive_report.get("post_rerun_production_ready") is False and "reactive_post_rerun_not_ready" not in blocked_reasons:
        blocked_reasons.append("reactive_post_rerun_not_ready")
    for blocker in list(reactive_report.get("post_rerun_release_blockers") or []):
        blocker_name = str(blocker).strip()
        if blocker_name and blocker_name not in blocked_reasons:
            blocked_reasons.append(blocker_name)
    rerun_stages = dict(rerun_summary.get("stage_counts") or {})
    dominant_rerun_stages = [
        str(name)
        for name, _count in sorted(
            ((str(name), int(count or 0)) for name, count in rerun_stages.items()),
            key=lambda item: (-item[1], item[0]),
        )
        if str(name)
    ]
    dominant_rerun_reasons = [
        str(name)
        for name, _count in sorted(
            (
                (str(name), int(count or 0))
                for name, count in dict(rerun_summary.get("reason_counts") or {}).items()
            ),
            key=lambda item: (-item[1], item[0]),
        )
        if str(name)
    ]
    final_deliverables = dict(final_meta.get("deliverables") or final_plan.get("deliverables") or {})
    requested_deliverables = list(run_summary.get("requested_deliverables") or final_deliverables.get("requested") or [])
    produced_deliverables = list(run_summary.get("produced_deliverables") or final_deliverables.get("produced") or [])
    failed_deliverables = list(
        dict.fromkeys(
            [
                str(item)
                for item in list(run_summary.get("failed_deliverables") or [])
                + list(final_deliverables.get("failed") or [])
                if str(item).strip()
            ]
        )
    )
    for failed_deliverable in failed_deliverables:
        failed_blocker = f"failed_deliverable_{str(failed_deliverable).strip().lower().replace(' ', '_')}"
        if failed_blocker.strip() and failed_blocker not in blocked_reasons:
            blocked_reasons.append(failed_blocker)
    produced_set = {str(item).strip() for item in produced_deliverables if str(item).strip()}
    failed_set = {str(item).strip() for item in failed_deliverables if str(item).strip()}
    missing_deliverables = list(
        dict.fromkeys(
            [
                str(item).strip()
                for item in list(run_summary.get("missing_deliverables") or [])
                + list(final_deliverables.get("missing") or [])
                + [
                    item
                    for item in requested_deliverables
                    if str(item).strip()
                    and str(item).strip() not in produced_set
                    and str(item).strip() not in failed_set
                ]
                if str(item).strip()
            ]
        )
    )
    for missing_deliverable in missing_deliverables:
        missing_blocker = f"missing_deliverable_{str(missing_deliverable).strip().lower().replace(' ', '_')}"
        if missing_blocker.strip() and missing_blocker not in blocked_reasons:
            blocked_reasons.append(missing_blocker)
    manual_validation = dict(final_meta.get("manual_validation") or {})
    manual_failures: list[Dict[str, Any]] = []
    seen_manual_failure_keys: set[str] = set()
    for failure in list(run_summary.get("manual_failures") or []) + list(manual_validation.get("failures") or []):
        if not isinstance(failure, dict):
            continue
        failure_record = {
            "code": failure.get("code"),
            "message": failure.get("message"),
            "system": failure.get("system"),
            "rule": failure.get("rule"),
            "location": failure.get("location"),
            "reason": failure.get("reason"),
        }
        failure_key = str(
            failure_record.get("code")
            or failure_record.get("rule")
            or failure_record.get("system")
            or failure_record.get("message")
            or "manual_validation_failure"
        ).strip()
        if not failure_key:
            failure_key = "manual_validation_failure"
        if failure_key in seen_manual_failure_keys:
            continue
        seen_manual_failure_keys.add(failure_key)
        manual_failures.append(failure_record)
        blocker = f"manual_validation_{failure_key.lower().replace(' ', '_')}"
        if blocker not in blocked_reasons:
            blocked_reasons.append(blocker)
    requested_set = {str(item).strip() for item in requested_deliverables if str(item).strip()}
    missing_set = {str(item).strip() for item in missing_deliverables if str(item).strip()}
    ready_deliverables = [
        str(item).strip()
        for item in produced_deliverables
        if str(item).strip()
        and str(item).strip() not in failed_set
        and str(item).strip() not in missing_set
        and (not requested_set or str(item).strip() in requested_set)
    ]
    extra_deliverables = list(run_summary.get("extra_deliverables") or [])
    release_ready = bool(reliability.get("release_ready")) or bool(final_meta.get("release_ready"))
    if blocked_exports or blocked_reasons or failed_deliverables or missing_deliverables or manual_failures:
        release_status = "blocked"
        release_note = "Blocked until outstanding export issues are resolved."
    elif release_ready:
        release_status = "ready"
        release_note = str(final_release_review.get("release_note") or "Release-ready engineering state.")
    elif str(final_release_review.get("release_status") or "").lower() == "ready":
        release_status = "ready"
        release_note = str(final_release_review.get("release_note") or "Release-ready engineering state.")
    elif bool(convergence.get("converged")) and int(convergence.get("unresolved_conflict_count") or 0) == 0:
        release_status = "ready"
        release_note = "Release-ready engineering state."
    else:
        release_status = "review"
        release_note = "Needs engineering review before release."
    effective_release_ready = (
        release_status == "ready"
        and not blocked_exports
        and not blocked_reasons
        and not failed_deliverables
        and not missing_deliverables
        and not manual_failures
    )
    unresolved_issue_categories = _clean_review_categories(
        unresolved_issue_categories,
        release_ready=effective_release_ready,
    )
    phase_checkpoints = _normalize_phase_checkpoints(
        dict(run_summary.get("phase_checkpoints") or {}),
        release_status=release_status,
        release_ready=effective_release_ready,
        blocked_exports=blocked_exports,
        blocked_reasons=blocked_reasons,
        failed_deliverables=failed_deliverables,
        manual_failures=manual_failures,
        stage_statuses=dict(dict(final_plan.get("meta") or {}).get("stage_completeness") or {}).get("statuses"),
    )
    return {
        "trust_score": float(engineering.get("trust_score") or 0.0),
        "converged": bool(convergence.get("converged")),
        "passes_run": int(convergence.get("passes_run") or 0),
        "unresolved_conflict_count": int(convergence.get("unresolved_conflict_count") or 0),
        "assumption_count": int(assumption_summary.get("count") or 0),
        "assumption_categories": [
            str(item)
            for item in list(assumption_summary.get("categories") or [])
            if str(item)
        ],
        "assumption_examples": [
            str(item)
            for item in list(assumption_summary.get("examples") or [])
            if str(item)
        ],
        "autofix_actions": [
            str(item)
            for item in list(fix_summary.get("autofix_actions") or [])
            if str(item)
        ],
        "dominant_fix_targets": dominant_fix_targets,
        "review_categories": unresolved_issue_categories,
        "blocked_exports": blocked_exports,
        "blocked_reasons": blocked_reasons,
        "requested_deliverables": requested_deliverables,
        "produced_deliverables": produced_deliverables,
        "failed_deliverables": failed_deliverables,
        "missing_deliverables": missing_deliverables,
        "manual_failures": manual_failures,
        "ready_deliverables": ready_deliverables,
        "extra_deliverables": extra_deliverables,
        "rerun_total": int(rerun_summary.get("total_reruns") or 0),
        "rerun_stages": dominant_rerun_stages[:3],
        "rerun_reasons": dominant_rerun_reasons[:3],
        "phase_checkpoints": phase_checkpoints,
        "release_status": release_status,
        "release_ready": effective_release_ready,
        "release_note": release_note,
        "engineering_status": str((final_plan.get("meta") or {}).get("engineering_status") or ""),
        "reliability": reliability,
        "optimization": optimization,
    }


def build_preview_response(
    *,
    artifact_service: ArtifactServiceProtocol,
    result_data: Dict[str, Any],
    project_store: Optional[ProjectStoreProtocol] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    preview_quality: Optional[str] = None,
    preview_style: Optional[str] = None,
    label_density: Optional[str] = None,
    render_labels: Optional[bool] = None,
    preview_layers: Optional[list[str]] = None,
    preview_mode: Optional[str] = None,
) -> Dict[str, Any]:
    result_data = _enrich_result_data_from_project(
        result_data,
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    final_plan = _display_plan_from_result(result_data, enforce_export_guards=False)
    if project_id:
        meta = final_plan.get("meta") if isinstance(final_plan.get("meta"), dict) else {}
        meta["project_id"] = project_id
        final_plan["meta"] = meta
    try:
        png_bytes = artifact_service.build_preview_png(
            final_plan,
            render_labels=bool(render_labels),
            quality=preview_quality or "standard",
            preview_style=preview_style,
            label_density=label_density,
            include_layers=preview_layers,
            preview_mode=preview_mode,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        png_bytes = artifact_service.build_preview_png(final_plan)
    from output.preview import build_preview_annotations

    preview_annotations = build_preview_annotations(
        final_plan,
        include_layers=set(preview_layers or []) if preview_layers else None,
        preview_mode=preview_mode,
        label_density=label_density,
    )
    return {
        "success": True,
        "preview_image_data_url": f"data:image/png;base64,{b64encode(png_bytes).decode('ascii')}",
        "preview_annotations": preview_annotations,
        "summary": {
            "project_name": final_plan.get("project_name", "Generated Plan"),
            "units": final_plan.get("units", "ft"),
            "action_count": len(final_plan.get("actions") or []),
            "review": _preview_review_summary(result_data, final_plan),
        },
    }


def export_dxf_artifact(
    *,
    artifact_service: ArtifactServiceProtocol,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
    filename_stem: Optional[str] = None,
) -> Path:
    result_data = _enrich_result_data_from_project(
        result_data,
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    final_plan = _display_plan_from_result(result_data, enforce_export_guards=False)
    final_meta = dict(final_plan.get("meta") or {})
    if final_plan_requires_construction_release(final_plan):
        construction_blockers = construction_release_blockers_from_meta(
            final_meta,
            requires_construction_release=True,
        )
        if construction_blockers:
            raise HTTPException(
                status_code=409,
                detail=(
                    "DXF export is blocked because construction release evidence is incomplete: "
                    + ", ".join(construction_blockers)
                ),
            )
    from output.dxf_exporter import finalize_export_metadata

    finalize_export_metadata(final_plan)
    stem = filename_stem or str(final_plan.get("project_name") or "civora-ai-plan")
    path = artifact_service.export_dxf(
        user_id=user_id,
        final_plan=final_plan,
        stem=stem,
    )
    if project_id:
        save_project_workflow_update(
            project_store=project_store,
            user_id=user_id,
            project_id=project_id,
            artifact_summary=artifact_summary(
                path=path,
                artifact_kind="dxf",
                project_id=project_id,
                result_data=result_data,
            ),
        )
    return path


def export_report_artifact(
    *,
    artifact_service: ArtifactServiceProtocol,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
    filename_stem: Optional[str] = None,
) -> Path:
    result_data = _enrich_result_data_from_project(
        result_data,
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    final_plan = dict(result_data.get("final_plan") or {})
    stem = filename_stem or str(final_plan.get("project_name") or "civora-ai-report")
    enriched_result_data = dict(result_data)
    request_metadata = dict(enriched_result_data.get("request_metadata") or {})
    request_metadata["release_review"] = _preview_review_summary(result_data, final_plan)
    enriched_result_data["request_metadata"] = request_metadata
    path = artifact_service.export_report_json(
        user_id=user_id,
        result_data=enriched_result_data,
        stem=stem,
    )
    if project_id:
        save_project_workflow_update(
            project_store=project_store,
            user_id=user_id,
            project_id=project_id,
            artifact_summary=artifact_summary(
                path=path,
                artifact_kind="report",
                project_id=project_id,
                result_data=enriched_result_data,
            ),
        )
    return path
