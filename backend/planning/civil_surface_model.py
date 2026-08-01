from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from engines.surface_engine import GridSurface, TinSurface, compare_surfaces

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str


REVIEW_ONLY_TRUTH_LABEL = (
    "Civil-style surface and feature-line data is review/design evidence only; "
    "construction release remains blocked without accepted survey/control and engineer review."
)

NON_SURVEY_SOURCE_TYPES = {
    "assumed",
    "address_context",
    "dem",
    "gis",
    "image_inferred",
    "inferred",
    "lidar",
    "manual",
    "terrain_inferred",
    "user-drawn",
}


@dataclass(frozen=True)
class SurfaceDatum:
    horizontal: str = ""
    vertical: str = ""
    coordinate_system: str = ""
    status: str = "missing"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizontal": self.horizontal,
            "vertical": self.vertical,
            "coordinate_system": self.coordinate_system,
            "status": self.status,
        }


@dataclass(frozen=True)
class FeatureLineVertex:
    x: float
    y: float
    z: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "z": None if self.z is None else round(self.z, 3)}


@dataclass(frozen=True)
class FeatureLineContract:
    feature_line_id: str
    type: str
    vertices: Sequence[FeatureLineVertex]
    source: str = ""
    source_confidence: str = "unknown"
    linked_surface_id: str = ""
    review_status: str = "review_required"
    blockers: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        validation = validate_feature_line(self)
        blockers = list(dict.fromkeys([*self.blockers, *validation["blockers"]]))
        return {
            "schema_version": "feature_line_contract_v1",
            "feature_line_id": self.feature_line_id,
            "type": self.type,
            "vertices": [vertex.to_dict() for vertex in self.vertices],
            "source": self.source,
            "source_confidence": self.source_confidence,
            "linked_surface_id": self.linked_surface_id,
            "review_status": self.review_status,
            "review_required": True,
            "construction_release_allowed": False,
            "validation": validation,
            "blockers": blockers,
            "truth_label": REVIEW_ONLY_TRUTH_LABEL,
        }


def feature_line_from_dict(value: Dict[str, Any], *, default_surface_id: str = "") -> FeatureLineContract:
    rec = safe_dict(value)
    vertices: List[FeatureLineVertex] = []
    for item in safe_list(rec.get("vertices") or rec.get("points")):
        point = safe_dict(item)
        if point:
            z_value = point.get("z", point.get("elevation"))
            vertices.append(
                FeatureLineVertex(
                    x=safe_float(point.get("x")),
                    y=safe_float(point.get("y")),
                    z=None if z_value is None else safe_float(z_value),
                )
            )
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            vertices.append(
                FeatureLineVertex(
                    x=safe_float(item[0]),
                    y=safe_float(item[1]),
                    z=safe_float(item[2]) if len(item) >= 3 and item[2] is not None else None,
                )
            )
    return FeatureLineContract(
        feature_line_id=safe_str(rec.get("feature_line_id") or rec.get("id"), "feature-line"),
        type=safe_str(rec.get("type"), "feature_line"),
        vertices=vertices,
        source=safe_str(rec.get("source")),
        source_confidence=safe_str(rec.get("source_confidence") or rec.get("confidence"), "unknown"),
        linked_surface_id=safe_str(rec.get("linked_surface_id") or rec.get("linked_surface"), default_surface_id),
        review_status=safe_str(rec.get("review_status"), "review_required"),
        blockers=tuple(safe_str(item) for item in safe_list(rec.get("blockers")) if safe_str(item)),
    )


def validate_feature_line(feature_line: FeatureLineContract | Dict[str, Any]) -> Dict[str, Any]:
    contract = feature_line_from_dict(feature_line) if isinstance(feature_line, dict) else feature_line
    blockers: List[str] = []
    warnings: List[str] = []
    vertices = list(contract.vertices or [])
    if not contract.feature_line_id:
        blockers.append("missing_feature_line_id")
    if len(vertices) < 2:
        blockers.append("feature_line_needs_at_least_two_vertices")
    if contract.type in {"breakline", "grade_break", "curb", "wall", "swale"} and any(vertex.z is None for vertex in vertices):
        blockers.append("breakline_requires_vertex_elevations")
    elif any(vertex.z is None for vertex in vertices):
        warnings.append("feature_line_has_partial_elevations")
    if not contract.linked_surface_id:
        blockers.append("feature_line_missing_linked_surface")
    if _is_low_confidence_source(contract.source_confidence) or safe_str(contract.source).lower() in NON_SURVEY_SOURCE_TYPES:
        warnings.append("feature_line_source_needs_survey_control_review")
    return {
        "valid": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "review_required": True,
        "construction_release_allowed": False,
    }


