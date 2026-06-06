from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str
from .export_package_report import build_export_package_report_v1


def _tag_name(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1]


def _parse_point_text(text: str) -> Optional[Tuple[float, float, float]]:
    parts = [part for part in safe_str(text).replace(",", " ").split() if part]
    if len(parts) < 2:
        return None
    try:
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2]) if len(parts) >= 3 else 0.0
    except Exception:
        return None
    return x, y, z


def _point_id(elem: ET.Element, fallback: str) -> str:
    return safe_str(elem.attrib.get("name") or elem.attrib.get("oID") or elem.attrib.get("pntRef") or elem.attrib.get("id"), fallback)


def import_landxml(path: Path) -> Dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return {"success": False, "source": str(path), "source_type": "landxml", "warnings": [safe_str(exc)]}

    point_lookup: Dict[str, Dict[str, Any]] = {}
    points: List[Dict[str, Any]] = []
    surfaces: List[Dict[str, Any]] = []
    alignments: List[Dict[str, Any]] = []
    pipe_networks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for elem in root.iter():
        if _tag_name(elem).lower() not in {"cgpoint", "p"}:
            continue
        parsed = _parse_point_text(elem.text or "")
        if parsed is None:
            continue
        pid = _point_id(elem, f"P-{len(points) + 1}")
        rec = {"id": pid, "x": parsed[0], "y": parsed[1], "z": parsed[2]}
        points.append(rec)
        point_lookup[pid] = rec

    for surface_elem in root.iter():
        if _tag_name(surface_elem).lower() != "surface":
            continue
        surface_points: List[Dict[str, Any]] = []
        breaklines: List[Dict[str, Any]] = []
        faces: List[List[str]] = []
        for child in surface_elem.iter():
            tag = _tag_name(child).lower()
            if tag in {"p", "cgpoint"}:
                parsed = _parse_point_text(child.text or "")
                if parsed is not None:
                    surface_points.append({"id": _point_id(child, f"SP-{len(surface_points) + 1}"), "x": parsed[0], "y": parsed[1], "z": parsed[2]})
            elif tag == "pntref":
                ref = safe_str(child.text)
                if ref in point_lookup:
                    surface_points.append(dict(point_lookup[ref]))
            elif tag in {"f", "face"}:
                refs = [safe_str(item) for item in safe_str(child.text).split() if safe_str(item)]
                if refs:
                    faces.append(refs)
            elif "breakline" in tag:
                breaklines.append({"name": safe_str(child.attrib.get("name"), f"breakline-{len(breaklines) + 1}"), "raw": safe_str(child.text)})
        surfaces.append(
            {
                "name": safe_str(surface_elem.attrib.get("name"), f"Surface-{len(surfaces) + 1}"),
                "point_count": len(surface_points),
                "points": surface_points,
                "face_count": len(faces),
                "faces": faces,
                "breakline_count": len(breaklines),
                "breaklines": breaklines,
                "source": str(path),
            }
        )

    for align_elem in root.iter():
        if _tag_name(align_elem).lower() != "alignment":
            continue
        alignment_points: List[List[float]] = []
        for child in align_elem.iter():
            if _tag_name(child).lower() in {"start", "end", "pnt", "p"}:
                parsed = _parse_point_text(child.text or "")
                if parsed is not None:
                    alignment_points.append([parsed[0], parsed[1], parsed[2]])
        alignments.append(
            {
                "name": safe_str(align_elem.attrib.get("name"), f"Alignment-{len(alignments) + 1}"),
                "length": safe_float(align_elem.attrib.get("length"), 0.0),
                "point_count": len(alignment_points),
                "points": alignment_points,
                "source": str(path),
            }
        )

    for pipe_network_elem in root.iter():
        if _tag_name(pipe_network_elem).lower() != "pipenetwork":
            continue
        pipe_count = 0
        struct_count = 0
        for child in pipe_network_elem.iter():
            tag = _tag_name(child).lower()
            if tag in {"pipe", "pipeflow"}:
                pipe_count += 1
            elif tag in {"struct", "structure"}:
                struct_count += 1
        pipe_networks.append(
            {
                "name": safe_str(pipe_network_elem.attrib.get("name"), f"PipeNetwork-{len(pipe_networks) + 1}"),
                "pipe_count": pipe_count,
                "structure_count": struct_count,
                "source": str(path),
            }
        )

    if surfaces and not any(surface["point_count"] for surface in surfaces):
        warnings.append("LandXML surfaces were found, but no explicit point data was parsed.")
    return {
        "success": bool(points or surfaces or alignments or pipe_networks),
        "source": str(path),
        "source_type": "landxml",
        "point_count": len(points),
        "points": points,
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "alignment_count": len(alignments),
        "alignments": alignments,
        "pipe_network_count": len(pipe_networks),
        "pipe_networks": pipe_networks,
        "warnings": warnings,
        "truth_label": "LandXML parsed into canonical exchange metadata; complex Civil3D object fidelity still requires engineer review.",
    }


