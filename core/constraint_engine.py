from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.geometry_core import (
    BoundingBox2D,
    EngineeringObject,
    IssueSeverity,
    Point2D,
    ProjectModel,
    ReviewIssue,
    Zone,
    ZoneType,
)


class ConstraintSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ConstraintIssue:
    code: str
    severity: str
    message: str
    data: Dict[str, Any]


@dataclass
class ConstraintResult:
    passed: bool
    severity: ConstraintSeverity = ConstraintSeverity.ERROR
    message: str = ""
    rule_name: Optional[str] = None
    object_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_review_issue(self) -> ReviewIssue:
        severity_map = {
            ConstraintSeverity.INFO: IssueSeverity.INFO,
            ConstraintSeverity.WARNING: IssueSeverity.WARNING,
            ConstraintSeverity.ERROR: IssueSeverity.ERROR,
        }
        return ReviewIssue(
            severity=severity_map[self.severity],
            message=self.message,
            object_id=self.object_id,
            rule_name=self.rule_name,
            meta=dict(self.meta),
        )


@dataclass
class ConstraintContext:
    project: ProjectModel
    objects: List[EngineeringObject] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseConstraint:
    name: str = "base_constraint"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        raise NotImplementedError


@dataclass
class MinObjectSpacingConstraint(BaseConstraint):
    min_spacing: float
    object_kinds: List[str] = field(default_factory=list)
    name: str = "min_object_spacing"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        objects = context.objects or list(context.project.objects.values())

        if self.object_kinds:
            objects = [o for o in objects if o.kind in self.object_kinds]

        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                a = objects[i]
                b = objects[j]
                dist = a.anchor.as_2d().distance_to(b.anchor.as_2d())
                if dist < self.min_spacing:
                    results.append(
                        ConstraintResult(
                            passed=False,
                            severity=ConstraintSeverity.WARNING,
                            message=f"Objects '{a.name or a.id}' and '{b.name or b.id}' are closer than {self.min_spacing}.",
                            rule_name=self.name,
                            object_id=a.id,
                            meta={
                                "other_object_id": b.id,
                                "distance": dist,
                                "min_spacing": self.min_spacing,
                            },
                        )
                    )
        return results


@dataclass
class ZoneContainmentConstraint(BaseConstraint):
    zone_ids: List[str] = field(default_factory=list)
    object_kinds: List[str] = field(default_factory=list)
    name: str = "zone_containment"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        zones = context.zones or list(context.project.zones.values())
        objects = context.objects or list(context.project.objects.values())

        if self.zone_ids:
            zone_lookup = {z.id: z for z in zones}
            zones = [zone_lookup[zid] for zid in self.zone_ids if zid in zone_lookup]

        if self.object_kinds:
            objects = [o for o in objects if o.kind in self.object_kinds]

        for obj in objects:
            pt = obj.anchor.as_2d()
            inside_any = any(zone.contains_point(pt) for zone in zones)
            if not inside_any:
                results.append(
                    ConstraintResult(
                        passed=False,
                        severity=ConstraintSeverity.ERROR,
                        message=f"Object '{obj.name or obj.id}' is outside required containment zones.",
                        rule_name=self.name,
                        object_id=obj.id,
                    )
                )
        return results


@dataclass
class MaxSpanConstraint(BaseConstraint):
    max_length: float
    object_kind: str = "beam"
    name: str = "max_span"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        objects = context.objects or list(context.project.objects.values())
        targets = [o for o in objects if o.kind == self.object_kind]

        for obj in targets:
            start = obj.properties.get("start")
            end = obj.properties.get("end")
            if not start or not end:
                continue

            try:
                dx = float(end[0]) - float(start[0])
                dy = float(end[1]) - float(start[1])
            except (TypeError, ValueError, IndexError):
                continue

            length = (dx * dx + dy * dy) ** 0.5

            if length > self.max_length:
                results.append(
                    ConstraintResult(
                        passed=False,
                        severity=ConstraintSeverity.WARNING,
                        message=f"{self.object_kind.title()} '{obj.name or obj.id}' exceeds max length {self.max_length}.",
                        rule_name=self.name,
                        object_id=obj.id,
                        meta={"length": length, "max_length": self.max_length},
                    )
                )
        return results


