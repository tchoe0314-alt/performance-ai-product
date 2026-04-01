from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry_core import (
    EngineeringObject,
    Obstacle,
    Point2D,
    Point3D,
    Polygon2D,
    Polyline2D,
    ProjectModel,
    Zone,
    ZoneType,
)
from parsers.sketch_parser import (
    ParsedSketch,
    SketchInput,
    SketchParser,
    SketchPoint,
    SketchRegion,
    SketchStroke,
    SketchText,
)


@dataclass
class ImageDetection:
    """
    Neutral detected object from an image or screenshot.

    This is not doing CV by itself yet.
    It is the normalized format your future detector/OCR system should output.
    """
    kind: str
    confidence: float = 1.0
    label: Optional[str] = None

    # One of these will usually be populated
    points: List[Tuple[float, float]] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None  # x, y, w, h
    center: Optional[Tuple[float, float]] = None

    # Optional semantics
    zone_type_hint: Optional[str] = None
    object_kind: Optional[str] = None
    is_obstacle: bool = False
    is_centerline: bool = False

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRTextDetection:
    text: str
    x: float
    y: float
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageAnalysisInput:
    """
    Bridge format between image understanding and your geometry engine.

    You can populate this from:
    - manual annotation UI
    - OCR output
    - CV detections
    - a screenshot parser
    - future vision models
    """
    detections: List[ImageDetection] = field(default_factory=list)
    texts: List[OCRTextDetection] = field(default_factory=list)
    image_width: Optional[float] = None
    image_height: Optional[float] = None
    source_name: Optional[str] = None
    source_type: str = "image"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageAnalysisResult:
    success: bool
    message: str = ""
    parsed_sketch: Optional[ParsedSketch] = None
    warnings: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