def build_surface_contract(
    *,
    surface_id: str,
    surface_role: str,
    source_type: str,
    source_confidence: str,
    control_status: str,
    datum: Optional[SurfaceDatum | Dict[str, Any]] = None,
    grid_surface: Optional[GridSurface] = None,
    tin_surface: Optional[TinSurface] = None,
    points: Optional[Sequence[Any]] = None,
    triangles: Optional[Sequence[Any]] = None,
    feature_lines: Optional[Sequence[FeatureLineContract | Dict[str, Any]]] = None,
    breakline_refs: Optional[Sequence[str]] = None,
    contours: Optional[Sequence[Dict[str, Any]]] = None,
    spot_elevations: Optional[Sequence[Dict[str, Any]]] = None,
    source_revision: str = "",
    last_validated_source_revision: str = "",
) -> Dict[str, Any]:
    datum_contract = _normalize_datum(datum)
    normalized_source_type = safe_str(source_type, "unknown")
    normalized_confidence = safe_str(source_confidence, "unknown")
    normalized_control = safe_str(control_status, "missing")
    feature_contracts = [
        item if isinstance(item, FeatureLineContract) else feature_line_from_dict(item, default_surface_id=surface_id)
        for item in list(feature_lines or [])
    ]
    validations = [validate_feature_line(item) for item in feature_contracts]
    blockers = _surface_blockers(
        source_type=normalized_source_type,
        source_confidence=normalized_confidence,
        control_status=normalized_control,
        datum=datum_contract,
        source_revision=source_revision,
        last_validated_source_revision=last_validated_source_revision,
    )
    for validation in validations:
        blockers.extend(validation["blockers"])
    blockers = list(dict.fromkeys(blockers))
    slope_range = _slope_range(grid_surface=grid_surface, tin_surface=tin_surface)
    point_count = len(points or []) or _safe_len(getattr(tin_surface, "points", None))
    triangle_count = len(triangles or []) or _safe_len(getattr(tin_surface, "triangles", None))
    grid_metadata = _grid_metadata(grid_surface)
    tin_metadata = dict(safe_dict(getattr(tin_surface, "metadata", {})))
    return {
        "schema_version": "civil_surface_contract_v1",
        "surface_id": safe_str(surface_id, "surface"),
        "surface_role": safe_str(surface_role, "surface"),
        "source_type": normalized_source_type,
        "source_confidence": normalized_confidence,
        "control_status": normalized_control,
        "datum": datum_contract.to_dict(),
        "datum_status": datum_contract.status,
        "points_metadata": {"count": point_count},
        "triangles_metadata": {"count": triangle_count, **tin_metadata},
        "grid_metadata": grid_metadata,
        "breaklines": list(breakline_refs or [item.feature_line_id for item in feature_contracts if item.type == "breakline"]),
        "feature_lines": [item.to_dict() for item in feature_contracts],
        "contours": list(contours or []),
        "spot_elevations": list(spot_elevations or []),
        "slope_range": slope_range,
        "review_required": True,
        "construction_release_allowed": False,
        "blockers": blockers,
        "validation": {
            "valid_for_review": not blockers,
            "feature_line_validation": validations,
            "missing_datum_or_control": any(item in blockers for item in ("missing_datum", "missing_control", "unverified_control")),
            "stale_or_dirty": "stale_or_dirty_surface_source" in blockers,
        },
        "truth_label": REVIEW_ONLY_TRUTH_LABEL,
    }