@dataclass
class ObjectOverlapConstraint(BaseConstraint):
    object_kinds: List[str] = field(default_factory=list)
    ignore_same_name_prefix: bool = False
    severity: ConstraintSeverity = ConstraintSeverity.WARNING
    name: str = "object_overlap"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        objects = context.objects or list(context.project.objects.values())

        if self.object_kinds:
            objects = [o for o in objects if o.kind in self.object_kinds]

        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                a = objects[i]
                b = objects[j]

                if self.ignore_same_name_prefix:
                    an = str(a.name or "")
                    bn = str(b.name or "")
                    if an and bn and (an.startswith(bn) or bn.startswith(an)):
                        continue

                abox = a.bbox()
                bbox = b.bbox()
                if abox is None or bbox is None:
                    continue

                if abox.intersects(bbox):
                    results.append(
                        ConstraintResult(
                            passed=False,
                            severity=self.severity,
                            message=f"Objects '{a.name or a.id}' and '{b.name or b.id}' overlap.",
                            rule_name=self.name,
                            object_id=a.id,
                            meta={"other_object_id": b.id},
                        )
                    )

        return results


@dataclass
class ZoneOverlapConstraint(BaseConstraint):
    zone_types: List[ZoneType] = field(default_factory=list)
    severity: ConstraintSeverity = ConstraintSeverity.WARNING
    name: str = "zone_overlap"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        zones = context.zones or list(context.project.zones.values())

        if self.zone_types:
            zones = [z for z in zones if z.zone_type in self.zone_types]

        for i in range(len(zones)):
            for j in range(i + 1, len(zones)):
                a = zones[i]
                b = zones[j]

                if a.bbox.intersects(b.bbox):
                    results.append(
                        ConstraintResult(
                            passed=False,
                            severity=self.severity,
                            message=f"Zones '{a.name or a.id}' and '{b.name or b.id}' overlap.",
                            rule_name=self.name,
                            object_id=None,
                            meta={"zone_a_id": a.id, "zone_b_id": b.id},
                        )
                    )

        return results


@dataclass
class DuplicateObjectAnchorConstraint(BaseConstraint):
    tolerance: float = 0.01
    object_kinds: List[str] = field(default_factory=list)
    severity: ConstraintSeverity = ConstraintSeverity.INFO
    name: str = "duplicate_object_anchor"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results: List[ConstraintResult] = []
        objects = context.objects or list(context.project.objects.values())

        if self.object_kinds:
            objects = [o for o in objects if o.kind in self.object_kinds]

        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                a = objects[i]
                b = objects[j]
                dist = a.anchor.as_2d().distance_to(b.anchor.as_2d())
                if dist <= self.tolerance:
                    results.append(
                        ConstraintResult(
                            passed=False,
                            severity=self.severity,
                            message=f"Objects '{a.name or a.id}' and '{b.name or b.id}' appear duplicated or nearly duplicated.",
                            rule_name=self.name,
                            object_id=a.id,
                            meta={
                                "other_object_id": b.id,
                                "distance": dist,
                                "tolerance": self.tolerance,
                            },
                        )
                    )
        return results


@dataclass
class CustomConstraint(BaseConstraint):
    evaluator: Callable[[ConstraintContext], List[ConstraintResult]]
    name: str = "custom_constraint"

    def evaluate(self, context: ConstraintContext) -> List[ConstraintResult]:
        results = self.evaluator(context)
        for r in results:
            if not r.rule_name:
                r.rule_name = self.name
        return results


@dataclass
class ConstraintEvaluationSummary:
    passed: bool
    total_results: int
    failed_results: int
    info_count: int
    warning_count: int
    error_count: int
    results: List[ConstraintResult] = field(default_factory=list)


