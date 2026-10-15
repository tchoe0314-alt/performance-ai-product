"""Saved-current drawing exports, isolated from stale calculation results.

These are preliminary editable footprints/linework, not a calculation package.
No generated result is used to repair, enrich or replace this captured geometry.
"""
from copy import deepcopy
from math import acos, atan2, ceil, cos, pi, sin, sqrt
from fastapi import HTTPException

from backend.services.canonical_canvas import resolve_canvas_input
from backend.services.canonical_results import BINDING_KEY, canvas_input_signature, canvas_live_input_signature
from backend.services.site_objects import geometry_issues
from backend.application.artifact_workflows import _site_object_layer, _rotated_rectangle_points, assert_current_export_result, finalize_export_artifact
from backend.planning.preliminary_export import prepare_preliminary_snapshot

SCOPE = "saved_current_geometry_only_no_calculations"


def _culdesac_details(item, units):
    params = (item.get("meta") or {}).get("cul_de_sac_v1")
    if not params:
        return []
    if not isinstance(params, dict) or params.get("version") != 1 or params.get("coordinateUnits") != units or params.get("islandRadiusFt") != 15 or params.get("transitionRadiusFt") != 20:
        raise HTTPException(409, "Current drawing export blocked: unsupported road parameters or units.")
    radius, width = params.get("bulbRadiusFt"), params.get("roadWidthFt")
    if type(radius) not in (float, int) or type(width) not in (float, int) or not 35 <= radius <= 80 or not 20 <= width <= 48:
        raise HTTPException(409, "Current drawing export blocked: invalid road dimensions.")
    scale = .3048 if units == "m" else 1
    a, x = width / 2, width / 2 + 20
    y = sqrt((radius + 20) ** 2 - x ** 2)
    theta, bottom = atan2(y, x), y + 110
    angle = item.get("rotation", 0) * pi / 180
    cx, cy = item["x"] + radius * scale, item["y"] + (bottom + radius) * scale / 2
    def world(point):
        dx, dy = point[0] * scale, (point[1] - (bottom - radius) / 2) * scale
        return [cx + dx * cos(angle) - dy * sin(angle), cy + dx * sin(angle) + dy * cos(angle)]
    local = [[-a, bottom], [-a, y]]
    def arc(ax, ay, r, start, sweep):
        count = ceil(abs(sweep) / (2 * acos(1 - .02 / r)))
        for n in range(1, count + 1):
            t = start + sweep * n / count
            local.append([ax + r * cos(t), ay + r * sin(t)])
    arc(-x, y, 20, 0, -theta)
    arc(0, 0, radius, pi - theta, pi + 2 * theta)
    arc(x, y, 20, -pi + theta, -theta)
    local.append([a, bottom])
    expected = list(map(world, local))
    actual = item.get("geometry") or []
    if abs(item["w"] - 2 * radius * scale) > 1e-6 or abs(item["d"] - (bottom + radius) * scale) > 1e-6 or len(actual) != len(expected) or any(abs(v - w) > 1e-6 for point, calculated in zip(actual, expected) for v, w in zip(point, calculated)):
        raise HTTPException(409, "Current drawing export blocked: parametric road geometry is out of sync.")
    parent = item["id"]
    def action(task, layer, suffix, **geometry):
        return {"task": task, "layer": layer, **geometry, "canonical_source_id": parent, "canonical_source_type": "road", "meta": {"entity_id": f"{parent}:{suffix}", "parent_object_id": parent, "preview_role": "final", "system": "layout", "review_required": True}}
    return [action("circle", "C-LANDSCAPE", "island", center=world([0, 0]), radius=15 * scale), *[action("polyline", "C-ROAD-MARKING", f"centerline-{n}", points=[world([offset, radius + 4]), world([offset, bottom])]) for n, offset in enumerate([-1 / 3, 1 / 3])]]


