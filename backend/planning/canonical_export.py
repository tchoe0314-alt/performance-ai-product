from __future__ import annotations

from typing import Any, Dict, List

from core.geometry_core import ProjectModel

from backend.planning.common import (
    lower_text,
    safe_dict,
    safe_float,
    safe_int,
    safe_list,
    safe_str,
)
from backend.planning.export_validation import (
    drainage_export_validation,
    primary_engineered_basins,
    storm_export_validation,
    utility_export_validation,
)


def canonical_action(
    action: Dict[str, Any],
    *,
    source_type: str,
    source_id: str,
    source_name: str = "",
    source_stage: str = "",
) -> Dict[str, Any]:
    out = dict(action)
    out["canonical_source_type"] = safe_str(source_type)
    out["canonical_source_id"] = safe_str(source_id)
    if source_name:
        out["canonical_source_name"] = safe_str(source_name)
    if source_stage:
        out["canonical_source_stage"] = safe_str(source_stage)
    return out


def canonical_structure_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    drainage = safe_dict(project.meta.get("drainage_canonical"))
    if not bool(drainage_export_validation(project, drainage_override=drainage).get("ready")):
        return actions
    for structure in safe_list(drainage.get("structures")):
        rec = safe_dict(structure)
        x = safe_float(rec.get("x"), 0.0)
        y = safe_float(rec.get("y"), 0.0)
        if x == 0.0 and y == 0.0 and not rec.get("name"):
            continue
        name = safe_str(rec.get("name"), "STRUCT")
        source_id = safe_str(rec.get("id"), name)
        struct_type = safe_str(
            rec.get("structure_type") or rec.get("canonical_type"), "structure"
        ).upper()
        actions.append(
            canonical_action(
                {
                    "task": "circle",
                    "origin": None,
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": name,
                    "layer": "STRUCTURE",
                    "text": None,
                    "text_height": None,
                    "center": [x, y],
                    "radius": 1.5,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="drainage_structure",
                source_id=source_id,
                source_name=name,
                source_stage="drainage",
            )
        )
        z = rec.get("z")
        flow = rec.get("estimated_flow_cfs")
        note = f"{struct_type} {name}"
        if z is not None:
            note += f" RIM {safe_float(z, 0.0):.2f}"
        if flow is not None:
            note += f" Q {safe_float(flow, 0.0):.2f} CFS"
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [x + 1.75, y + 1.75],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": note,
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="drainage_structure",
                source_id=source_id,
                source_name=name,
                source_stage="drainage",
            )
        )
    return actions