class ConstraintEngine:
    def evaluate(
        self,
        project: ProjectModel,
        constraints: Sequence[BaseConstraint],
        objects: Optional[List[EngineeringObject]] = None,
        zones: Optional[List[Zone]] = None,
        persist_to_project: bool = False,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> ConstraintEvaluationSummary:
        context = ConstraintContext(
            project=project,
            objects=objects or [],
            zones=zones or [],
            meta=extra_meta or {},
        )

        all_results: List[ConstraintResult] = []
        for constraint in constraints:
            all_results.extend(constraint.evaluate(context))

        if persist_to_project:
            for result in all_results:
                if not result.passed:
                    project.add_issue(result.to_review_issue())

        failed = [r for r in all_results if not r.passed]
        info_count = sum(1 for r in failed if r.severity == ConstraintSeverity.INFO)
        warning_count = sum(1 for r in failed if r.severity == ConstraintSeverity.WARNING)
        error_count = sum(1 for r in failed if r.severity == ConstraintSeverity.ERROR)

        return ConstraintEvaluationSummary(
            passed=len(failed) == 0,
            total_results=len(all_results),
            failed_results=len(failed),
            info_count=info_count,
            warning_count=warning_count,
            error_count=error_count,
            results=all_results,
        )


def rects_overlap(a: Dict[str, float], b: Dict[str, float]) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"]
        or b["x"] + b["w"] <= a["x"]
        or a["y"] + a["h"] <= b["y"]
        or b["y"] + b["h"] <= a["y"]
    )


def point_in_rect(px: float, py: float, rect: Dict[str, float]) -> bool:
    return (
        rect["x"] <= px <= rect["x"] + rect["w"]
        and rect["y"] <= py <= rect["y"] + rect["h"]
    )


def _make_issue(
    code: str,
    severity: str,
    message: str,
    data: Dict[str, Any] | None = None,
) -> ConstraintIssue:
    return ConstraintIssue(
        code=code,
        severity=severity,
        message=message,
        data={} if data is None else data,
    )


def validate_site_layout(layout: Dict[str, Any]) -> List[ConstraintIssue]:
    issues: List[ConstraintIssue] = []

    lot = layout.get("lot")
    setback = float(layout.get("setback", 0))
    building = layout.get("building")
    parking = layout.get("parking")
    driveway = layout.get("driveway")

    if not lot or not building:
        issues.append(
            _make_issue(
                code="MISSING_CORE_LAYOUT",
                severity="error",
                message="Lot or building missing from layout.",
            )
        )
        return issues

    buildable = {
        "x": lot["x"] + setback,
        "y": lot["y"] + setback,
        "w": lot["w"] - 2 * setback,
        "h": lot["h"] - 2 * setback,
    }

    if buildable["w"] <= 0 or buildable["h"] <= 0:
        issues.append(
            _make_issue(
                code="INVALID_BUILDABLE_AREA",
                severity="error",
                message="Setback leaves no valid buildable area.",
                data={"lot": lot, "setback": setback, "buildable": buildable},
            )
        )
        return issues

    building_inside_buildable = (
        buildable["x"] <= building["x"]
        and buildable["y"] <= building["y"]
        and building["x"] + building["w"] <= buildable["x"] + buildable["w"]
        and building["y"] + building["h"] <= buildable["y"] + buildable["h"]
    )

    if not building_inside_buildable:
        issues.append(
            _make_issue(
                code="BUILDING_OUTSIDE_SETBACK",
                severity="error",
                message="Building is outside setback/buildable area.",
                data={"buildable": buildable, "building": building},
            )
        )

    building_inside_lot = (
        lot["x"] <= building["x"]
        and lot["y"] <= building["y"]
        and building["x"] + building["w"] <= lot["x"] + lot["w"]
        and building["y"] + building["h"] <= lot["y"] + lot["h"]
    )

    if not building_inside_lot:
        issues.append(
            _make_issue(
                code="BUILDING_OUTSIDE_LOT",
                severity="error",
                message="Building extends outside lot.",
                data={"lot": lot, "building": building},
            )
        )

    if parking and rects_overlap(building, parking):
        issues.append(
            _make_issue(
                code="PARKING_OVERLAPS_BUILDING",
                severity="error",
                message="Parking overlaps building footprint.",
                data={"building": building, "parking": parking},
            )
        )

    if parking:
        parking_inside_lot = (
            lot["x"] <= parking["x"]
            and lot["y"] <= parking["y"]
            and parking["x"] + parking["w"] <= lot["x"] + lot["w"]
            and parking["y"] + parking["h"] <= lot["y"] + lot["h"]
        )

        if not parking_inside_lot:
            issues.append(
                _make_issue(
                    code="PARKING_OUTSIDE_LOT",
                    severity="error",
                    message="Parking extends outside lot.",
                    data={"lot": lot, "parking": parking},
                )
            )

    if driveway:
        driveway_inside_lot = (
            lot["x"] <= driveway["x"]
            and lot["y"] <= driveway["y"]
            and driveway["x"] + driveway["w"] <= lot["x"] + lot["w"]
            and driveway["y"] + driveway["h"] <= lot["y"] + lot["h"]
        )

        if not driveway_inside_lot:
            issues.append(
                _make_issue(
                    code="DRIVEWAY_OUTSIDE_LOT",
                    severity="warning",
                    message="Driveway extends outside lot.",
                    data={"lot": lot, "driveway": driveway},
                )
            )

    if parking and driveway and not rects_overlap(parking, driveway):
        issues.append(
            _make_issue(
                code="DRIVEWAY_NOT_CONNECTED_TO_PARKING",
                severity="warning",
                message="Driveway does not appear to connect to parking.",
                data={"parking": parking, "driveway": driveway},
            )
        )

    return issues


