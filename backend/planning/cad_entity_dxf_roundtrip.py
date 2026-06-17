from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List, Optional, Tuple

import ezdxf

from .cad_entity_model import CAD_ENTITY_MODEL_VERSION, build_cad_entity_model
from .common import safe_dict, safe_float, safe_list, safe_str


DXF_ROUNDTRIP_REPORT_VERSION = "dxf_roundtrip_report_v1"

SUPPORTED_DXF_ENTITY_MAPPING = {
    "line": "LINE",
    "polyline": "LWPOLYLINE",
    "polygon": "LWPOLYLINE",
    "rectangle": "LWPOLYLINE",
    "circle": "CIRCLE",
    "arc": "ARC",
    "text": "TEXT",
    "dimension": "DIMENSION",
    "hatch": "HATCH",
    "block_reference": "INSERT",
}


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _point(value: Any) -> Optional[Tuple[float, float]]:
    if isinstance(value, dict):
        x = safe_float(value.get("x"), None)
        y = safe_float(value.get("y"), None)
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x = safe_float(value[0], None)
        y = safe_float(value[1], None)
    else:
        return None
    if x is None or y is None:
        return None
    return float(x), float(y)


def _points(values: Any) -> List[Tuple[float, float]]:
    return [point for point in (_point(item) for item in safe_list(values)) if point is not None]


def _layer_name(entity: Dict[str, Any], layer_by_id: Dict[str, Dict[str, Any]]) -> str:
    layer_id = safe_str(entity.get("layer_id"), "layer_draft")
    layer = safe_dict(layer_by_id.get(layer_id))
    return safe_str(layer.get("name") or layer_id, "Draft").replace(" ", "_")[:255]


def _aci_color(value: Any) -> int:
    if isinstance(value, int):
        return max(1, min(value, 255))
    text = safe_str(value).strip()
    if text.isdigit():
        return max(1, min(int(text), 255))
    lower = text.lower()
    if lower in {"red", "#ff0000"}:
        return 1
    if lower in {"yellow", "#ffff00"}:
        return 2
    if lower in {"green", "#00ff00"}:
        return 3
    if lower in {"cyan", "#00ffff", "blue", "#0000ff"}:
        return 4 if lower in {"cyan", "#00ffff"} else 5
    if lower in {"magenta", "#ff00ff"}:
        return 6
    return 7