class ImageAnalysisEngine:
    """
    First-stage image analysis bridge.

    What it does now:
    - converts image detections into sketch-like primitives
    - routes them through SketchParser
    - produces zones, centerlines, objects, obstacles, and anchors

    What it does NOT do yet:
    - actual computer vision
    - OCR itself
    - raster processing
    - symbol recognition from raw pixels

    This is still extremely useful because it gives your future vision layer
    a stable output contract that plugs into the rest of the system.
    """

    REGION_KINDS = {
        "room", "building", "site", "parcel", "lot", "zone", "pad", "road_area",
        "parking", "corridor", "bridge_area", "restricted", "drainage_area",
    }

    STROKE_KINDS = {
        "line", "polyline", "route", "centerline", "alignment", "pipe", "wall_line",
        "beam_line", "grid_line", "road_centerline",
    }

    POINT_KINDS = {
        "point", "fixture", "equipment", "column", "beam", "manhole", "inlet",
        "drain", "pier", "abutment", "support", "anchor",
    }

    def analyze(self, analysis_input: ImageAnalysisInput) -> ImageAnalysisResult:
        sketch_input = self._to_sketch_input(analysis_input)
        parser = SketchParser()
        parsed = parser.parse(sketch_input)

        counts = {
            "detections": len(analysis_input.detections),
            "texts": len(analysis_input.texts),
            "zones": len(parsed.boundary_zones),
            "obstacles": len(parsed.obstacles),
            "objects": len(parsed.objects),
            "centerlines": len(parsed.centerlines),
            "anchors": len(parsed.anchors),
        }

        warnings = list(parsed.warnings)

        if not analysis_input.detections and not analysis_input.texts:
            warnings.append("No image detections or OCR text were provided.")

        return ImageAnalysisResult(
            success=True,
            message="Image analysis normalized into project-ready geometry.",
            parsed_sketch=parsed,
            warnings=warnings,
            counts=counts,
            meta={
                "source_name": analysis_input.source_name,
                "source_type": analysis_input.source_type,
                **analysis_input.meta,
            },
        )

    def apply_to_project(
        self,
        project: ProjectModel,
        analysis_input: ImageAnalysisInput,
        add_as_entities: bool = False,
    ) -> ImageAnalysisResult:
        result = self.analyze(analysis_input)
        if not result.success or result.parsed_sketch is None:
            return result

        parser = SketchParser()
        parser.apply_to_project(
            project=project,
            sketch=self._to_sketch_input(analysis_input),
            add_as_entities=add_as_entities,
        )

        return result

    def from_detection_dict(self, data: Dict[str, Any]) -> ImageAnalysisInput:
        detections = [
            ImageDetection(
                kind=item["kind"],
                confidence=float(item.get("confidence", 1.0)),
                label=item.get("label"),
                points=[tuple(pt) for pt in item.get("points", [])],
                bbox=tuple(item["bbox"]) if item.get("bbox") else None,
                center=tuple(item["center"]) if item.get("center") else None,
                zone_type_hint=item.get("zone_type_hint"),
                object_kind=item.get("object_kind"),
                is_obstacle=bool(item.get("is_obstacle", False)),
                is_centerline=bool(item.get("is_centerline", False)),
                meta=item.get("meta", {}),
            )
            for item in data.get("detections", [])
        ]

        texts = [
            OCRTextDetection(
                text=item["text"],
                x=float(item["x"]),
                y=float(item["y"]),
                confidence=float(item.get("confidence", 1.0)),
                meta=item.get("meta", {}),
            )
            for item in data.get("texts", [])
        ]

        return ImageAnalysisInput(
            detections=detections,
            texts=texts,
            image_width=data.get("image_width"),
            image_height=data.get("image_height"),
            source_name=data.get("source_name"),
            source_type=data.get("source_type", "image"),
            meta=data.get("meta", {}),
        )

    def _to_sketch_input(self, analysis_input: ImageAnalysisInput) -> SketchInput:
        sketch = SketchInput(meta={
            "source_name": analysis_input.source_name,
            "source_type": analysis_input.source_type,
            "image_width": analysis_input.image_width,
            "image_height": analysis_input.image_height,
            **analysis_input.meta,
        })

        for det in analysis_input.detections:
            kind_l = det.kind.strip().lower()

            if self._is_region_detection(kind_l, det):
                region = self._region_from_detection(det)
                if region is not None:
                    sketch.regions.append(region)
                continue

            if self._is_stroke_detection(kind_l, det):
                stroke = self._stroke_from_detection(det)
                if stroke is not None:
                    sketch.strokes.append(stroke)
                continue

            point = self._point_from_detection(det)
            if point is not None:
                sketch.points.append(point)

        for txt in analysis_input.texts:
            sketch.texts.append(
                SketchText(
                    text=txt.text,
                    x=txt.x,
                    y=txt.y,
                    kind="ocr_text",
                    meta={"confidence": txt.confidence, **txt.meta},
                )
            )

        return sketch

    def _is_region_detection(self, kind_l: str, det: ImageDetection) -> bool:
        if kind_l in self.REGION_KINDS:
            return True
        if det.zone_type_hint is not None:
            return True
        return bool(det.bbox and len(det.points) != 2 and len(det.points) != 1)

    def _is_stroke_detection(self, kind_l: str, det: ImageDetection) -> bool:
        if kind_l in self.STROKE_KINDS:
            return True
        if det.is_centerline:
            return True
        return len(det.points) >= 2 and det.bbox is None and det.center is None

    def _region_from_detection(self, det: ImageDetection) -> Optional[SketchRegion]:
        if det.points and len(det.points) >= 3:
            pts = [
                SketchPoint(x=float(x), y=float(y))
                for x, y in det.points
            ]
        elif det.bbox:
            x, y, w, h = det.bbox
            pts = [
                SketchPoint(x=x, y=y),
                SketchPoint(x=x + w, y=y),
                SketchPoint(x=x + w, y=y + h),
                SketchPoint(x=x, y=y + h),
            ]
        else:
            return None

        return SketchRegion(
            points=pts,
            label=det.label,
            kind=det.kind,
            zone_type_hint=det.zone_type_hint,
            meta={
                "confidence": det.confidence,
                "is_obstacle": det.is_obstacle,
                "object_kind": det.object_kind,
                **det.meta,
            },
        )

    def _stroke_from_detection(self, det: ImageDetection) -> Optional[SketchStroke]:
        if det.points and len(det.points) >= 2:
            pts = [SketchPoint(x=float(x), y=float(y)) for x, y in det.points]
            return SketchStroke(
                points=pts,
                label=det.label,
                kind=det.kind,
                closed_hint=bool(det.meta.get("closed_hint", False)),
                meta={
                    "confidence": det.confidence,
                    "is_centerline": det.is_centerline,
                    "is_obstacle": det.is_obstacle,
                    "object_kind": det.object_kind,
                    **det.meta,
                },
            )

        if det.bbox:
            x, y, w, h = det.bbox
            pts = [
                SketchPoint(x=x, y=y),
                SketchPoint(x=x + w, y=y + h),
            ]
            return SketchStroke(
                points=pts,
                label=det.label,
                kind=det.kind,
                meta={
                    "confidence": det.confidence,
                    "is_centerline": det.is_centerline,
                    "is_obstacle": det.is_obstacle,
                    "object_kind": det.object_kind,
                    **det.meta,
                },
            )

        return None

    def _point_from_detection(self, det: ImageDetection) -> Optional[SketchPoint]:
        if det.center:
            x, y = det.center
            return SketchPoint(
                x=float(x),
                y=float(y),
                label=det.label,
                kind=det.object_kind or det.kind,
                meta={"confidence": det.confidence, **det.meta},
            )

        if det.points and len(det.points) == 1:
            x, y = det.points[0]
            return SketchPoint(
                x=float(x),
                y=float(y),
                label=det.label,
                kind=det.object_kind or det.kind,
                meta={"confidence": det.confidence, **det.meta},
            )

        if det.bbox:
            x, y, w, h = det.bbox
            cx = x + w / 2.0
            cy = y + h / 2.0
            return SketchPoint(
                x=float(cx),
                y=float(cy),
                label=det.label,
                kind=det.object_kind or det.kind,
                meta={"confidence": det.confidence, "bbox": det.bbox, **det.meta},
            )

        return None


def analyze_image_input(analysis_input: ImageAnalysisInput) -> ImageAnalysisResult:
    return ImageAnalysisEngine().analyze(analysis_input)


def analyze_image_dict(data: Dict[str, Any]) -> ImageAnalysisResult:
    engine = ImageAnalysisEngine()
    analysis_input = engine.from_detection_dict(data)
    return engine.analyze(analysis_input)