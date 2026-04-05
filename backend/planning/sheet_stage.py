from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.config import DEFAULT_PAD_ELEV

from .common import dedupe_keep_order, polyline_length, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import unwrap_fields_for_execution
from .runtime import PlannerExecutionContext


def _sample_along_line(start: Sequence[float], end: Sequence[float], count: int) -> List[List[float]]:
    if count <= 1:
        return [[safe_float(start[0], 0.0), safe_float(start[1], 0.0)]]
    sx, sy = safe_float(start[0], 0.0), safe_float(start[1], 0.0)
    ex, ey = safe_float(end[0], 0.0), safe_float(end[1], 0.0)
    return [[sx + (ex - sx) * (idx / max(count - 1, 1)), sy + (ey - sy) * (idx / max(count - 1, 1))] for idx in range(count)]


def _polyline_station_samples(path: Sequence[Sequence[float]], count: int) -> List[Dict[str, Any]]:
    points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in path if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if len(points) < 2:
        return []
    lengths = [0.0]
    for idx in range(1, len(points)):
        lengths.append(lengths[-1] + polyline_length([points[idx - 1], points[idx]]))
    total = lengths[-1]
    if total <= 0.0:
        return [{"station_ft": 0.0, "point": points[0]}]
    out: List[Dict[str, Any]] = []
    for sample_idx in range(max(2, count)):
        target = total * (sample_idx / max(max(2, count) - 1, 1))
        for idx in range(1, len(points)):
            if lengths[idx] + 1e-9 < target:
                continue
            segment_length = max(lengths[idx] - lengths[idx - 1], 1e-9)
            ratio = (target - lengths[idx - 1]) / segment_length
            x0, y0 = points[idx - 1]
            x1, y1 = points[idx]
            out.append(
                {
                    "station_ft": round(target, 3),
                    "point": [round(x0 + (x1 - x0) * ratio, 3), round(y0 + (y1 - y0) * ratio, 3)],
                    "segment_index": idx - 1,
                }
            )
            break
    return out


def _perpendicular_cut_line(path: Sequence[Sequence[float]], station_point: Sequence[float], station_segment_index: int, half_width_ft: float) -> List[List[float]]:
    points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in path if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if len(points) < 2:
        x = safe_float(station_point[0], 0.0)
        y = safe_float(station_point[1], 0.0)
        return [[x - half_width_ft, y], [x + half_width_ft, y]]
    idx = max(0, min(len(points) - 2, safe_int(station_segment_index, 0)))
    x0, y0 = points[idx]
    x1, y1 = points[idx + 1]
    dx = x1 - x0
    dy = y1 - y0
    mag = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    nx = -dy / mag
    ny = dx / mag
    px = safe_float(station_point[0], 0.0)
    py = safe_float(station_point[1], 0.0)
    return [
        [round(px - nx * half_width_ft, 3), round(py - ny * half_width_ft, 3)],
        [round(px + nx * half_width_ft, 3), round(py + ny * half_width_ft, 3)],
    ]