def validate_expanded_site_plan(parsed: Dict[str, Any]) -> List[ConstraintIssue]:
    issues: List[ConstraintIssue] = []

    lot = parsed.get("lot")
    buildings = parsed.get("buildings") or []
    parking_areas = parsed.get("parking_areas") or []
    drive_aisles = parsed.get("drive_aisles") or []
    ponds = parsed.get("ponds") or []
    drainage_structures = parsed.get("drainage_structures") or []

    if not lot:
        issues.append(
            _make_issue(
                code="MISSING_LOT",
                severity="error",
                message="Expanded site plan is missing lot geometry.",
            )
        )
        return issues

    lot_rect = {
        "x": float(lot["x"]),
        "y": float(lot["y"]),
        "w": float(lot["w"]),
        "h": float(lot["h"]),
    }

    for b in buildings:
        rect = {
            "x": float(b.get("x", 0.0)),
            "y": float(b.get("y", 0.0)),
            "w": float(b.get("w", 0.0)),
            "h": float(b.get("d", 0.0)),
        }
        if rect["w"] <= 0 or rect["h"] <= 0:
            issues.append(
                _make_issue(
                    code="INVALID_BUILDING_SIZE",
                    severity="error",
                    message=f"Building '{b.get('label', 'UNKNOWN')}' has invalid dimensions.",
                    data={"building": b},
                )
            )
            continue

        inside = (
            lot_rect["x"] <= rect["x"]
            and lot_rect["y"] <= rect["y"]
            and rect["x"] + rect["w"] <= lot_rect["x"] + lot_rect["w"]
            and rect["y"] + rect["h"] <= lot_rect["y"] + lot_rect["h"]
        )
        if not inside:
            issues.append(
                _make_issue(
                    code="BUILDING_OUTSIDE_SITE",
                    severity="error",
                    message=f"Building '{b.get('label', 'UNKNOWN')}' extends outside the site.",
                    data={"building": b},
                )
            )

    for i in range(len(buildings)):
        ai = {
            "x": float(buildings[i].get("x", 0.0)),
            "y": float(buildings[i].get("y", 0.0)),
            "w": float(buildings[i].get("w", 0.0)),
            "h": float(buildings[i].get("d", 0.0)),
        }
        for j in range(i + 1, len(buildings)):
            bj = {
                "x": float(buildings[j].get("x", 0.0)),
                "y": float(buildings[j].get("y", 0.0)),
                "w": float(buildings[j].get("w", 0.0)),
                "h": float(buildings[j].get("d", 0.0)),
            }
            if rects_overlap(ai, bj):
                issues.append(
                    _make_issue(
                        code="BUILDING_OVERLAP",
                        severity="error",
                        message=f"Buildings '{buildings[i].get('label', i)}' and '{buildings[j].get('label', j)}' overlap.",
                    )
                )

    for p in parking_areas:
        rect = {
            "x": float(p.get("x", 0.0)),
            "y": float(p.get("y", 0.0)),
            "w": float(p.get("w", 0.0)),
            "h": float(p.get("h", 0.0)),
        }
        inside = (
            lot_rect["x"] <= rect["x"]
            and lot_rect["y"] <= rect["y"]
            and rect["x"] + rect["w"] <= lot_rect["x"] + lot_rect["w"]
            and rect["y"] + rect["h"] <= lot_rect["y"] + lot_rect["h"]
        )
        if not inside:
            issues.append(
                _make_issue(
                    code="PARKING_OUTSIDE_SITE",
                    severity="error",
                    message=f"Parking area '{p.get('label', 'UNKNOWN')}' extends outside the site.",
                    data={"parking": p},
                )
            )

    if buildings and not parking_areas:
        issues.append(
            _make_issue(
                code="NO_PARKING_AREAS",
                severity="warning",
                message="Buildings exist but no parking areas were generated.",
            )
        )

    if parking_areas and not drive_aisles:
        issues.append(
            _make_issue(
                code="NO_DRIVE_AISLES",
                severity="warning",
                message="Parking exists but no drive aisles/access drives were generated.",
            )
        )

    if drainage_structures and not ponds:
        issues.append(
            _make_issue(
                code="DRAINAGE_WITHOUT_OUTFALL",
                severity="warning",
                message="Drainage structures exist but no ponds/outfall targets were generated.",
            )
        )

    return issues