def prepare_current_geometry_result(project):
    inputs = resolve_canvas_input(project.get("project_input") or {})
    if canvas_input_signature(inputs) is None:
        raise HTTPException(409, "Save this project in the current workspace before exporting its drawing.")
    fields = inputs.get("manual_fields") or {}
    units = fields.get("units")
    if units not in {"ft", "m"}:
        raise HTTPException(409, "Current drawing export blocked: set valid drawing units first.")
    objects = fields.get("site_objects")
    if not isinstance(objects, list) or not objects:
        raise HTTPException(409, "Current drawing export blocked: no canonical drawing objects.")
    if len(objects) > 500 or sum(len(item.get("geometry") or []) for item in objects) > 3000:
        raise HTTPException(409, "Current drawing export exceeds the preliminary pilot size limit (500 objects / 3000 vertices).")
    physical = [item for item in objects if item.get("placed") is not False and item.get("type") != "group"]
    # Combined source traces are kept in JSON/history, not duplicated as footprints.
    combined = set()
    for item in physical:
        refs = (item.get("meta") or {}).get("combined_from_object_ids", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise HTTPException(409, "Current drawing export blocked: invalid combined-object references.")
        combined.update(refs)
    physical = [item for item in physical if item.get("id") not in combined]
    for item in physical:
        if geometry_issues(item):
            raise HTTPException(409, f"Current drawing export blocked: invalid geometry for {item.get('label') or item.get('id')}.")
    actions = []
    for item in physical:
        kind = item.get("geometry_type", item.get("geometryType", "rect"))
        action = {"layer": _site_object_layer(item), "label": item.get("label") or item.get("name") or item["id"], "canonical_source_id": item["id"], "canonical_source_type": item["type"], "meta": {"entity_id": item["id"], "preview_role": "final", "system": "layout", "review_required": True, "drawing_only_snapshot": True}}
        if kind in {"polygon", "polyline"}:
            action.update(task=kind, points=deepcopy(item["geometry"]), closed=kind == "polygon")
        elif kind == "point":
            action.update(task="point", origin=deepcopy(item["geometry"][0]))
        elif kind == "rect":
            x, y = item.get("x", 0), item.get("y", 0)
            if item.get("rotation", 0):
                action.update(task="polygon", points=_rotated_rectangle_points(x, y, item["w"], item["d"], item["rotation"]), closed=True)
            else:
                action.update(task="rectangle", origin=[x, y], width=item["w"], height=item["d"])
        else:
            raise HTTPException(409, "Current drawing export blocked: unsupported object geometry.")
        actions.append(action)
        actions.extend(_culdesac_details(item, units))
    sites = (inputs.get("meta") or {}).get("site_inputs") or {}
    if sites.get("coordinate_conversion_failed") is True:
        raise HTTPException(409, "Current drawing export blocked: coordinate conversion failed.")
    statuses = (inputs.get("meta") or {}).get("system_dirty_state") or {}
    incomplete = [key for key, status in statuses.items() if status != "fresh"]
    notes = [
        "Current saved object footprints and linework only. No previous calculation output is included.",
        "Parking fields are exported as editable footprints; individual stall/aisle detailing is not supplied by this drawing-only path.",
        "Parametric road edges use the saved 0.02 ft chord-tolerance outline; islands and paired centerlines are included.",
        "Local working coordinates only unless independently survey-verified. This export does not perform a coordinate conversion.",
        "Quantities, pricing, grading surfaces, pipe profiles and engineering validation are not included.",
        "Custom objects retain their chosen primitive; their engineering meaning is not inferred.",
    ]
    sources = ((sites.get("brief_sources_v1") or {}).get("records") or [])
    assumptions = ["Every drawn object remains a preliminary, unverified design representation."]
    assumptions += [f"Source {s['name']}: {s['verification']}; rights {s['rights']}; {'superseded' if s['superseded'] else 'current record'}; version {s['version'] or 'unknown'}; reference {s['origin']}" for s in sources]
    requirements = (sites.get("brief_requirements_v1") or {}).get("fields") or {}
    assumptions += [f"Recorded requirement {field}: {entry['value']} {entry['unit']}; not automatically checked." for field, entry in requirements.items() if entry["value"] is not None]
    plan = {"project_name": project.get("name") or "Civora drawing", "units": units, "actions": actions, "meta": {"project_id": project["project_id"], "source_canonical_revision": project.get("revision_token") or "unverified revision", "stale_outputs": incomplete, "assumptions": assumptions, "warnings": notes, "review_export_include_all_systems": True, "preview_options": {"allow_heuristics": False, "allow_synthesis": False, "allow_profile_inference": False}, "geometry_only": True, "quantities": {"success": False, "status": "not_included"}, "cost_estimate": {"success": False, "status": "not_included"}}}
    plan = prepare_preliminary_snapshot(plan, geometry_scope=SCOPE)
    return {"final_plan": plan, "metadata": {BINDING_KEY: {"version": 1, "scope": "canvas_manual_fields_and_site_inputs", "input_signature": canvas_input_signature(inputs), "live_input_key_v1": canvas_live_input_signature(inputs)}, "current_geometry_export_v1": {"version": 1, "geometry_scope": SCOPE, "object_ids": [item["id"] for item in physical], "calculation_results_included": False}}}


def export_current_geometry_artifact(*, artifact_service, project_store, user_id, project_id, result_data, export_format, filename_stem=None):
    if export_format not in {"dxf", "pdf"} or (result_data.get("metadata") or {}).get("current_geometry_export_v1", {}).get("geometry_scope") != SCOPE:
        raise HTTPException(409, "Invalid current-drawing export snapshot.")
    assert_current_export_result(project_store=project_store, user_id=user_id, project_id=project_id, result_data=result_data)
    if export_format == "dxf":
        path = artifact_service.export_dxf(user_id=user_id, final_plan=deepcopy(result_data["final_plan"]), stem=filename_stem, prefinalized=True)
    else:
        path = artifact_service.export_review_pdf(user_id=user_id, result_data=result_data, sheet_set={}, stem=filename_stem, geometry_scope=SCOPE)
    finalize_export_artifact(project_store=project_store, user_id=user_id, project_id=project_id, path=path, artifact_kind=f"drawing_{export_format}", result_data=result_data)
    return path


def queue_current_geometry_export(*, project_store, job_queue, user_id, project_id, expected_revision, export_format, acknowledged):
    from backend.services.project_revision import check_revision, ProjectRevisionConflict
    if acknowledged is not True or export_format not in {"dxf", "pdf"}:
        raise HTTPException(400, "Acknowledge the preliminary drawing-only scope before exporting.")
    project = project_store.get_project(user_id=user_id, project_id=project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    if project.get("access_role", "owner") in {"viewer", "reviewer"}:
        raise HTTPException(403, "Editing permission is required to create a new drawing export.")
    try:
        check_revision(project, expected_revision)
    except ProjectRevisionConflict as exc:
        raise HTTPException(409, "Project changed. Save and request a new drawing export.") from exc
    kind = f"export_current_geometry_{export_format}"
    job = job_queue.submit_job(user_id=user_id, job_type=kind, project_id=project_id, payload={"expected_revision": expected_revision, "filename_stem": project.get("name"), "export_scope": "review", "preliminary_acknowledged": True})
    return {"success": True, "job": job, "geometry_scope": SCOPE, "construction_release_allowed": False}


def build_current_geometry_export_runner(*, artifact_service, project_store, update_job_progress, export_format):
    def runner(job):
        from backend.services.project_revision import check_revision, ProjectRevisionConflict
        project_id, user_id = job["project_id"], job["user_id"]
        if job["payload"].get("preliminary_acknowledged") is not True:
            raise HTTPException(400, "Drawing-only scope acknowledgement is missing.")
        project = project_store.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            raise HTTPException(404, "Project not found.")
        if project.get("access_role", "owner") in {"viewer", "reviewer"}:
            raise HTTPException(403, "Drawing export permission changed.")
        try:
            check_revision(project, job["payload"]["expected_revision"])
        except ProjectRevisionConflict as exc:
            raise HTTPException(409, "Project changed after queuing. Save and export the current drawing again.") from exc
        update_job_progress(job["job_id"], stage="Checking current drawing", detail="Validating the saved geometry; calculations are excluded.", progress=30)
        result = prepare_current_geometry_result(project)
        update_job_progress(job["job_id"], stage="Exporting current drawing", detail="Creating a preliminary drawing with scope and source disclosures.", progress=60)
        path = export_current_geometry_artifact(artifact_service=artifact_service, project_store=project_store, user_id=user_id, project_id=project_id, result_data=result, export_format=export_format, filename_stem=project.get("name"))
        manifest = {
            "version": 1,
            "project_id": project_id,
            "source_canonical_revision": project["revision_token"],
            "units": result["final_plan"]["units"],
            "geometry_scope": SCOPE,
            "object_ids": deepcopy(result["metadata"]["current_geometry_export_v1"]["object_ids"]),
            "calculation_results_included": False,
            "construction_release_allowed": False,
        }
        return {"success": True, "export_manifest_v1": manifest, "artifact": {"kind": f"drawing_{export_format}", "filename": path.name, "download_path": f"/api/artifacts/{path.name}", "review_only": True, "construction_release_allowed": False, "export_scope": "review", "geometry_scope": SCOPE}, "job_progress": {"stage": "Drawing ready", "detail": "Preliminary drawing only; engineering and external CAD review required.", "progress": 100}}
    return runner