def run_sheet_stage(
    ctx: PlannerExecutionContext,
    *,
    requested_profile_or_sections: Callable[[Dict[str, Any]], Tuple[bool, bool]],
    build_existing_surface: Callable[[Dict[str, Any]], Any],
    expanded_obstacle_rectangles: Callable[[Any], List[Dict[str, Any]]],
    path_hits_buffered_rect: Callable[[Sequence[Sequence[float]], Dict[str, Any]], bool],
    grading_local_adjustments: Callable[[Any], List[Dict[str, Any]]],
    station_text: Callable[[float], str],
    sample_grid_surface: Callable[[Any, float, float, float], float],
    preferred_corridor_for_segment: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
    sheet_alignment: Callable[[Any, Dict[str, Any]], Tuple[List[List[float]], bool, str]],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    wants_profile, wants_sections = requested_profile_or_sections(parsed)
    if not wants_profile and not wants_sections:
        manager.mark_system_skipped("sheets", "Sheet stage skipped because no profile or cross-section deliverables were requested.")
        ctx.add_stage("sheets", True, "Sheet stage skipped because no profile or cross-section deliverables were requested.")
        return

    try:
        manager.mark_system_running("sheets", "Generating profile and cross-section deliverables.")
        grading = safe_dict(manager.latest_outputs.get("grading", project.meta.get("grading_summary", {})))
        existing_surface = grading.get("existing_surface") or build_existing_surface(unwrap_fields_for_execution(parsed))
        proposed_surface = grading.get("proposed_surface") or existing_surface

        alignments: List[Dict[str, Any]] = []
        protected_zones = expanded_obstacle_rectangles(project)
        drainage_meta = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_summary", {})))
        storm_meta = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
        sanitary_meta = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
        structure_lookup: Dict[str, Dict[str, Any]] = {}
        for structure in safe_list(drainage_meta.get("structures")):
            rec = safe_dict(structure)
            name = safe_str(rec.get("name"))
            if not name:
                continue
            structure_lookup[name] = {
                "name": name,
                "x": safe_float(rec.get("x"), 0.0),
                "y": safe_float(rec.get("y"), 0.0),
                "rim_elev_ft": safe_float(rec.get("z"), 0.0),
                "kind": safe_str(rec.get("structure_type") or rec.get("canonical_type") or rec.get("object_type"), "structure"),
            }
        for manhole in safe_list(sanitary_meta.get("manholes")):
            rec = safe_dict(manhole)
            name = safe_str(rec.get("name"))
            if not name:
                continue
            structure_lookup[name] = {
                "name": name,
                "x": safe_float(rec.get("x"), 0.0),
                "y": safe_float(rec.get("y"), 0.0),
                "rim_elev_ft": safe_float(rec.get("rim_elev_ft"), 0.0),
                "kind": "sanitary_manhole",
            }

        def alignment_protected_context(points: Sequence[Sequence[float]]) -> Dict[str, Any]:
            path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            touched = []
            for zone in protected_zones:
                if path_hits_buffered_rect(path, zone):
                    touched.append(
                        {
                            "kind": safe_str(zone.get("kind")),
                            "name": safe_str(zone.get("name")),
                            "penalty": safe_float(zone.get("penalty"), 0.0),
                        }
                    )
            return {
                "zone_count": len(touched),
                "zone_kinds": dedupe_keep_order(safe_str(item.get("kind")) for item in touched if safe_str(item.get("kind"))),
                "zones": touched,
            }

        def alignment_grading_context(points: Sequence[Sequence[float]], alignment_type: str) -> Dict[str, Any]:
            path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            adjustments = []
            for item in grading_local_adjustments(project):
                rec = safe_dict(item)
                location = safe_list(rec.get("location"))
                if len(location) < 2:
                    continue
                nearest = min((((safe_float(pt[0], 0.0) - safe_float(location[0], 0.0)) ** 2 + (safe_float(pt[1], 0.0) - safe_float(location[1], 0.0)) ** 2) ** 0.5 for pt in path), default=1e9)
                if nearest <= 20.0:
                    adjustments.append(
                        {
                            "target": safe_str(rec.get("target")),
                            "repair_modes": deepcopy(safe_list(rec.get("repair_modes"))),
                            "distance_ft": round(nearest, 3),
                        }
                    )
            return {
                "alignment_type": alignment_type,
                "local_adjustment_count": len(adjustments),
                "local_adjustments": adjustments[:6],
                "surface_source": "proposed_surface" if proposed_surface is not None else "existing_surface",
            }

        def section_feature_runs(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
            runs: List[Dict[str, Any]] = []
            current: Optional[Dict[str, Any]] = None
            for row in rows:
                rec = safe_dict(row)
                feature_type = safe_str(rec.get("feature_type"), "section_edge")
                offset_ft = safe_float(rec.get("offset_ft"), 0.0)
                if current is None or safe_str(current.get("feature_type")) != feature_type:
                    if current is not None:
                        current["width_ft"] = round(abs(safe_float(current.get("end_offset_ft"), 0.0) - safe_float(current.get("start_offset_ft"), 0.0)), 3)
                        runs.append(current)
                    current = {
                        "feature_type": feature_type,
                        "start_offset_ft": offset_ft,
                        "end_offset_ft": offset_ft,
                        "min_fg_ft": safe_float(rec.get("proposed_elev_ft"), 0.0),
                        "max_fg_ft": safe_float(rec.get("proposed_elev_ft"), 0.0),
                    }
                else:
                    current["end_offset_ft"] = offset_ft
                    current["min_fg_ft"] = min(safe_float(current.get("min_fg_ft"), 0.0), safe_float(rec.get("proposed_elev_ft"), 0.0))
                    current["max_fg_ft"] = max(safe_float(current.get("max_fg_ft"), 0.0), safe_float(rec.get("proposed_elev_ft"), 0.0))
            if current is not None:
                current["width_ft"] = round(abs(safe_float(current.get("end_offset_ft"), 0.0) - safe_float(current.get("start_offset_ft"), 0.0)), 3)
                runs.append(current)
            return runs

        def section_modeled_widths(runs: Sequence[Dict[str, Any]]) -> Dict[str, float]:
            lane = sum(safe_float(item.get("width_ft"), 0.0) for item in runs if safe_str(item.get("feature_type")) == "travel_lane")
            curb = sum(safe_float(item.get("width_ft"), 0.0) for item in runs if safe_str(item.get("feature_type")) == "curb_gutter")
            walk = sum(safe_float(item.get("width_ft"), 0.0) for item in runs if safe_str(item.get("feature_type")) == "sidewalk")
            pipe_zone = sum(safe_float(item.get("width_ft"), 0.0) for item in runs if safe_str(item.get("feature_type")) == "pipe_centerline")
            improved = lane + curb + walk
            return {
                "lane_width_ft": round(lane, 3),
                "curb_gutter_width_ft": round(curb, 3),
                "sidewalk_total_width_ft": round(walk, 3),
                "pipe_zone_width_ft": round(pipe_zone, 3),
                "improved_width_ft": round(improved, 3),
            }

        def section_edge_conditions(cut_line: Sequence[Sequence[float]]) -> Dict[str, Any]:
            conditions = []
            for zone in protected_zones:
                if path_hits_buffered_rect(cut_line, zone):
                    conditions.append(
                        {
                            "kind": safe_str(zone.get("kind")),
                            "name": safe_str(zone.get("name")),
                            "penalty": safe_float(zone.get("penalty"), 0.0),
                        }
                    )
            return {
                "count": len(conditions),
                "kinds": dedupe_keep_order(safe_str(item.get("kind")) for item in conditions if safe_str(item.get("kind"))),
                "zones": conditions[:6],
            }

        alignment_points, horizontal, alignment_source = sheet_alignment(project, parsed)
        road_samples = _polyline_station_samples(alignment_points, 5)
        road_stations: List[Dict[str, Any]] = []
        for sample in road_samples:
            point = safe_list(sample.get("point"))
            if len(point) < 2:
                continue
            road_stations.append(
                {
                    "station_ft": safe_float(sample.get("station_ft"), 0.0),
                    "station_text": station_text(safe_float(sample.get("station_ft"), 0.0)),
                    "point": [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)],
                    "segment_index": safe_int(sample.get("segment_index"), 0),
                    "existing_elev_ft": round(sample_grid_surface(existing_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                    "proposed_elev_ft": round(sample_grid_surface(proposed_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                }
            )
        alignments.append(
            {
                "name": "ROAD ALIGNMENT 1",
                "alignment_type": "roadway",
                "points": [[round(pt[0], 3), round(pt[1], 3)] for pt in alignment_points],
                "source": alignment_source,
                "source_system": "roadway",
                "alignment_owner": "road_centerline",
                "ownership_class": "roadway_primary",
                "preferred_corridor": {},
                "horizontal": horizontal,
                "total_length_ft": round(polyline_length(alignment_points), 3),
                "stations": deepcopy(road_stations),
                "protected_zone_context": alignment_protected_context(alignment_points),
                "grading_context": alignment_grading_context(alignment_points, "roadway"),
            }
        )

        storm_segments = safe_list(storm_meta.get("segments"))
        if storm_segments:
            longest_storm = max(storm_segments, key=lambda seg: safe_float(safe_dict(seg).get("length_ft"), 0.0))
            storm_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(safe_dict(longest_storm).get("path") or safe_dict(longest_storm).get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            if len(storm_path) >= 2:
                storm_samples = _polyline_station_samples(storm_path, 5)
                storm_stations: List[Dict[str, Any]] = []
                start_invert = safe_float(safe_dict(longest_storm).get("start_invert"), DEFAULT_PAD_ELEV - 4.0)
                end_invert = safe_float(safe_dict(longest_storm).get("end_invert"), start_invert - 1.0)
                total_length = max(polyline_length(storm_path), 1e-9)
                for sample in storm_samples:
                    point = safe_list(sample.get("point"))
                    station_ft = safe_float(sample.get("station_ft"), 0.0)
                    ratio = station_ft / total_length
                    storm_stations.append(
                        {
                            "station_ft": station_ft,
                            "station_text": station_text(station_ft),
                            "point": [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)],
                            "segment_index": safe_int(sample.get("segment_index"), 0),
                            "existing_elev_ft": round(sample_grid_surface(existing_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                            "proposed_elev_ft": round(sample_grid_surface(proposed_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                            "pipe_invert_ft": round(start_invert + (end_invert - start_invert) * ratio, 3),
                        }
                    )
                alignments.append(
                    {
                        "name": safe_str(safe_dict(longest_storm).get("pipe"), "STORM MAIN"),
                        "alignment_type": "storm_pipe",
                        "points": [[round(pt[0], 3), round(pt[1], 3)] for pt in storm_path],
                        "source": "storm_pipe",
                        "source_system": "storm",
                        "alignment_owner": safe_str(safe_dict(longest_storm).get("pipe"), "STORM MAIN"),
                        "ownership_class": "storm_main",
                        "preferred_corridor": deepcopy(safe_dict(longest_storm.get("preferred_corridor")) or preferred_corridor_for_segment(project, {"system": "storm", **safe_dict(longest_storm)})),
                        "horizontal": abs(storm_path[-1][0] - storm_path[0][0]) >= abs(storm_path[-1][1] - storm_path[0][1]),
                        "total_length_ft": round(total_length, 3),
                        "stations": storm_stations,
                        "network_segment": deepcopy(safe_dict(longest_storm)),
                        "protected_zone_context": alignment_protected_context(storm_path),
                        "grading_context": alignment_grading_context(storm_path, "storm_pipe"),
                    }
                )

        sanitary_main = None
        for segment in safe_list(sanitary_meta.get("segments")):
            rec = safe_dict(segment)
            if safe_str(rec.get("segment_role")) == "main":
                sanitary_main = rec
                break
        if sanitary_main:
            sanitary_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(sanitary_main.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            if len(sanitary_path) >= 2:
                sanitary_samples = _polyline_station_samples(sanitary_path, 5)
                sanitary_stations: List[Dict[str, Any]] = []
                start_invert = safe_float(sanitary_main.get("start_invert_ft"), DEFAULT_PAD_ELEV - 5.0)
                end_invert = safe_float(sanitary_main.get("end_invert_ft"), start_invert - 1.0)
                total_length = max(polyline_length(sanitary_path), 1e-9)
                for sample in sanitary_samples:
                    point = safe_list(sample.get("point"))
                    station_ft = safe_float(sample.get("station_ft"), 0.0)
                    ratio = station_ft / total_length
                    sanitary_stations.append(
                        {
                            "station_ft": station_ft,
                            "station_text": station_text(station_ft),
                            "point": [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)],
                            "segment_index": safe_int(sample.get("segment_index"), 0),
                            "existing_elev_ft": round(sample_grid_surface(existing_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                            "proposed_elev_ft": round(sample_grid_surface(proposed_surface, point[0], point[1], DEFAULT_PAD_ELEV), 3),
                            "pipe_invert_ft": round(start_invert + (end_invert - start_invert) * ratio, 3),
                        }
                    )
                alignments.append(
                    {
                        "name": safe_str(sanitary_main.get("name"), "SANITARY MAIN"),
                        "alignment_type": "sanitary_pipe",
                        "points": [[round(pt[0], 3), round(pt[1], 3)] for pt in sanitary_path],
                        "source": "sanitary_pipe",
                        "source_system": "sanitary",
                        "alignment_owner": safe_str(sanitary_main.get("name"), "SANITARY MAIN"),
                        "ownership_class": "sanitary_main",
                        "preferred_corridor": deepcopy(safe_dict(sanitary_main.get("preferred_corridor")) or preferred_corridor_for_segment(project, {"system": "sanitary", **safe_dict(sanitary_main)})),
                        "horizontal": abs(sanitary_path[-1][0] - sanitary_path[0][0]) >= abs(sanitary_path[-1][1] - sanitary_path[0][1]),
                        "total_length_ft": round(total_length, 3),
                        "stations": sanitary_stations,
                        "network_segment": deepcopy(safe_dict(sanitary_main)),
                        "protected_zone_context": alignment_protected_context(sanitary_path),
                        "grading_context": alignment_grading_context(sanitary_path, "sanitary_pipe"),
                    }
                )

        profiles: List[Dict[str, Any]] = []
        cross_sections: List[Dict[str, Any]] = []
        if wants_profile:
            for alignment in alignments:
                alignment_type = safe_str(alignment.get("alignment_type"), "roadway")
                profile_name = "ROAD PROFILE 1" if alignment_type == "roadway" else f"{safe_str(alignment.get('name'), alignment_type.upper())} PROFILE"
                stations = [safe_dict(item) for item in safe_list(alignment.get("stations")) if isinstance(item, dict)]
                first_station = stations[0] if stations else {}
                last_station = stations[-1] if stations else {}
                structure_marks: List[Dict[str, Any]] = []
                pipe_band_records: List[Dict[str, Any]] = []
                if alignment_type in {"storm_pipe", "sanitary_pipe"}:
                    segment = safe_dict(alignment.get("network_segment"))
                    if segment:
                        if alignment_type == "storm_pipe":
                            from_name = safe_str(segment.get("from"))
                            to_name = safe_str(segment.get("to"))
                            invert_in = safe_float(segment.get("start_invert"), 0.0)
                            invert_out = safe_float(segment.get("end_invert"), 0.0)
                            slope_pct = safe_float(segment.get("slope_pct"), 0.0)
                            cover_in = safe_float(segment.get("cover_start_ft"), 0.0)
                            cover_out = safe_float(segment.get("cover_end_ft"), 0.0)
                        else:
                            from_name = safe_str(segment.get("start_name"))
                            to_name = safe_str(segment.get("end_name"))
                            invert_in = safe_float(segment.get("start_invert_ft"), 0.0)
                            invert_out = safe_float(segment.get("end_invert_ft"), 0.0)
                            slope_pct = safe_float(segment.get("slope_pct"), 0.0) or safe_float(segment.get("slope_ft_ft"), 0.0) * 100.0
                            cover_in = safe_float(segment.get("cover_start_ft"), 0.0)
                            cover_out = safe_float(segment.get("cover_end_ft"), 0.0)
                        from_structure = deepcopy(safe_dict(structure_lookup.get(from_name)))
                        to_structure = deepcopy(safe_dict(structure_lookup.get(to_name)))
                        for station_rec, structure_rec, invert in (
                            (first_station, from_structure, invert_in),
                            (last_station, to_structure, invert_out),
                        ):
                            if structure_rec:
                                structure_marks.append(
                                    {
                                        "label": safe_str(structure_rec.get("name"), "STR"),
                                        "station_ft": safe_float(station_rec.get("station_ft"), 0.0),
                                        "station_text": safe_str(station_rec.get("station_text"), station_text(safe_float(station_rec.get("station_ft"), 0.0))),
                                        "rim_elev_ft": safe_float(structure_rec.get("rim_elev_ft"), 0.0),
                                        "invert_ft": invert,
                                        "kind": safe_str(structure_rec.get("kind"), "structure"),
                                    }
                                )
                        pipe_band_records.append(
                            {
                                "start_station_ft": safe_float(first_station.get("station_ft"), 0.0),
                                "end_station_ft": safe_float(last_station.get("station_ft"), 0.0),
                                "start_station_text": safe_str(first_station.get("station_text"), station_text(safe_float(first_station.get("station_ft"), 0.0))),
                                "end_station_text": safe_str(last_station.get("station_text"), station_text(safe_float(last_station.get("station_ft"), 0.0))),
                                "diameter_in": safe_float(segment.get("diameter_in"), 0.0),
                                "slope_pct": slope_pct,
                                "from_structure": from_name,
                                "to_structure": to_name,
                                "rim_in_ft": safe_float(from_structure.get("rim_elev_ft"), 0.0),
                                "rim_out_ft": safe_float(to_structure.get("rim_elev_ft"), 0.0),
                                "invert_in_ft": invert_in,
                                "invert_out_ft": invert_out,
                                "cover_in_ft": cover_in,
                                "cover_out_ft": cover_out,
                                "flow_cfs": safe_float(segment.get("flow_cfs"), 0.0),
                                "capacity_cfs": safe_float(segment.get("capacity_cfs"), 0.0),
                                "capacity_ratio": safe_float(segment.get("capacity_ratio"), 0.0),
                                "assumed": False,
                            }
                        )
                profiles.append(
                    {
                        "name": profile_name,
                        "alignment_name": safe_str(alignment.get("name"), profile_name),
                        "alignment_type": alignment_type,
                        "alignment_points": deepcopy(safe_list(alignment.get("points"))),
                        "stations": deepcopy(stations),
                        "orientation": "horizontal" if bool(alignment.get("horizontal")) else "vertical",
                        "source": safe_str(alignment.get("source"), "unknown"),
                        "source_system": safe_str(alignment.get("source_system"), alignment_type),
                        "alignment_owner": safe_str(alignment.get("alignment_owner"), safe_str(alignment.get("name"), profile_name)),
                        "ownership_class": safe_str(alignment.get("ownership_class"), alignment_type),
                        "preferred_corridor": deepcopy(safe_dict(alignment.get("preferred_corridor"))),
                        "protected_zone_context": deepcopy(safe_dict(alignment.get("protected_zone_context"))),
                        "grading_context": deepcopy(safe_dict(alignment.get("grading_context"))),
                        "vertical_exaggeration": 5.0 if alignment_type == "roadway" else 8.0,
                        "sheet_title": "GRADING PROFILE" if alignment_type == "roadway" else "UTILITY PROFILE",
                        "sheet_name": profile_name,
                        "station_range_ft": [
                            safe_float(first_station.get("station_ft"), 0.0),
                            safe_float(last_station.get("station_ft"), 0.0),
                        ],
                        "structure_marks": deepcopy(structure_marks),
                        "pipe_band_records": deepcopy(pipe_band_records),
                    }
                )
        if wants_sections:
            for alignment in alignments:
                alignment_type = safe_str(alignment.get("alignment_type"), "roadway")
                alignment_pts = safe_list(alignment.get("points"))
                half_width = 18.0 if alignment_type == "roadway" else 12.0
                for index, station in enumerate(safe_list(alignment.get("stations"))[1:-1], start=1):
                    point = safe_list(safe_dict(station).get("point"))
                    if len(point) < 2:
                        continue
                    cut_line = _perpendicular_cut_line(alignment_pts, point, safe_int(safe_dict(station).get("segment_index"), 0), half_width)
                    section_samples = _sample_along_line(cut_line[0], cut_line[-1], 7)
                    sample_rows = []
                    section_width = max(polyline_length(cut_line), 1e-9)
                    lane_width = 24.0 if alignment_type == "roadway" else None
                    sidewalk_width = 5.0 if alignment_type == "roadway" else None
                    curb_width = 2.0 if alignment_type == "roadway" else None
                    for sample_idx, sample_pt in enumerate(section_samples):
                        offset_ft = -section_width / 2.0 + section_width * (sample_idx / max(len(section_samples) - 1, 1))
                        existing_elev = round(sample_grid_surface(existing_surface, sample_pt[0], sample_pt[1], DEFAULT_PAD_ELEV), 3)
                        proposed_elev = round(sample_grid_surface(proposed_surface, sample_pt[0], sample_pt[1], DEFAULT_PAD_ELEV), 3)
                        feature_type = "section_edge"
                        if alignment_type == "roadway":
                            lane_half = safe_float(lane_width, 24.0) / 2.0
                            curb_limit = lane_half + safe_float(curb_width, 2.0)
                            walk_limit = curb_limit + safe_float(sidewalk_width, 5.0)
                            abs_offset = abs(offset_ft)
                            if abs_offset <= lane_half:
                                feature_type = "travel_lane"
                            elif abs_offset <= curb_limit:
                                feature_type = "curb_gutter"
                            elif abs_offset <= walk_limit:
                                feature_type = "sidewalk"
                        elif abs(offset_ft) <= 1.0:
                            feature_type = "pipe_centerline"
                        row = {
                            "point": [round(sample_pt[0], 3), round(sample_pt[1], 3)],
                            "offset_ft": round(offset_ft, 3),
                            "existing_elev_ft": existing_elev,
                            "proposed_elev_ft": proposed_elev,
                            "feature_type": feature_type,
                        }
                        if alignment_type != "roadway":
                            row["pipe_invert_ft"] = round(safe_float(station.get("pipe_invert_ft"), proposed_elev - 5.0), 3)
                        sample_rows.append(row)
                    feature_runs = section_feature_runs(sample_rows)
                    modeled_widths = section_modeled_widths(feature_runs)
                    edge_conditions = section_edge_conditions(cut_line)
                    cross_sections.append(
                        {
                            "name": f"{safe_str(alignment.get('name'), alignment_type.upper())} SECTION {index}",
                            "alignment_name": safe_str(alignment.get("name"), alignment_type.upper()),
                            "alignment_type": alignment_type,
                            "source_system": safe_str(alignment.get("source_system"), alignment_type),
                            "alignment_owner": safe_str(alignment.get("alignment_owner"), safe_str(alignment.get("name"), alignment_type.upper())),
                            "ownership_class": safe_str(alignment.get("ownership_class"), alignment_type),
                            "preferred_corridor": deepcopy(safe_dict(alignment.get("preferred_corridor"))),
                            "protected_zone_context": deepcopy(safe_dict(alignment.get("protected_zone_context"))),
                            "grading_context": deepcopy(safe_dict(alignment.get("grading_context"))),
                            "station_ft": safe_float(safe_dict(station).get("station_ft"), 0.0),
                            "station_text": safe_str(safe_dict(station).get("station_text"), station_text(safe_float(safe_dict(station).get("station_ft"), 0.0))),
                            "anchor_point": [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)],
                            "cut_line_points": [[round(pt[0], 3), round(pt[1], 3)] for pt in cut_line],
                            "width_ft": round(section_width, 3),
                            "lane_width_ft": modeled_widths.get("lane_width_ft") or lane_width,
                            "sidewalk_width_ft": modeled_widths.get("sidewalk_total_width_ft") or sidewalk_width,
                            "curb_gutter_width_ft": modeled_widths.get("curb_gutter_width_ft") or curb_width,
                            "samples": sample_rows,
                            "section_context": {
                                "sample_count": len(sample_rows),
                                "feature_types": dedupe_keep_order(safe_str(item.get("feature_type")) for item in sample_rows if safe_str(item.get("feature_type"))),
                                "cut_length_ft": round(section_width, 3),
                                "feature_runs": deepcopy(feature_runs),
                                "modeled_widths": deepcopy(modeled_widths),
                                "edge_conditions": deepcopy(edge_conditions),
                            },
                            "sheet_title": "CROSS SECTIONS" if alignment_type == "roadway" else "UTILITY CROSS SECTIONS",
                            "sheet_name": f"{safe_str(alignment.get('name'), alignment_type.upper())} SECTIONS",
                        }
                    )

        project.meta["alignments"] = deepcopy(alignments)
        project.meta["profiles"] = deepcopy(profiles)
        project.meta["cross_sections"] = deepcopy(cross_sections)
        manager.latest_outputs["alignments"] = deepcopy(alignments)
        manager.latest_outputs["profiles"] = deepcopy(profiles)
        manager.latest_outputs["cross_sections"] = deepcopy(cross_sections)
        manager.set_metric("alignment_count", len(alignments), category="sheets")
        manager.set_metric("profile_count", len(profiles), category="sheets")
        manager.set_metric("cross_section_count", len(cross_sections), category="sheets")
        manager.mark_system_complete("sheets", "Profile and cross-section generation completed.")
        ctx.add_stage(
            "sheets",
            True,
            "Profile and cross-section generation completed.",
            alignment_count=len(alignments),
            profile_count=len(profiles),
            cross_section_count=len(cross_sections),
        )
    except Exception as exc:
        manager.mark_system_failed("sheets", f"Sheet stage failed: {exc}", [safe_str(exc)])
        ctx.record_warning(f"Sheet stage failed: {exc}")
        ctx.add_stage("sheets", False, f"Sheet stage failed: {exc}")
