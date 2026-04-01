from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


EPS = 1e-9
STRICT_MODE = "strict"
ASSISTED_MODE = "assisted"


# =============================================================================
# INPUT / OUTPUT MODELS
# =============================================================================

@dataclass
class SketchPrimitive:
    primitive_type: str  # line | rectangle | circle | polygon | text_region | arrow
    points: List[Tuple[float, float]] = field(default_factory=list)
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    rotation_deg: Optional[float] = None
    text: Optional[str] = None
    label: Optional[str] = None
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SketchScaleReference:
    pixel_length: float
    real_length: float
    units: str = "ft"

    def pixels_per_unit(self) -> float:
        if self.real_length <= 0.0:
            raise ValueError("real_length must be > 0.")
        return self.pixel_length / self.real_length


@dataclass
class SketchToPlanRequest:
    mode: str = STRICT_MODE

    primitives: List[SketchPrimitive] = field(default_factory=list)
    plan_type: Optional[str] = None
    units: str = "ft"

    scale_reference: Optional[SketchScaleReference] = None
    pixels_per_unit: Optional[float] = None

    infer_building_rectangles: bool = True
    infer_lot_boundary: bool = True
    infer_internal_roads: bool = True
    infer_labels: bool = True
    infer_text_notes: bool = True

    min_feature_size: float = 8.0
    rectangle_angle_tol_deg: float = 8.0

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SketchAssumption:
    field_name: str
    assumed_value: Any
    reason: str


@dataclass
class SketchIssue:
    code: str
    severity: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SketchPlanObject:
    object_type: str
    geometry_type: str
    label: Optional[str] = None
    points: List[Tuple[float, float]] = field(default_factory=list)
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    rotation_deg: Optional[float] = None
    layer_hint: Optional[str] = None
    source_primitive_type: Optional[str] = None
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SketchToPlanResult:
    success: bool
    message: str = ""
    plan_type: str = "unknown"
    units: str = "ft"
    pixels_per_unit: Optional[float] = None
    objects: List[SketchPlanObject] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    issues: List[SketchIssue] = field(default_factory=list)
    assumptions: List[SketchAssumption] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def error_count(self) -> int:
        return len(self.errors) + sum(1 for i in self.issues if i.severity.lower() == "error")

    def warning_count(self) -> int:
        return len(self.warnings) + sum(1 for i in self.issues if i.severity.lower() == "warning")


# =============================================================================
# ENGINE
# =============================================================================