def _ensure_layers(doc: Any, model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    layer_by_id = {safe_str(layer.get("id")): safe_dict(layer) for layer in safe_list(model.get("layers")) if safe_dict(layer)}
    for layer in layer_by_id.values():
        name = safe_str(layer.get("name") or layer.get("id"), "Draft").replace(" ", "_")[:255]
        if name in doc.layers:
            target = doc.layers.get(name)
        else:
            target = doc.layers.add(name)
        target.dxf.color = _aci_color(layer.get("color"))
        linetype = safe_str(layer.get("linetype"), "CONTINUOUS").upper()
        target.dxf.linetype = linetype if linetype in doc.linetypes else "CONTINUOUS"
    return layer_by_id


def _style_defaults(entity: Dict[str, Any], style_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    style = safe_dict(style_by_id.get(safe_str(entity.get("style_id"))))
    return safe_dict(style.get("defaults"))


def _dxf_attribs(entity: Dict[str, Any], layer: str, style_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    defaults = _style_defaults(entity, style_by_id)
    attribs: Dict[str, Any] = {"layer": layer}
    color = defaults.get("color")
    if color and safe_str(color).lower() != "by_layer":
        attribs["color"] = _aci_color(color)
    linetype = safe_str(defaults.get("linetype")).upper()
    if linetype and linetype != "BY_LAYER":
        attribs["linetype"] = linetype
    return attribs


def _rect_points(geometry: Dict[str, Any]) -> List[Tuple[float, float]]:
    points = _points(geometry.get("points") or geometry.get("vertices"))
    if len(points) >= 4:
        return points[:4]
    origin = _point(geometry.get("origin") or geometry.get("min"))
    width = safe_float(geometry.get("width"), 0.0)
    height = safe_float(geometry.get("height"), 0.0)
    if not origin or width == 0.0 or height == 0.0:
        return []
    x, y = origin
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def _ensure_block(doc: Any, block_name: str) -> str:
    name = safe_str(block_name, "CIVORA_SYMBOL_PLACEHOLDER").replace(" ", "_")[:255]
    if name in doc.blocks:
        return name
    block = doc.blocks.new(name=name)
    block.add_circle((0.0, 0.0), 1.0, dxfattribs={"layer": "0"})
    block.add_line((-1.4, 0.0), (1.4, 0.0), dxfattribs={"layer": "0"})
    block.add_line((0.0, -1.4), (0.0, 1.4), dxfattribs={"layer": "0"})
    return name


def _add_entity_to_dxf(msp: Any, doc: Any, entity: Dict[str, Any], layer: str, style_by_id: Dict[str, Dict[str, Any]]) -> Tuple[bool, str]:
    entity_type = safe_str(entity.get("type"))
    geometry = safe_dict(entity.get("geometry"))
    attribs = _dxf_attribs(entity, layer, style_by_id)
    try:
        if entity_type == "line":
            start = _point(geometry.get("start"))
            end = _point(geometry.get("end"))
            if not start or not end:
                return False, "invalid_geometry"
            msp.add_line(start, end, dxfattribs=attribs)
        elif entity_type in {"polyline", "polygon"}:
            pts = _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))
            if len(pts) < (3 if entity_type == "polygon" else 2):
                return False, "invalid_geometry"
            msp.add_lwpolyline(pts, close=bool(entity_type == "polygon" or geometry.get("closed")), dxfattribs=attribs)
        elif entity_type == "rectangle":
            pts = _rect_points(geometry)
            if len(pts) < 4:
                return False, "invalid_geometry"
            msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
        elif entity_type == "circle":
            center = _point(geometry.get("center"))
            radius = safe_float(geometry.get("radius"), 0.0)
            if not center or radius <= 0.0:
                return False, "invalid_geometry"
            msp.add_circle(center, radius, dxfattribs=attribs)
        elif entity_type == "arc":
            center = _point(geometry.get("center"))
            radius = safe_float(geometry.get("radius"), 0.0)
            if not center or radius <= 0.0:
                return False, "invalid_geometry"
            msp.add_arc(center, radius, safe_float(geometry.get("start_angle"), 0.0), safe_float(geometry.get("end_angle"), 0.0), dxfattribs=attribs)
        elif entity_type == "text":
            insert = _point(geometry.get("insert") or geometry.get("position"))
            text = safe_str(geometry.get("text") or entity.get("label"))
            if not insert or not text:
                return False, "invalid_geometry"
            msp.add_text(text, dxfattribs={**attribs, "height": max(safe_float(geometry.get("height") or geometry.get("text_height"), 1.0), 0.1)}).set_placement(insert)
        elif entity_type == "dimension":
            pts = _points(geometry.get("points"))
            start = _point(geometry.get("start")) or (pts[0] if len(pts) >= 1 else None)
            end = _point(geometry.get("end")) or (pts[1] if len(pts) >= 2 else None)
            if not start or not end:
                return False, "invalid_geometry"
            offset = safe_float(geometry.get("offset"), 4.0)
            dim = msp.add_linear_dim(base=(start[0], start[1] + offset), p1=start, p2=end, dxfattribs=attribs)
            dim.render()
        elif entity_type == "hatch":
            pts = _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))
            if len(pts) < 3:
                return False, "invalid_geometry"
            hatch = msp.add_hatch(color=_aci_color(safe_dict(_style_defaults(entity, style_by_id).get("hatch")).get("color")), dxfattribs=attribs)
            hatch.paths.add_polyline_path(pts, is_closed=True)
        elif entity_type == "block_reference":
            insert = _point(geometry.get("insert") or geometry.get("origin"))
            if not insert:
                return False, "invalid_geometry"
            block_name = _ensure_block(doc, geometry.get("block_name") or entity.get("block_name") or entity.get("symbol_id"))
            msp.add_blockref(block_name, insert, dxfattribs=attribs)
        else:
            return False, "unsupported_entity_type"
    except Exception as exc:
        return False, f"dxf_write_failed:{safe_str(exc)}"
    return True, ""