def canonical_basin_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    drainage = safe_dict(project.meta.get("drainage_canonical"))
    export_validation = drainage_export_validation(project, drainage_override=drainage)
    if not bool(export_validation.get("ready")):
        return actions
    primary_ids = set(safe_list(export_validation.get("primary_basin_ids")))
    for basin in primary_engineered_basins(drainage):
        rec = safe_dict(basin)
        source_id = safe_str(rec.get("id"), safe_str(rec.get("name"), "BASIN"))
        if primary_ids and source_id not in primary_ids:
            continue
        centroid = safe_list(rec.get("centroid_xy"))
        if len(centroid) < 2:
            continue
        x = safe_float(centroid[0], 0.0)
        y = safe_float(centroid[1], 0.0)
        name = safe_str(rec.get("name"), "BASIN")
        boundary_points = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("boundary_points"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(boundary_points) >= 3:
            actions.append(
                canonical_action(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": boundary_points,
                        "closed": True,
                        "width": None,
                        "height": None,
                        "label": name,
                        "layer": "BASIN_BOUNDARY",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=source_id,
                    source_name=name,
                    source_stage="drainage",
                )
            )
        else:
            continue
        bottom_points = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("bottom_points"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(bottom_points) >= 3:
            actions.append(
                canonical_action(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": bottom_points,
                        "closed": True,
                        "width": None,
                        "height": None,
                        "label": f"{name} BOTTOM",
                        "layer": "FG_CONTOUR",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=f"{source_id}:bottom",
                    source_name=name,
                    source_stage="drainage",
                )
            )
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [x, y - 4.0],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": f"DETENTION BASIN {name}",
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="drainage_basin",
                source_id=source_id,
                source_name=name,
                source_stage="drainage",
            )
        )
        detention = safe_dict(rec.get("detention_design"))
        if detention:
            actions.append(
                canonical_action(
                    {
                        "task": "text_note",
                        "origin": [x, y - 6.0],
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": None,
                        "layer": "ANNO",
                        "text": f"VOL {safe_float(detention.get('required_storage_cf'), 0.0):.0f} CF | BOT {safe_float(rec.get('bottom_elev_ft'), 0.0):.2f}",
                        "text_height": 0.7,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=f"{source_id}:storage",
                    source_name=name,
                    source_stage="drainage",
                )
            )
        outlet = safe_dict(rec.get("outlet_structure"))
        if outlet:
            ox = safe_float(outlet.get("x"), x)
            oy = safe_float(outlet.get("y"), y)
            outlet_name = safe_str(outlet.get("name"), f"{name}-OUTLET")
            actions.append(
                canonical_action(
                    {
                        "task": "circle",
                        "origin": None,
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": outlet_name,
                        "layer": "STRUCTURE",
                        "text": None,
                        "text_height": None,
                        "center": [ox, oy],
                        "radius": 1.25,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=f"{source_id}:outlet",
                    source_name=name,
                    source_stage="drainage",
                )
            )
            outlet_note = outlet_name
            if outlet.get("invert_ft") is not None or outlet.get("invert_out_ft") is not None:
                outlet_note += f" INV {safe_float(outlet.get('invert_out_ft', outlet.get('invert_ft')), 0.0):.2f}"
            actions.append(
                canonical_action(
                    {
                        "task": "text_note",
                        "origin": [ox + 1.75, oy + 1.75],
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": None,
                        "layer": "ANNO",
                        "text": outlet_note,
                        "text_height": 0.7,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=f"{source_id}:outlet_note",
                    source_name=name,
                    source_stage="drainage",
                )
            )
            actions.append(
                canonical_action(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": [[x, y], [ox, oy]],
                        "closed": False,
                        "width": None,
                        "height": None,
                        "label": f"{name} OUTLET",
                        "layer": "DRAIN_FLOW",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="drainage_basin",
                    source_id=f"{source_id}:flow",
                    source_name=name,
                    source_stage="drainage",
                )
            )
    return actions


def canonical_drainage_surface_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    drainage = safe_dict(project.meta.get("drainage_canonical"))
    if not bool(drainage_export_validation(project, drainage_override=drainage).get("ready")):
        return actions

    low_points = sorted(
        [safe_dict(item) for item in safe_list(drainage.get("low_points")) if safe_dict(item)],
        key=lambda item: (
            -safe_int(item.get("contributing_cells"), 0),
            safe_float(item.get("z"), 0.0),
        ),
    )
    for index, rec in enumerate(low_points[:6], start=1):
        x = safe_float(rec.get("x"), 0.0)
        y = safe_float(rec.get("y"), 0.0)
        if x == 0.0 and y == 0.0 and not rec.get("name"):
            continue
        source_id = safe_str(rec.get("id"), safe_str(rec.get("name"), f"LOW-{index}"))
        label = f"LP-{index} {safe_float(rec.get('z'), 0.0):.2f}"
        actions.append(
            canonical_action(
                {
                    "task": "point",
                    "origin": [x, y],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": label,
                    "layer": "LOW_POINTS",
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": 0.9,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="drainage_low_point",
                source_id=source_id,
                source_name=safe_str(rec.get("name"), label),
                source_stage="drainage",
            )
        )

    flow_paths = sorted(
        [safe_dict(item) for item in safe_list(drainage.get("flow_paths")) if safe_dict(item)],
        key=lambda item: -safe_float(item.get("length_ft"), 0.0),
    )
    seen_targets: set[str] = set()
    emitted = 0
    for rec in flow_paths:
        path = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("path"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(path) < 2:
            continue
        target_name = safe_str(rec.get("target_name"), "")
        target_key = target_name or safe_str(rec.get("id"), "")
        if target_key and target_key in seen_targets and emitted >= 4:
            continue
        if target_key:
            seen_targets.add(target_key)
        source_id = safe_str(rec.get("id"), f"FLOW-{emitted+1}")
        actions.append(
            canonical_action(
                {
                    "task": "polyline",
                    "origin": None,
                    "points": path,
                    "closed": False,
                    "width": None,
                    "height": None,
                    "label": target_name or source_id,
                    "layer": "DRAIN_FLOW",
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="drainage_flow_path",
                source_id=source_id,
                source_name=target_name or source_id,
                source_stage="drainage",
            )
        )
        emitted += 1
        if emitted >= 8:
            break
    return actions


def canonical_storm_pipe_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    segments = safe_list(project.meta.get("storm_pipe_segments"))
    if not segments:
        segments = safe_list(safe_dict(project.meta.get("storm_pipe_summary")).get("segments"))
    if not bool(storm_export_validation(project).get("ready")):
        return actions
    for index, segment in enumerate(segments, start=1):
        path = safe_list(getattr(segment, "path", None))
        if not path:
            path = safe_list(getattr(segment, "route_points", None))
        if not path:
            rec = safe_dict(segment)
            path = safe_list(rec.get("path") or rec.get("route_points"))
        if len(path) < 2:
            continue
        name = safe_str(getattr(segment, "name", None), "") or safe_str(
            safe_dict(segment).get("pipe"), f"PIPE-{index}"
        )
        diameter = getattr(segment, "diameter_in", None)
        if diameter is None:
            diameter = safe_dict(segment).get("diameter_in")
        slope = getattr(segment, "slope_ft_ft", None)
        if slope is None:
            slope = safe_dict(segment).get("slope_pct")
        start_invert = getattr(segment, "start_invert", None)
        if start_invert is None:
            start_invert = safe_dict(segment).get("start_invert")
        end_invert = getattr(segment, "end_invert", None)
        if end_invert is None:
            end_invert = safe_dict(segment).get("end_invert")
        source_id = safe_str(getattr(segment, "id", None), "") or safe_str(
            safe_dict(segment).get("id"), name
        )
        actions.append(
            canonical_action(
                {
                    "task": "polyline",
                    "origin": None,
                    "points": [
                        [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
                        for p in path
                        if isinstance(p, (list, tuple)) and len(p) >= 2
                    ],
                    "closed": False,
                    "width": None,
                    "height": None,
                    "label": name,
                    "layer": "PIPE",
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="storm_pipe_segment",
                source_id=source_id,
                source_name=name,
                source_stage="storm_pipes",
            )
        )
        pts = [
            [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
            for p in path
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        mid = pts[len(pts) // 2]
        text = name
        if diameter is not None:
            text += f' {safe_float(diameter, 0.0):.0f}"'
        if slope is not None:
            text += f" S={safe_float(slope, 0.0):.3f}"
        if start_invert is not None and end_invert is not None:
            text += f" INV {safe_float(start_invert, 0.0):.2f}->{safe_float(end_invert, 0.0):.2f}"
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [mid[0], mid[1]],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": text,
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="storm_pipe_segment",
                source_id=source_id,
                source_name=name,
                source_stage="storm_pipes",
            )
        )
    return actions


def canonical_sanitary_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    sanitary = safe_dict(project.meta.get("sanitary_summary"))
    for segment in safe_list(sanitary.get("segments")):
        rec = safe_dict(segment)
        route_points = safe_list(rec.get("route_points"))
        if len(route_points) < 2:
            continue
        name = safe_str(rec.get("name"), "SAN")
        source_id = safe_str(rec.get("id"), name)
        actions.append(
            canonical_action(
                {
                    "task": "polyline",
                    "origin": None,
                    "points": [
                        [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
                        for p in route_points
                        if isinstance(p, (list, tuple)) and len(p) >= 2
                    ],
                    "closed": False,
                    "width": None,
                    "height": None,
                    "label": name,
                    "layer": "SAN",
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="sanitary_segment",
                source_id=source_id,
                source_name=name,
                source_stage="sanitary",
            )
        )
        pts = [
            [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
            for p in route_points
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        mid = pts[len(pts) // 2]
        label = name
        if rec.get("diameter_in") is not None:
            label += f' {safe_float(rec.get("diameter_in"), 0.0):.0f}"'
        if rec.get("slope_ft_ft") is not None:
            label += f" S={safe_float(rec.get('slope_ft_ft'), 0.0):.4f}"
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [mid[0], mid[1]],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": label,
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="sanitary_segment",
                source_id=source_id,
                source_name=name,
                source_stage="sanitary",
            )
        )
    for manhole in safe_list(sanitary.get("manholes")):
        rec = safe_dict(manhole)
        x = safe_float(rec.get("x"), 0.0)
        y = safe_float(rec.get("y"), 0.0)
        name = safe_str(rec.get("name"), "SMH")
        source_id = safe_str(rec.get("id"), name)
        actions.append(
            canonical_action(
                {
                    "task": "circle",
                    "origin": None,
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": name,
                    "layer": "STRUCTURE",
                    "text": None,
                    "text_height": None,
                    "center": [x, y],
                    "radius": 2.0,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="sanitary_manhole",
                source_id=source_id,
                source_name=name,
                source_stage="sanitary",
            )
        )
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [x + 1.5, y + 1.5],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": name,
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="sanitary_manhole",
                source_id=source_id,
                source_name=name,
                source_stage="sanitary",
            )
        )
    return actions


def canonical_sheet_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for profile in safe_list(project.meta.get("profiles")):
        rec = safe_dict(profile)
        path = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("alignment_points"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        source_id = safe_str(
            rec.get("id"),
            safe_str(rec.get("name") or rec.get("alignment_name"), "PROFILE"),
        )
        if len(path) >= 2:
            actions.append(
                canonical_action(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": path,
                        "closed": False,
                        "width": None,
                        "height": None,
                        "label": safe_str(
                            rec.get("alignment_name") or rec.get("name"),
                            "PROFILE ALIGNMENT",
                        ),
                        "layer": "ROUTE",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="profile_alignment",
                    source_id=source_id,
                    source_name=safe_str(
                        rec.get("alignment_name") or rec.get("name")
                    ),
                    source_stage="sheets",
                )
            )
    for section in safe_list(project.meta.get("cross_sections")):
        rec = safe_dict(section)
        source_id = safe_str(rec.get("id"), safe_str(rec.get("name"), "SECTION"))
        cut_line = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("cut_line_points"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(cut_line) >= 2:
            actions.append(
                canonical_action(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": cut_line,
                        "closed": False,
                        "width": None,
                        "height": None,
                        "label": safe_str(rec.get("name"), "SECTION"),
                        "layer": "ROUTE",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="cross_section_cut",
                    source_id=source_id,
                    source_name=safe_str(rec.get("name")),
                    source_stage="sheets",
                )
            )
        origin = safe_list(rec.get("anchor_point"))
        if len(origin) >= 2:
            actions.append(
                canonical_action(
                    {
                        "task": "point",
                        "origin": [
                            safe_float(origin[0], 0.0),
                            safe_float(origin[1], 0.0),
                        ],
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": f"SEC {safe_str(rec.get('station_text'), 'SECTION')}",
                        "layer": "ROUTE",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": 0.5,
                        "start_angle": None,
                        "end_angle": None,
                    },
                    source_type="cross_section_cut",
                    source_id=source_id,
                    source_name=safe_str(rec.get("name")),
                    source_stage="sheets",
                )
            )
    return actions


def utility_layer_for_system(system_type: str) -> str:
    system = lower_text(system_type)
    if "sanitary" in system or "sewer" in system:
        return "SAN"
    if "storm" in system:
        return "STORM"
    if "water" in system:
        return "WATER"
    return "UTILITY"


def canonical_utility_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    utilities = safe_dict(project.meta.get("utility_summary"))
    if not bool(utility_export_validation(project, utilities_override=utilities).get("ready")):
        return actions
    hooks = safe_dict(utilities.get("conflict_hooks"))
    segments = safe_list(hooks.get("utility_segments"))
    system_type = safe_str(
        hooks.get("utility_system_type") or utilities.get("system_type"),
        "generic_utility",
    )
    layer = utility_layer_for_system(system_type)
    for index, segment in enumerate(segments, start=1):
        rec = safe_dict(segment)
        route_points = safe_list(rec.get("route_points"))
        if len(route_points) < 2:
            continue
        name = safe_str(rec.get("name"), f"{layer}-{index}")
        source_id = safe_str(rec.get("id"), name)
        actions.append(
            canonical_action(
                {
                    "task": "polyline",
                    "origin": None,
                    "points": [
                        [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
                        for p in route_points
                        if isinstance(p, (list, tuple)) and len(p) >= 2
                    ],
                    "closed": False,
                    "width": None,
                    "height": None,
                    "label": name,
                    "layer": layer,
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="utility_segment",
                source_id=source_id,
                source_name=name,
                source_stage="utility_network",
            )
        )
        pts = [
            [safe_float(p[0], 0.0), safe_float(p[1], 0.0)]
            for p in route_points
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        mid = pts[len(pts) // 2]
        text = name
        diameter = rec.get("diameter_in")
        if diameter is not None:
            text += f' {safe_float(diameter, 0.0):.0f}"'
        depth = rec.get("depth_end_ft")
        if depth is not None:
            text += f" D={safe_float(depth, 0.0):.1f}ft"
        slope = rec.get("slope_ft_ft")
        if slope is not None:
            text += f" S={safe_float(slope, 0.0):.4f}"
        actions.append(
            canonical_action(
                {
                    "task": "text_note",
                    "origin": [mid[0], mid[1]],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": "ANNO",
                    "text": text,
                    "text_height": 0.8,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                },
                source_type="utility_segment",
                source_id=source_id,
                source_name=name,
                source_stage="utility_network",
            )
        )
    return actions


def drawing_entity_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for entity in safe_list(getattr(project, "drawing_entities", [])):
        layer = safe_str(
            getattr(getattr(entity, "style", None), "layer", "ANNO"), "ANNO"
        ).upper()
        if hasattr(entity, "text") and hasattr(entity, "insertion"):
            insertion = getattr(entity, "insertion", None)
            actions.append(
                {
                    "task": "text_note",
                    "origin": [
                        safe_float(getattr(insertion, "x", 0.0), 0.0),
                        safe_float(getattr(insertion, "y", 0.0), 0.0),
                    ],
                    "points": None,
                    "closed": None,
                    "width": None,
                    "height": None,
                    "label": None,
                    "layer": layer,
                    "text": safe_str(getattr(entity, "text", ""), ""),
                    "text_height": max(
                        0.35, safe_float(getattr(entity, "height", 1.0), 1.0)
                    ),
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                }
            )
        elif hasattr(entity, "polyline"):
            polyline = getattr(entity, "polyline", None)
            points = [
                [
                    safe_float(getattr(pt, "x", 0.0), 0.0),
                    safe_float(getattr(pt, "y", 0.0), 0.0),
                ]
                for pt in getattr(polyline, "points", [])
            ]
            if len(points) >= 2:
                actions.append(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": points,
                        "closed": bool(getattr(polyline, "closed", False)),
                        "width": None,
                        "height": None,
                        "label": None,
                        "layer": layer,
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                    }
                )
    return actions


def canonical_export_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    actions.extend(canonical_structure_actions(project))
    actions.extend(canonical_basin_actions(project))
    actions.extend(canonical_drainage_surface_actions(project))
    actions.extend(canonical_storm_pipe_actions(project))
    actions.extend(canonical_sanitary_actions(project))
    actions.extend(canonical_sheet_actions(project))
    actions.extend(canonical_utility_actions(project))
    actions.extend(drawing_entity_actions(project))
    return actions