class SketchToPlanEngine:
    """
    Structured sketch-to-plan engine foundation.

    Design goals:
    - no fake CV claims
    - deterministic conversion from provided primitives to plan objects
    - strict / assisted modes
    - planner-ready output
    - future-compatible with image_analysis_engine outputs

    Current behavior:
    - validates sketch primitives
    - resolves scale if explicitly given
    - classifies rectangles/lines/circles into plan-oriented objects
    - infers likely lot, building, road, note, and symbol objects
    - returns structured objects that can be consumed by planner/UI later

    Future layering:
    - OCR-backed text extraction
    - symbol recognition
    - contour/sketch cleanup
    - primitive graph reasoning
    - topology inference
    """

    VALID_PLAN_TYPES = {
        "unknown",
        "site_plan",
        "floor_plan",
        "grading_plan",
        "drainage_plan",
        "utility_plan",
        "subdivision_plan",
        "bridge_plan",
        "corridor_plan",
    }

    def convert(self, request: SketchToPlanRequest) -> SketchToPlanResult:
        result = SketchToPlanResult(success=True, message="Sketch converted to structured plan objects.")
        request = self._normalize_request(request, result)

        if result.error_count() > 0:
            result.success = False
            result.message = "Sketch-to-plan request validation failed."
            return result

        primitives = self._clean_primitives(request.primitives, request, result)
        if result.error_count() > 0:
            result.success = False
            result.message = "Sketch primitive validation failed."
            return result

        objects: List[SketchPlanObject] = []

        if request.infer_lot_boundary:
            lot_obj = self._infer_lot_boundary(primitives, request, result)
            if lot_obj is not None:
                objects.append(lot_obj)

        objects.extend(self._infer_rectangular_objects(primitives, request, result))
        objects.extend(self._infer_line_objects(primitives, request, result))
        objects.extend(self._infer_circle_objects(primitives, request, result))
        objects.extend(self._infer_text_objects(primitives, request, result))

        self._post_validate(objects, request, result)

        result.objects = objects
        result.plan_type = request.plan_type or self._infer_plan_type(objects)
        result.units = request.units
        result.pixels_per_unit = self._resolve_pixels_per_unit(request, result)
        result.metadata = {
            "primitive_count": len(primitives),
            "object_count": len(objects),
            "line_object_count": sum(1 for o in objects if o.geometry_type == "polyline"),
            "polygon_object_count": sum(1 for o in objects if o.geometry_type == "polygon"),
            "text_object_count": sum(1 for o in objects if o.geometry_type == "text"),
            "mode": request.mode,
            "future_planner_ready": True,
            **request.meta,
        }

        if result.error_count() > 0:
            result.success = False
            result.message = "Sketch conversion completed with blocking errors."
        elif result.warning_count() > 0:
            result.message = "Sketch conversion completed with warnings."

        return result

    # ------------------------------------------------------------------
    # validation / normalization
    # ------------------------------------------------------------------

    def _issue(self, code: str, severity: str, message: str, **context: Any) -> SketchIssue:
        return SketchIssue(code=code, severity=severity, message=message, context=context)

    def _fail(self, result: SketchToPlanResult, code: str, message: str, **context: Any) -> SketchToPlanResult:
        result.success = False
        result.message = message
        result.errors.append(message)
        result.issues.append(self._issue(code, "error", message, **context))
        return result

    def _assume(self, result: SketchToPlanResult, field_name: str, assumed_value: Any, reason: str) -> Any:
        result.assumptions.append(SketchAssumption(field_name=field_name, assumed_value=assumed_value, reason=reason))
        return assumed_value

    def _normalize_request(self, request: SketchToPlanRequest, result: SketchToPlanResult) -> SketchToPlanRequest:
        mode = str(request.mode or STRICT_MODE).strip().lower()
        if mode not in {STRICT_MODE, ASSISTED_MODE}:
            result.issues.append(self._issue("MODE_INVALID", "error", "mode must be 'strict' or 'assisted'.", mode=request.mode))
            mode = STRICT_MODE

        plan_type = request.plan_type
        if plan_type is not None:
            plan_type = str(plan_type).strip().lower()
            if plan_type not in self.VALID_PLAN_TYPES:
                if mode == STRICT_MODE:
                    result.issues.append(self._issue(
                        "PLAN_TYPE_INVALID",
                        "error",
                        f"plan_type must be one of {sorted(self.VALID_PLAN_TYPES)}.",
                        plan_type=request.plan_type,
                    ))
                else:
                    plan_type = self._assume(result, "plan_type", "unknown", "Assisted mode defaulted invalid plan_type to 'unknown'.")

        if request.scale_reference is not None:
            if request.scale_reference.pixel_length <= 0.0 or request.scale_reference.real_length <= 0.0:
                result.issues.append(self._issue(
                    "SCALE_REFERENCE_INVALID",
                    "error",
                    "scale_reference pixel_length and real_length must be > 0.",
                ))

        if request.pixels_per_unit is not None and request.pixels_per_unit <= 0.0:
            result.issues.append(self._issue("PIXELS_PER_UNIT_INVALID", "error", "pixels_per_unit must be > 0.", value=request.pixels_per_unit))

        if request.min_feature_size <= 0.0:
            result.issues.append(self._issue("MIN_FEATURE_SIZE_INVALID", "error", "min_feature_size must be > 0.", value=request.min_feature_size))

        return SketchToPlanRequest(
            mode=mode,
            primitives=list(request.primitives),
            plan_type=plan_type,
            units=str(request.units or "ft"),
            scale_reference=request.scale_reference,
            pixels_per_unit=request.pixels_per_unit,
            infer_building_rectangles=bool(request.infer_building_rectangles),
            infer_lot_boundary=bool(request.infer_lot_boundary),
            infer_internal_roads=bool(request.infer_internal_roads),
            infer_labels=bool(request.infer_labels),
            infer_text_notes=bool(request.infer_text_notes),
            min_feature_size=float(request.min_feature_size),
            rectangle_angle_tol_deg=float(request.rectangle_angle_tol_deg),
            meta=dict(request.meta),
        )

    def _clean_primitives(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> List[SketchPrimitive]:
        cleaned: List[SketchPrimitive] = []

        if not primitives:
            msg = "No sketch primitives were provided."
            if request.mode == STRICT_MODE:
                result.errors.append(msg)
                result.issues.append(self._issue("NO_PRIMITIVES", "error", msg))
            else:
                result.warnings.append(msg)
                result.issues.append(self._issue("NO_PRIMITIVES", "warning", msg))
            return cleaned

        for idx, primitive in enumerate(primitives, start=1):
            ptype = str(primitive.primitive_type or "").strip().lower()
            if not ptype:
                msg = f"Primitive {idx} is missing primitive_type."
                if request.mode == STRICT_MODE:
                    result.issues.append(self._issue("PRIMITIVE_TYPE_REQUIRED", "error", msg, primitive_index=idx))
                    continue
                ptype = str(self._assume(result, f"primitive_{idx}.primitive_type", "unknown", "Assisted mode defaulted missing primitive_type."))

            points = []
            for p in primitive.points:
                if len(p) != 2:
                    result.issues.append(self._issue("POINT_INVALID", "warning", f"Primitive {idx} contains invalid point.", primitive_index=idx))
                    continue
                points.append((float(p[0]), float(p[1])))

            cleaned_primitive = SketchPrimitive(
                primitive_type=ptype,
                points=points,
                center=(float(primitive.center[0]), float(primitive.center[1])) if primitive.center is not None else None,
                radius=float(primitive.radius) if primitive.radius is not None else None,
                width=float(primitive.width) if primitive.width is not None else None,
                height=float(primitive.height) if primitive.height is not None else None,
                rotation_deg=float(primitive.rotation_deg) if primitive.rotation_deg is not None else None,
                text=primitive.text,
                label=primitive.label,
                confidence=float(primitive.confidence),
                meta=dict(primitive.meta),
            )

            if not self._primitive_meets_min_size(cleaned_primitive, request.min_feature_size):
                result.issues.append(self._issue(
                    "PRIMITIVE_TOO_SMALL",
                    "warning",
                    f"Primitive {idx} is below min_feature_size threshold.",
                    primitive_index=idx,
                    primitive_type=ptype,
                ))
                continue

            cleaned.append(cleaned_primitive)

        return cleaned

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------

    def _infer_lot_boundary(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> Optional[SketchPlanObject]:
        rectangles = [p for p in primitives if p.primitive_type == "rectangle"]
        polygons = [p for p in primitives if p.primitive_type == "polygon"]

        best: Optional[SketchPrimitive] = None
        best_area = -1.0

        for p in rectangles:
            area = (p.width or 0.0) * (p.height or 0.0)
            if area > best_area:
                best_area = area
                best = p

        for p in polygons:
            bbox = self._bbox_from_points(p.points)
            if bbox is None:
                continue
            area = bbox[2] * bbox[3]
            if area > best_area:
                best_area = area
                best = p

        if best is None:
            return None

        if best.primitive_type == "rectangle":
            pts = self._rectangle_points_from_primitive(best)
            return SketchPlanObject(
                object_type="lot_boundary",
                geometry_type="polygon",
                label=best.label or "LOT",
                points=pts,
                width=best.width,
                height=best.height,
                rotation_deg=best.rotation_deg,
                layer_hint="SITE",
                source_primitive_type="rectangle",
                confidence=best.confidence,
                meta={"inference": "largest_rectangle"},
            )

        return SketchPlanObject(
            object_type="lot_boundary",
            geometry_type="polygon",
            label=best.label or "LOT",
            points=list(best.points),
            layer_hint="SITE",
            source_primitive_type="polygon",
            confidence=best.confidence,
            meta={"inference": "largest_polygon"},
        )

    def _infer_rectangular_objects(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> List[SketchPlanObject]:
        out: List[SketchPlanObject] = []
        rectangles = [p for p in primitives if p.primitive_type == "rectangle"]

        if not rectangles:
            return out

        sorted_rects = sorted(
            rectangles,
            key=lambda p: (p.width or 0.0) * (p.height or 0.0),
            reverse=True,
        )

        # largest likely lot already handled, remaining may be buildings/pads/rooms
        for idx, rect in enumerate(sorted_rects):
            pts = self._rectangle_points_from_primitive(rect)
            label = rect.label or rect.text or f"RECT_{idx+1}"
            area = (rect.width or 0.0) * (rect.height or 0.0)

            obj_type = "rectangle_feature"
            layer_hint = "SITE"

            if request.infer_building_rectangles and area > 0.0:
                if idx == 0 and request.infer_lot_boundary:
                    # skip first if lot boundary likely consumed
                    continue
                obj_type = "building_footprint"
                layer_hint = "BUILDING"

            out.append(
                SketchPlanObject(
                    object_type=obj_type,
                    geometry_type="polygon",
                    label=label,
                    points=pts,
                    width=rect.width,
                    height=rect.height,
                    rotation_deg=rect.rotation_deg,
                    layer_hint=layer_hint,
                    source_primitive_type="rectangle",
                    confidence=rect.confidence,
                    meta={"area_px2": area},
                )
            )

        return out

    def _infer_line_objects(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> List[SketchPlanObject]:
        out: List[SketchPlanObject] = []
        for idx, line in enumerate([p for p in primitives if p.primitive_type == "line"], start=1):
            if len(line.points) < 2:
                continue

            label = line.label or line.text or f"LINE_{idx}"
            obj_type = "linework"
            layer_hint = "SITE"

            if request.infer_internal_roads and self._polyline_length(line.points) >= request.min_feature_size * 3.0:
                obj_type = "internal_road_centerline"
                layer_hint = "ROAD"

            out.append(
                SketchPlanObject(
                    object_type=obj_type,
                    geometry_type="polyline",
                    label=label,
                    points=list(line.points),
                    layer_hint=layer_hint,
                    source_primitive_type="line",
                    confidence=line.confidence,
                    meta={"length_px": self._polyline_length(line.points)},
                )
            )
        return out

    def _infer_circle_objects(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> List[SketchPlanObject]:
        out: List[SketchPlanObject] = []
        for idx, circle in enumerate([p for p in primitives if p.primitive_type == "circle"], start=1):
            if circle.center is None or circle.radius is None:
                continue
            out.append(
                SketchPlanObject(
                    object_type="circular_feature",
                    geometry_type="circle",
                    label=circle.label or circle.text or f"CIRCLE_{idx}",
                    center=circle.center,
                    radius=circle.radius,
                    layer_hint="SITE",
                    source_primitive_type="circle",
                    confidence=circle.confidence,
                    meta={},
                )
            )
        return out

    def _infer_text_objects(
        self,
        primitives: Sequence[SketchPrimitive],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> List[SketchPlanObject]:
        out: List[SketchPlanObject] = []
        if not request.infer_text_notes:
            return out

        text_like = [p for p in primitives if p.primitive_type in {"text_region", "label"}]
        for idx, text_primitive in enumerate(text_like, start=1):
            center = text_primitive.center
            if center is None:
                bbox = self._bbox_from_points(text_primitive.points)
                if bbox is not None:
                    center = (bbox[0] + bbox[2] / 2.0, bbox[1] + bbox[3] / 2.0)

            if center is None:
                continue

            out.append(
                SketchPlanObject(
                    object_type="text_note",
                    geometry_type="text",
                    label=text_primitive.text or text_primitive.label or f"NOTE_{idx}",
                    center=center,
                    layer_hint="ANNO",
                    source_primitive_type=text_primitive.primitive_type,
                    confidence=text_primitive.confidence,
                    meta={},
                )
            )
        return out

    # ------------------------------------------------------------------
    # post validation / helpers
    # ------------------------------------------------------------------

    def _post_validate(
        self,
        objects: Sequence[SketchPlanObject],
        request: SketchToPlanRequest,
        result: SketchToPlanResult,
    ) -> None:
        if not objects:
            msg = "No plan objects were created from provided primitives."
            if request.mode == STRICT_MODE:
                result.errors.append(msg)
                result.issues.append(self._issue("NO_PLAN_OBJECTS", "error", msg))
            else:
                result.warnings.append(msg)
                result.issues.append(self._issue("NO_PLAN_OBJECTS", "warning", msg))

        lot_count = sum(1 for o in objects if o.object_type == "lot_boundary")
        if lot_count == 0 and request.infer_lot_boundary:
            result.issues.append(self._issue(
                "LOT_NOT_INFERRED",
                "warning",
                "Lot boundary inference was enabled but no lot boundary object was created.",
            ))

    def _infer_plan_type(self, objects: Sequence[SketchPlanObject]) -> str:
        building_count = sum(1 for o in objects if o.object_type == "building_footprint")
        road_count = sum(1 for o in objects if o.object_type == "internal_road_centerline")
        lot_count = sum(1 for o in objects if o.object_type == "lot_boundary")

        if lot_count > 0 and road_count > 0:
            return "site_plan"
        if building_count > 2 and road_count == 0:
            return "floor_plan"
        if road_count > 0:
            return "corridor_plan"
        return "unknown"

    def _resolve_pixels_per_unit(self, request: SketchToPlanRequest, result: SketchToPlanResult) -> Optional[float]:
        if request.scale_reference is not None:
            return request.scale_reference.pixels_per_unit()
        if request.pixels_per_unit is not None:
            return request.pixels_per_unit

        if request.mode == ASSISTED_MODE:
            result.warnings.append("No explicit scale reference was provided; output geometry remains unscaled.")
            result.issues.append(self._issue(
                "SCALE_UNKNOWN",
                "warning",
                "No explicit scale reference was provided; output geometry remains unscaled.",
            ))
            return None

        result.issues.append(self._issue(
            "SCALE_NOT_PROVIDED",
            "warning",
            "No scale reference or pixels_per_unit was provided.",
        ))
        return None

    def _rectangle_points_from_primitive(self, rect: SketchPrimitive) -> List[Tuple[float, float]]:
        if rect.points and len(rect.points) >= 4:
            return list(rect.points)

        if rect.center is None or rect.width is None or rect.height is None:
            return []

        cx, cy = rect.center
        hw = rect.width / 2.0
        hh = rect.height / 2.0
        return [
            (cx - hw, cy - hh),
            (cx + hw, cy - hh),
            (cx + hw, cy + hh),
            (cx - hw, cy + hh),
        ]

    def _primitive_meets_min_size(self, primitive: SketchPrimitive, min_feature_size: float) -> bool:
        if primitive.primitive_type == "line":
            return self._polyline_length(primitive.points) >= min_feature_size - EPS
        if primitive.primitive_type == "rectangle":
            if primitive.width is not None and primitive.height is not None:
                return primitive.width >= min_feature_size - EPS and primitive.height >= min_feature_size - EPS
            if len(primitive.points) >= 4:
                bbox = self._bbox_from_points(primitive.points)
                if bbox is None:
                    return False
                return bbox[2] >= min_feature_size - EPS and bbox[3] >= min_feature_size - EPS
            return False
        if primitive.primitive_type == "circle":
            return primitive.radius is not None and primitive.radius * 2.0 >= min_feature_size - EPS
        return True

    def _bbox_from_points(self, pts: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float, float, float]]:
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        return (min_x, min_y, max_x - min_x, max_y - min_y)

    def _polyline_length(self, pts: Sequence[Tuple[float, float]]) -> float:
        total = 0.0
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            total += (dx * dx + dy * dy) ** 0.5
        return total


# =============================================================================
# CONVENIENCE HELPER
# =============================================================================

def sketch_to_plan(request: SketchToPlanRequest) -> SketchToPlanResult:
    return SketchToPlanEngine().convert(request)