def build_landxml_pipe_network(plan: Dict[str, Any], *, network_name: str = "Civora Pipe Network") -> str:
    meta = safe_dict(plan.get("meta"))
    storm = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    sanitary = safe_dict(meta.get("sanitary") or meta.get("sanitary_summary"))
    root = ET.Element("LandXML", {"version": "1.2", "date": "generated"})
    networks = ET.SubElement(root, "PipeNetworks")
    network = ET.SubElement(networks, "PipeNetwork", {"name": network_name})
    pipes = ET.SubElement(network, "Pipes")
    structures = ET.SubElement(network, "Structs")

    def add_pipe(system: str, rec: Dict[str, Any], idx: int) -> None:
        name = safe_str(rec.get("pipe") or rec.get("name") or rec.get("id"), f"{system.upper()}-{idx}")
        attrs = {
            "name": name,
            "system": system,
            "length": f"{safe_float(rec.get('length_ft'), 0.0):.3f}",
            "diameter": f"{safe_float(rec.get('diameter_ft'), safe_float(rec.get('diameter_in'), 0.0) / 12.0):.3f}",
            "slope": f"{safe_float(rec.get('slope') or rec.get('slope_ft_ft'), 0.0):.6f}",
        }
        pipe_elem = ET.SubElement(pipes, "Pipe", attrs)
        path = safe_list(rec.get("path") or rec.get("route_points") or rec.get("points"))
        if path:
            centerline = ET.SubElement(pipe_elem, "Centerline")
            for point in path:
                if isinstance(point, dict):
                    x, y = safe_float(point.get("x")), safe_float(point.get("y"))
                elif isinstance(point, (list, tuple)) and len(point) >= 2:
                    x, y = safe_float(point[0]), safe_float(point[1])
                else:
                    continue
                ET.SubElement(centerline, "P").text = f"{x:.3f} {y:.3f} 0.000"

    for idx, rec in enumerate(safe_list(storm.get("segments")), start=1):
        add_pipe("storm", safe_dict(rec), idx)
    for idx, rec in enumerate(safe_list(sanitary.get("segments")), start=1):
        add_pipe("sanitary", safe_dict(rec), idx)
    for idx, rec in enumerate(safe_list(storm.get("structures")) + safe_list(sanitary.get("manholes")), start=1):
        row = safe_dict(rec)
        ET.SubElement(
            structures,
            "Struct",
            {
                "name": safe_str(row.get("name") or row.get("id"), f"STRUCT-{idx}"),
                "x": f"{safe_float(row.get('x'), 0.0):.3f}",
                "y": f"{safe_float(row.get('y'), 0.0):.3f}",
            },
        )
    report = build_export_package_report_v1(plan, export_type="landxml")
    meta_node = ET.SubElement(
        root,
        "CivoraExportPackageReport",
        {
            "source": safe_str(report.get("source")),
            "export_type": safe_str(report.get("export_type")),
            "source_project_id": safe_str(report.get("source_project_id")),
            "source_canonical_revision": safe_str(report.get("source_canonical_revision")),
            "source_canonical_hash": safe_str(report.get("source_canonical_hash")),
            "generated_at": safe_str(report.get("generated_at")),
            "standards_status": safe_str(report.get("standards_status")),
            "existing_conditions_status": safe_str(report.get("existing_conditions_status")),
            "engine_depth_status": safe_str(report.get("engine_depth_status")),
            "construction_release_blocked": str(bool(report.get("construction_release_blocked"))).lower(),
            "layer_contract_status": safe_str(report.get("layer_contract_status")),
            "deliverable_confidence": safe_str(report.get("deliverable_confidence")),
            "civil3d_compatibility": safe_str(report.get("civil3d_compatibility")),
            "dwg_compatibility": safe_str(report.get("dwg_compatibility")),
        },
    )
    for key in ("included_systems", "excluded_systems", "stale_outputs_detected", "missing_inputs", "canonical_ids_included"):
        values_node = ET.SubElement(meta_node, key)
        for value in safe_list(report.get(key)):
            ET.SubElement(values_node, "Item").text = safe_str(value)
    return ET.tostring(root, encoding="unicode")


__all__ = ["build_landxml_pipe_network", "import_landxml"]