def _sidecar_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")


def export_cad_entity_model_to_dxf(model: Dict[str, Any], artifact_path: Path) -> Dict[str, Any]:
    normalized = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: safe_dict(model)})
    doc = ezdxf.new("R2010")
    layer_by_id = _ensure_layers(doc, normalized)
    style_by_id = {safe_str(style.get("id")): safe_dict(style) for style in safe_list(normalized.get("styles")) if safe_dict(style)}
    msp = doc.modelspace()
    exported: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []
    for entity in safe_list(normalized.get("entities")):
        rec = safe_dict(entity)
        entity_type = safe_str(rec.get("type"))
        if entity_type not in SUPPORTED_DXF_ENTITY_MAPPING:
            unsupported.append({"entity_id": safe_str(rec.get("id")), "type": entity_type, "reason": "unsupported_entity_type"})
            continue
        layer = _layer_name(rec, layer_by_id)
        ok, reason = _add_entity_to_dxf(msp, doc, rec, layer, style_by_id)
        if ok:
            exported.append(
                {
                    "entity_id": safe_str(rec.get("id")),
                    "type": entity_type,
                    "dxf_type": SUPPORTED_DXF_ENTITY_MAPPING[entity_type],
                    "layer_id": safe_str(rec.get("layer_id")),
                    "layer": layer,
                    "style_id": safe_str(rec.get("style_id")),
                    "label": safe_str(safe_dict(rec.get("geometry")).get("text") or rec.get("label")),
                    "dirty": bool(rec.get("dirty")),
                    "stale": bool(rec.get("stale") or rec.get("review_status") == "stale"),
                }
            )
        else:
            unsupported.append({"entity_id": safe_str(rec.get("id")), "type": entity_type, "reason": reason or "dxf_write_failed"})
    doc.saveas(str(artifact_path))
    sidecar = {
        "source": "cad_entity_dxf_sidecar_v1",
        "artifact_path": str(artifact_path),
        "source_model_version": CAD_ENTITY_MODEL_VERSION,
        "entity_count": len(safe_list(normalized.get("entities"))),
        "exported_entities": exported,
        "unsupported_entities": unsupported,
        "layers": deepcopy(safe_list(normalized.get("layers"))),
        "styles": deepcopy(safe_list(normalized.get("styles"))),
        "review_required": True,
        "construction_release_allowed": False,
    }
    _sidecar_path(artifact_path).write_text(json.dumps(sidecar, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return sidecar


def _parse_dxf(artifact_path: Path) -> Dict[str, Any]:
    doc = ezdxf.readfile(str(artifact_path))
    entity_counts: Dict[str, int] = {}
    layers: List[str] = []
    colors: Dict[str, List[str]] = {}
    linetypes: Dict[str, List[str]] = {}
    text_labels: List[str] = []
    block_names: List[str] = []
    for entity in doc.modelspace():
        dxf_type = safe_str(entity.dxftype()).upper()
        entity_counts[dxf_type] = entity_counts.get(dxf_type, 0) + 1
        layer = safe_str(getattr(entity.dxf, "layer", ""))
        if layer:
            layers.append(layer)
        color = safe_str(getattr(entity.dxf, "color", ""))
        if color:
            colors.setdefault(layer, []).append(color)
        linetype = safe_str(getattr(entity.dxf, "linetype", ""))
        if linetype:
            linetypes.setdefault(layer, []).append(linetype)
        if dxf_type in {"TEXT", "MTEXT"}:
            plain_text = getattr(entity, "plain_text", None)
            text = safe_str(plain_text() if callable(plain_text) else "") or safe_str(getattr(entity.dxf, "text", ""))
            if text:
                text_labels.append(text)
        if dxf_type == "INSERT":
            block_names.append(safe_str(getattr(entity.dxf, "name", "")))
    table_layers = []
    layer_metadata = {}
    for layer in doc.layers:
        name = safe_str(layer.dxf.name)
        table_layers.append(name)
        layer_metadata[name] = {
            "color": safe_str(getattr(layer.dxf, "color", "")),
            "linetype": safe_str(getattr(layer.dxf, "linetype", "")),
        }
    return {
        "entity_counts": entity_counts,
        "layers": sorted(_unique(layers)),
        "table_layers": sorted(_unique(table_layers)),
        "layer_metadata": layer_metadata,
        "colors": {key: sorted(_unique(value)) for key, value in colors.items()},
        "linetypes": {key: sorted(_unique(value)) for key, value in linetypes.items()},
        "text_labels": _unique(text_labels),
        "block_names": _unique(block_names),
    }


def verify_cad_entity_dxf_roundtrip(model: Dict[str, Any], artifact_path: Optional[Path] = None) -> Dict[str, Any]:
    tempdir: Optional[TemporaryDirectory[str]] = None
    if artifact_path is None:
        tempdir = TemporaryDirectory()
        artifact_path = Path(tempdir.name) / "cad-entity-roundtrip.dxf"
    try:
        normalized = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: safe_dict(model)})
        sidecar = export_cad_entity_model_to_dxf(normalized, artifact_path)
        parsed = _parse_dxf(artifact_path)
        exported = [safe_dict(item) for item in safe_list(sidecar.get("exported_entities"))]
        unsupported = [safe_dict(item) for item in safe_list(sidecar.get("unsupported_entities"))]
        expected_by_dxf: Dict[str, int] = {}
        for item in exported:
            dxf_type = safe_str(item.get("dxf_type")).upper()
            expected_by_dxf[dxf_type] = expected_by_dxf.get(dxf_type, 0) + 1
        parsed_counts = safe_dict(parsed.get("entity_counts"))
        count_mismatches = [
            f"{dxf_type}:expected_{count}_parsed_{safe_str(parsed_counts.get(dxf_type), '0')}"
            for dxf_type, count in expected_by_dxf.items()
            if int(parsed_counts.get(dxf_type, 0)) < count
        ]
        expected_layers = _unique(item.get("layer") for item in exported)
        missing_layers = [layer for layer in expected_layers if layer not in safe_list(parsed.get("layers")) and layer not in safe_list(parsed.get("table_layers"))]
        expected_text = _unique(item.get("label") for item in exported if safe_str(item.get("type")) == "text")
        missing_text = [text for text in expected_text if text not in safe_list(parsed.get("text_labels"))]
        expected_blocks = _unique(item.get("entity_id") for item in exported if safe_str(item.get("type")) == "block_reference")
        parsed_block_count = len(safe_list(parsed.get("block_names")))
        sidecar_ids = _unique(item.get("entity_id") for item in exported)
        dirty_entities = _unique(item.get("id") for item in safe_list(normalized.get("entities")) if safe_dict(item).get("dirty") or safe_dict(item).get("stale") or safe_str(safe_dict(item).get("review_status")) == "stale")
        invalid_entities = _unique(
            item.get("entity_id")
            for item in safe_list(safe_dict(normalized.get("validation")).get("entities"))
            if safe_dict(item).get("valid") is False
        )
        blockers = []
        if count_mismatches:
            blockers.append("dxf_entity_count_mismatch")
        if missing_layers:
            blockers.append("dxf_layer_preservation_failed")
        if missing_text:
            blockers.append("dxf_text_preservation_failed")
        if dirty_entities:
            blockers.append("cad_entity_stale_or_dirty")
        if invalid_entities:
            blockers.append("cad_entity_validation_blocked")
        if unsupported:
            blockers.append("cad_entity_dxf_unsupported_entities")
        preserved = {
            "entity_count": not count_mismatches,
            "supported_entity_types": sorted(expected_by_dxf.keys()),
            "layers": not missing_layers,
            "colors_linetypes": bool(parsed.get("layer_metadata")),
            "text_labels": not missing_text,
            "dimensions": "DIMENSION" in parsed_counts if expected_by_dxf.get("DIMENSION") else "not_present",
            "symbol_block_placeholders": parsed_block_count >= len(expected_blocks) if expected_blocks else "not_present",
            "canonical_cad_entity_ids": bool(sidecar_ids),
        }
        lost_limited = []
        if missing_layers:
            lost_limited.append({"field": "layers", "missing": missing_layers})
        if missing_text:
            lost_limited.append({"field": "text_labels", "missing": missing_text})
        if count_mismatches:
            lost_limited.append({"field": "entity_counts", "mismatches": count_mismatches})
        if expected_blocks and parsed_block_count < len(expected_blocks):
            lost_limited.append({"field": "symbol_block_placeholders", "expected": len(expected_blocks), "parsed": parsed_block_count})
        if dirty_entities:
            lost_limited.append({"field": "export_ready_claim", "reason": "stale_or_dirty_cad_entities_block_export_ready_claims", "entity_ids": dirty_entities})
        if unsupported:
            lost_limited.append({"field": "unsupported_entities", "reason": "unsupported_cad_entities_block_export_ready_claims", "entities": deepcopy(unsupported)})
        report = {
            "source": DXF_ROUNDTRIP_REPORT_VERSION,
            "model_version": CAD_ENTITY_MODEL_VERSION,
            "artifact_path": str(artifact_path),
            "sidecar_path": str(_sidecar_path(artifact_path)),
            "supported_dxf_entity_mapping": deepcopy(SUPPORTED_DXF_ENTITY_MAPPING),
            "expected_entity_count": len(exported),
            "parsed_entity_count": sum(int(value) for value in parsed_counts.values()),
            "expected_entity_type_counts": expected_by_dxf,
            "parsed_entity_type_counts": parsed_counts,
            "preserved": preserved,
            "lost_limited": lost_limited,
            "unsupported": unsupported,
            "blockers": _unique(blockers),
            "roundtrip_preservation_matrix": {
                "entity_count": "passed" if not count_mismatches else "blocked",
                "supported_entity_types": "passed" if not count_mismatches else "limited",
                "layers": "passed" if not missing_layers else "blocked",
                "colors_linetypes": "passed" if parsed.get("layer_metadata") else "limited",
                "text_labels": "passed" if not missing_text else "blocked",
                "dimensions": "passed" if expected_by_dxf.get("DIMENSION") and parsed_counts.get("DIMENSION") else "not_present_or_not_supported_by_export",
                "symbol_block_placeholders": "passed" if expected_blocks and parsed_block_count >= len(expected_blocks) else "not_present_or_not_supported_by_export",
                "canonical_cad_entity_ids": "passed_via_sidecar" if sidecar_ids else "blocked",
            },
            "parsed_layers": safe_list(parsed.get("layers")),
            "parsed_layer_metadata": safe_dict(parsed.get("layer_metadata")),
            "parsed_text_labels": safe_list(parsed.get("text_labels")),
            "parsed_block_names": safe_list(parsed.get("block_names")),
            "canonical_cad_entity_ids": sidecar_ids,
            "stale_dirty_entity_ids": dirty_entities,
            "invalid_entity_ids": invalid_entities,
            "local_roundtrip_verified": not count_mismatches and not missing_layers and not missing_text,
            "export_ready_claim_allowed": not dirty_entities and not invalid_entities and not blockers,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": "DXF roundtrip is a local review exchange check from persistent CAD entities; it does not verify AutoCAD, Civil 3D, DWG, construction release, or professional approval.",
        }
        return report
    except Exception as exc:
        return {
            "source": DXF_ROUNDTRIP_REPORT_VERSION,
            "model_version": CAD_ENTITY_MODEL_VERSION,
            "artifact_path": str(artifact_path) if artifact_path else "",
            "preserved": {},
            "lost_limited": [],
            "unsupported": [],
            "blockers": [f"dxf_roundtrip_failed:{safe_str(exc)}"],
            "local_roundtrip_verified": False,
            "export_ready_claim_allowed": False,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": "DXF roundtrip failed locally; no readiness or external CAD compatibility is claimed.",
        }
    finally:
        if tempdir is not None:
            tempdir.cleanup()


__all__ = [
    "DXF_ROUNDTRIP_REPORT_VERSION",
    "SUPPORTED_DXF_ENTITY_MAPPING",
    "export_cad_entity_model_to_dxf",
    "verify_cad_entity_dxf_roundtrip",
]