def compare_existing_proposed_surfaces(existing: GridSurface, proposed: GridSurface) -> Dict[str, Any]:
    comparison = compare_surfaces(existing, proposed)
    return {
        "schema_version": "civil_surface_comparison_v1",
        "existing_surface_id": "EG",
        "proposed_surface_id": "FG",
        "comparison": comparison,
        "cut_fill_summary_hook": cut_fill_summary_hook(comparison),
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "EG/FG comparison is sampled design evidence and requires survey/control and engineer review before reliance.",
    }


def cut_fill_summary_hook(comparison: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cut_cf": round(safe_float(comparison.get("cut_cf")), 3),
        "fill_cf": round(safe_float(comparison.get("fill_cf")), 3),
        "net_cf": round(safe_float(comparison.get("net_cf")), 3),
        "review_required": True,
        "construction_release_allowed": False,
        "blockers": ["accepted_surface_review_required"],
    }


def _normalize_datum(datum: Optional[SurfaceDatum | Dict[str, Any]]) -> SurfaceDatum:
    if isinstance(datum, SurfaceDatum):
        return datum
    rec = safe_dict(datum)
    return SurfaceDatum(
        horizontal=safe_str(rec.get("horizontal") or rec.get("horizontal_datum")),
        vertical=safe_str(rec.get("vertical") or rec.get("vertical_datum") or rec.get("datum")),
        coordinate_system=safe_str(rec.get("coordinate_system") or rec.get("crs") or rec.get("epsg")),
        status=safe_str(rec.get("status"), "missing"),
    )


def _surface_blockers(
    *,
    source_type: str,
    source_confidence: str,
    control_status: str,
    datum: SurfaceDatum,
    source_revision: str,
    last_validated_source_revision: str,
) -> List[str]:
    blockers: List[str] = []
    if datum.status not in {"accepted", "verified"} or not (datum.vertical and datum.coordinate_system):
        blockers.append("missing_datum")
    if control_status not in {"accepted", "verified"}:
        blockers.append("missing_control" if control_status in {"", "missing", "unknown"} else "unverified_control")
    if source_type.lower() in NON_SURVEY_SOURCE_TYPES or _is_low_confidence_source(source_confidence):
        blockers.append("not_survey_control_backed")
    if source_revision and last_validated_source_revision and source_revision != last_validated_source_revision:
        blockers.append("stale_or_dirty_surface_source")
    return blockers


def _is_low_confidence_source(value: str) -> bool:
    text = safe_str(value).lower()
    return text in {"", "assumed", "draft", "inferred", "low", "unknown", "user_drawn_review_required"}


def _grid_metadata(surface: Optional[GridSurface]) -> Dict[str, Any]:
    if surface is None:
        return {"available": False}
    return {
        "available": True,
        "nrows": safe_int(getattr(surface, "nrows", 0)),
        "ncols": safe_int(getattr(surface, "ncols", 0)),
        "cell_size": round(safe_float(getattr(surface, "cell_size", 0.0)), 3),
        "bounds": [round(safe_float(item), 3) for item in surface.bounds()],
    }


def _slope_range(*, grid_surface: Optional[GridSurface], tin_surface: Optional[TinSurface]) -> Dict[str, Any]:
    slopes: List[float] = []
    if tin_surface is not None:
        for triangle in getattr(tin_surface, "triangles", []) or []:
            plane = getattr(triangle, "plane", (0.0, 0.0, 0.0))
            if len(plane) >= 2:
                slopes.append((safe_float(plane[0]) ** 2 + safe_float(plane[1]) ** 2) ** 0.5 * 100.0)
    if grid_surface is not None and not slopes:
        for row in range(max(0, grid_surface.nrows - 1)):
            for col in range(max(0, grid_surface.ncols - 1)):
                dz_dx = (grid_surface.values[row][col + 1] - grid_surface.values[row][col]) / max(grid_surface.cell_size, 1e-9)
                dz_dy = (grid_surface.values[row + 1][col] - grid_surface.values[row][col]) / max(grid_surface.cell_size, 1e-9)
                slopes.append((dz_dx * dz_dx + dz_dy * dz_dy) ** 0.5 * 100.0)
    if not slopes:
        return {"min_pct": None, "max_pct": None}
    return {"min_pct": round(min(slopes), 3), "max_pct": round(max(slopes), 3)}


def _safe_len(value: Any) -> int:
    try:
        return len(value or [])
    except Exception:
        return 0