def validate_drainage_summary(
    basins_count: int,
    inlets_count: int,
    ponds_count: int,
    warnings_count: int,
) -> List[ConstraintIssue]:
    issues: List[ConstraintIssue] = []

    if ponds_count == 0:
        issues.append(
            _make_issue(
                code="NO_PONDS",
                severity="error",
                message="No detention pond targets defined.",
            )
        )

    if basins_count == 0:
        issues.append(
            _make_issue(
                code="NO_BASINS",
                severity="warning",
                message="No drainage basins identified.",
            )
        )

    if inlets_count == 0:
        issues.append(
            _make_issue(
                code="NO_INLETS",
                severity="warning",
                message="No inlets were placed.",
            )
        )

    if warnings_count > 20:
        issues.append(
            _make_issue(
                code="TOO_MANY_WARNINGS",
                severity="warning",
                message="The plan generated an unusually high number of warnings.",
                data={"warnings_count": warnings_count},
            )
        )

    if inlets_count > 0 and ponds_count > 0 and basins_count == 0:
        issues.append(
            _make_issue(
                code="NO_BASIN_LABELS_FOR_DRAINAGE",
                severity="info",
                message="Drainage objects exist, but basin labeling/segmentation appears missing.",
            )
        )

    return issues


def evaluate_constraints(
    project: ProjectModel,
    constraints: Sequence[BaseConstraint],
    objects: Optional[List[EngineeringObject]] = None,
    zones: Optional[List[Zone]] = None,
    persist_to_project: bool = False,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> ConstraintEvaluationSummary:
    return ConstraintEngine().evaluate(
        project=project,
        constraints=constraints,
        objects=objects,
        zones=zones,
        persist_to_project=persist_to_project,
        extra_meta=extra_meta,
    )