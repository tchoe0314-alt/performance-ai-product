from __future__ import annotations

"""
sanitary_engine.py (MERGED TRUE MAX VERSION)

Purpose
-------
Network-aware sanitary drainage sizing, invert assignment, routing-hook, and
reporting engine for the AI civil engineering platform.

This file preserves the strong original sanitary sizing base and expands it with:
- network topology validation
- upstream/downstream hierarchy handling
- loop detection
- relative invert assignment (A-mode: realistic, grading-ready later)
- geometry/routing hooks
- manhole / cleanout / junction logic
- conflict-ready metadata
- explain/report/fix/optimize hooks

Design intent
-------------
- Keep the original fixture / segment / request / result model style
- Preserve DFU sizing capability
- Add realistic sanitary-network behavior now
- Keep architecture ready for future grading-surface integration later
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import math


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SanitaryFixture:
    name: str
    fixture_type: str
    drainage_fu: float
    discharge_gpm: float = 0.0
    requires_grease_waste: bool = False
    branch_length: float = 0.0
    elevation_ft: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SanitaryPipeSegment:
    name: str
    segment_type: str  # branch | lateral | main | trunk | building_drain | grease | site_connection | outfall
    connected_fixture_names: List[str] = field(default_factory=list)
    connected_segment_names: List[str] = field(default_factory=list)  # downstream children in original file usage
    upstream_segment_names: List[str] = field(default_factory=list)   # optional explicit upstream references
    length: float = 0.0
    slope: float = 0.0
    min_slope: float = 0.02
    max_slope: Optional[float] = None
    min_size_in: float = 2.0

    assigned_dfu: float = 0.0
    assigned_flow_gpm: float = 0.0
    assigned_size_in: float = 0.0
    capacity_gpm: float = 0.0
    capacity_cfs: float = 0.0
    velocity_fps: float = 0.0
    capacity_ratio: float = 0.0
    flow_depth_ratio: float = 0.0
    mannings_n: float = 0.013

    requires_cleanout: bool = False
    cleanout_spacing_ft: float = 100.0
    cleanout_count: int = 0

    invert_drop: float = 0.0
    upstream_invert_ft: Optional[float] = None
    downstream_invert_ft: Optional[float] = None
    rim_elev_ft: Optional[float] = None

    geometry_points: List[Tuple[float, float]] = field(default_factory=list)
    route_name: Optional[str] = None
    route_system_type: str = "sanitary"

    has_manhole_upstream: bool = False
    has_manhole_downstream: bool = False
    manhole_count: int = 0
    junction_count: int = 0

    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SanitarySizingRequest:
    fixtures: List[SanitaryFixture] = field(default_factory=list)
    segments: List[SanitaryPipeSegment] = field(default_factory=list)
    conservative: bool = True
    auto_assign_slopes: bool = True
    grease_interceptor_required: bool = False

    default_branch_slope: float = 0.02
    default_lateral_slope: float = 0.02
    default_main_slope: float = 0.01
    default_trunk_slope: float = 0.005
    default_building_drain_slope: float = 0.01
    default_site_connection_slope: float = 0.008

    # A-mode relative invert system
    start_reference_invert_ft: float = 100.0
    auto_assign_inverts: bool = True
    assign_relative_rims: bool = True

    # network logic
    validate_network_topology: bool = True
    auto_promote_hierarchy: bool = True
    max_manhole_spacing_ft: float = 300.0
    max_cleanout_spacing_ft: float = 100.0

    # routing / geometry hooks
    use_geometry_length_if_available: bool = True
    geometry_length_factor: float = 1.0

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SanitarySystemSummary:
    segment_count: int = 0
    fixture_count: int = 0
    total_dfu: float = 0.0
    total_flow_gpm: float = 0.0
    total_length_ft: float = 0.0
    max_depth_drop_ft: float = 0.0
    cleanout_count: int = 0
    manhole_count: int = 0
    junction_count: int = 0
    grease_fixture_count: int = 0
    issue_count: int = 0
    by_segment_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_count": self.segment_count,
            "fixture_count": self.fixture_count,
            "total_dfu": round(self.total_dfu, 3),
            "total_flow_gpm": round(self.total_flow_gpm, 3),
            "total_length_ft": round(self.total_length_ft, 3),
            "max_depth_drop_ft": round(self.max_depth_drop_ft, 3),
            "cleanout_count": self.cleanout_count,
            "manhole_count": self.manhole_count,
            "junction_count": self.junction_count,
            "grease_fixture_count": self.grease_fixture_count,
            "issue_count": self.issue_count,
            "by_segment_type": dict(self.by_segment_type),
        }


@dataclass
class SanitarySizingResult:
    success: bool
    message: str = ""
    segments: List[SanitaryPipeSegment] = field(default_factory=list)
    total_dfu: float = 0.0
    total_flow_gpm: float = 0.0
    grease_fixture_count: int = 0
    warnings: List[str] = field(default_factory=list)
    summary: SanitarySystemSummary = field(default_factory=SanitarySystemSummary)
    explain: Dict[str, Any] = field(default_factory=dict)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ENGINE
# =============================================================================

class SanitaryEngine:
    """
    Expanded sanitary drainage engine.

    Strong original capabilities preserved:
    - DFU aggregation
    - basic pipe sizing
    - slope defaults
    - cleanout logic
    - grease fixture awareness

    New max capabilities:
    - network topology validation
    - loop detection
    - hierarchy classification
    - relative invert assignment
    - manhole/junction logic
    - geometry-aware lengths
    - planner/intelligence-ready summaries
    """

    DEFAULT_DFU_TABLE = {
        "lav": 1.0,
        "sink": 2.0,
        "kitchen_sink": 2.0,
        "service_sink": 3.0,
        "wc": 4.0,
        "wc_public": 6.0,
        "urinal": 4.0,
        "shower": 2.0,
        "floor_drain": 2.0,
        "mop_sink": 3.0,
        "dishwasher": 2.0,
        "bar_sink": 2.0,
        "3_comp_sink": 4.0,
        "grease_fixture": 4.0,
    }

    CAPACITY_TABLE = [
        {"size_in": 2.0, "max_dfu": 8.0, "min_slope": 0.02},
        {"size_in": 2.5, "max_dfu": 21.0, "min_slope": 0.02},
        {"size_in": 3.0, "max_dfu": 35.0, "min_slope": 0.02},
        {"size_in": 4.0, "max_dfu": 180.0, "min_slope": 0.01},
        {"size_in": 5.0, "max_dfu": 390.0, "min_slope": 0.01},
        {"size_in": 6.0, "max_dfu": 620.0, "min_slope": 0.01},
        {"size_in": 8.0, "max_dfu": 1400.0, "min_slope": 0.005},
    ]

    TYPE_SLOPE_MAP = {
        "branch": "default_branch_slope",
        "lateral": "default_lateral_slope",
        "main": "default_main_slope",
        "trunk": "default_trunk_slope",
        "building_drain": "default_building_drain_slope",
        "site_connection": "default_site_connection_slope",
        "grease": "default_main_slope",
        "outfall": "default_trunk_slope",
    }

    def size(self, request: SanitarySizingRequest) -> SanitarySizingResult:
        if not request.segments:
            return SanitarySizingResult(False, message="No sanitary pipe segments provided.")

        fixtures = self._normalize_fixtures(request.fixtures)
        segments = [self._clone_segment(seg, request) for seg in request.segments]

        fixture_lookup = {fx.name: fx for fx in fixtures}
        segment_lookup = {seg.name: seg for seg in segments}

        warnings: List[str] = []
        grease_fixture_count = sum(1 for fx in fixtures if fx.requires_grease_waste)

        if request.validate_network_topology:
            warnings.extend(self._validate_unique_segment_names(segments))
            warnings.extend(self._synchronize_network_references(segments, segment_lookup))
            warnings.extend(self._detect_network_loops(segments, segment_lookup))

        if request.auto_promote_hierarchy:
            self._auto_promote_hierarchy(segments, segment_lookup)

        self._apply_geometry_lengths(segments, request)

        # local fixture assignment
        for seg in segments:
            local_dfu = 0.0
            local_flow = 0.0
            for fx_name in seg.connected_fixture_names:
                fx = fixture_lookup.get(fx_name)
                if fx is None:
                    seg.warnings.append(f"Missing fixture '{fx_name}'.")
                    continue
                local_dfu += fx.drainage_fu
                local_flow += max(fx.discharge_gpm, self._dfu_to_gpm(fx.drainage_fu, request.conservative))
                if fx.requires_grease_waste and seg.segment_type not in {"grease"}:
                    seg.warnings.append(f"Grease fixture '{fx.name}' connected to non-grease segment.")
            seg.assigned_dfu = round(local_dfu, 3)
            seg.assigned_flow_gpm = round(local_flow, 3)

        # propagate network loads
        self._propagate_network_demands(segments, segment_lookup)

        # assign sizes/slopes
        for seg in segments:
            size_row = self._pick_pipe_size(seg.assigned_dfu, seg.min_size_in)
            seg.assigned_size_in = size_row["size_in"]

            if request.auto_assign_slopes and seg.slope <= 0.0:
                seg.slope = self._default_slope_for_segment(seg, request, size_row["min_slope"])

            if seg.slope < max(seg.min_slope, size_row["min_slope"]):
                seg.warnings.append("Segment slope is below recommended minimum for assigned size.")
            if seg.max_slope is not None and seg.slope > seg.max_slope:
                seg.warnings.append("Segment slope exceeds maximum allowed slope.")
            if seg.assigned_dfu > size_row["max_dfu"]:
                seg.warnings.append("Assigned DFU exceeds simplified pipe capacity table.")

            seg.invert_drop = round(seg.length * seg.slope, 4)
            self._assign_manning_capacity(seg)
            if seg.capacity_ratio > 1.0:
                seg.warnings.append("Assigned sanitary flow exceeds Manning full-flow capacity.")
            elif seg.capacity_ratio > 0.8:
                seg.warnings.append("Assigned sanitary flow is above 80 percent of Manning full-flow capacity.")
            if 0.0 < seg.velocity_fps < 2.0:
                seg.warnings.append("Sanitary velocity is below preferred self-cleansing velocity.")
            if seg.velocity_fps > 10.0:
                seg.warnings.append("Sanitary velocity exceeds preferred maximum velocity.")

            seg.requires_cleanout = self._requires_cleanout(seg)
            seg.cleanout_spacing_ft = max(1.0, request.max_cleanout_spacing_ft if seg.cleanout_spacing_ft <= 0 else seg.cleanout_spacing_ft)
            if seg.requires_cleanout:
                seg.cleanout_count = self._estimate_cleanout_count(seg.length, seg.cleanout_spacing_ft)

        # assign relative invert system
        if request.auto_assign_inverts:
            warnings.extend(self._assign_relative_inverts(segments, segment_lookup, request))

        # manhole / junction logic
        self._assign_manhole_and_junction_logic(segments, segment_lookup, request)

        # collect warnings
        for seg in segments:
            warnings.extend(seg.warnings)

        if request.grease_interceptor_required and grease_fixture_count == 0:
            warnings.append("Grease interceptor requested but no grease fixtures were identified.")
        if grease_fixture_count > 0 and not request.grease_interceptor_required:
            warnings.append("Grease-producing fixtures found; grease interceptor logic may be required.")
        if not any(seg.assigned_dfu > 0.0 for seg in segments):
            warnings.append("No effective sanitary fixture demand was assigned.")

        total_dfu = max((seg.assigned_dfu for seg in segments), default=0.0)
        total_flow = max((seg.assigned_flow_gpm for seg in segments), default=0.0)

        summary = self._build_summary(segments, fixtures, grease_fixture_count, warnings)
        explain = self._build_explain_payload(segments, request, summary)
        optimize_hooks = self._build_optimize_hooks(segments, summary)
        conflict_hooks = self._build_conflict_hooks(segments)

        return SanitarySizingResult(
            success=True,
            message="Sanitary system sized.",
            segments=segments,
            total_dfu=round(total_dfu, 3),
            total_flow_gpm=round(total_flow, 3),
            grease_fixture_count=grease_fixture_count,
            warnings=sorted(set(warnings)),
            summary=summary,
            explain=explain,
            optimize_hooks=optimize_hooks,
            conflict_hooks=conflict_hooks,
        )

    # =========================================================================
    # NORMALIZATION / BASIC HELPERS
    # =========================================================================

    def _normalize_fixtures(self, fixtures: Sequence[SanitaryFixture]) -> List[SanitaryFixture]:
        normalized: List[SanitaryFixture] = []
        for fx in fixtures:
            dfu = fx.drainage_fu
            if dfu <= 0.0:
                dfu = self.DEFAULT_DFU_TABLE.get(fx.fixture_type.strip().lower(), 2.0)
            normalized.append(
                SanitaryFixture(
                    name=fx.name,
                    fixture_type=fx.fixture_type,
                    drainage_fu=dfu,
                    discharge_gpm=fx.discharge_gpm,
                    requires_grease_waste=fx.requires_grease_waste,
                    branch_length=fx.branch_length,
                    elevation_ft=fx.elevation_ft,
                    meta=dict(fx.meta),
                )
            )
        return normalized

    def _clone_segment(self, seg: SanitaryPipeSegment, request: SanitarySizingRequest) -> SanitaryPipeSegment:
        return SanitaryPipeSegment(
            name=seg.name,
            segment_type=seg.segment_type,
            connected_fixture_names=list(seg.connected_fixture_names),
            connected_segment_names=list(seg.connected_segment_names),
            upstream_segment_names=list(seg.upstream_segment_names),
            length=seg.length,
            slope=seg.slope,
            min_slope=seg.min_slope,
            max_slope=seg.max_slope,
            min_size_in=seg.min_size_in,
            assigned_dfu=seg.assigned_dfu,
            assigned_flow_gpm=seg.assigned_flow_gpm,
            assigned_size_in=seg.assigned_size_in,
            capacity_gpm=seg.capacity_gpm,
            capacity_cfs=seg.capacity_cfs,
            velocity_fps=seg.velocity_fps,
            capacity_ratio=seg.capacity_ratio,
            flow_depth_ratio=seg.flow_depth_ratio,
            mannings_n=seg.mannings_n,
            requires_cleanout=seg.requires_cleanout,
            cleanout_spacing_ft=seg.cleanout_spacing_ft if seg.cleanout_spacing_ft > 0 else request.max_cleanout_spacing_ft,
            cleanout_count=seg.cleanout_count,
            invert_drop=seg.invert_drop,
            upstream_invert_ft=seg.upstream_invert_ft,
            downstream_invert_ft=seg.downstream_invert_ft,
            rim_elev_ft=seg.rim_elev_ft,
            geometry_points=list(seg.geometry_points),
            route_name=seg.route_name,
            route_system_type=seg.route_system_type,
            has_manhole_upstream=seg.has_manhole_upstream,
            has_manhole_downstream=seg.has_manhole_downstream,
            manhole_count=seg.manhole_count,
            junction_count=seg.junction_count,
            warnings=list(seg.warnings),
            meta=dict(seg.meta),
        )

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except Exception:
            return float(default)

    def _dfu_to_gpm(self, dfu: float, conservative: bool) -> float:
        if dfu <= 0.0:
            return 0.0
        if dfu <= 4:
            gpm = dfu * 2.0
        elif dfu <= 20:
            gpm = 8.0 + (dfu - 4.0) * 1.25
        elif dfu <= 100:
            gpm = 28.0 + (dfu - 20.0) * 0.75
        else:
            gpm = 88.0 + (dfu - 100.0) * 0.45
        if conservative:
            gpm *= 1.1
        return gpm

    # =========================================================================
    # NETWORK TOPOLOGY
    # =========================================================================

    def _validate_unique_segment_names(self, segments: Sequence[SanitaryPipeSegment]) -> List[str]:
        warnings: List[str] = []
        seen: Set[str] = set()
        for seg in segments:
            if seg.name in seen:
                warnings.append(f"Duplicate sanitary segment name '{seg.name}' detected.")
            seen.add(seg.name)
        return warnings

    def _synchronize_network_references(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
    ) -> List[str]:
        warnings: List[str] = []
        for seg in segments:
            for child_name in list(seg.connected_segment_names):
                child = segment_lookup.get(child_name)
                if child is None:
                    warnings.append(f"Segment '{seg.name}' references missing downstream segment '{child_name}'.")
                    continue
                if seg.name not in child.upstream_segment_names:
                    child.upstream_segment_names.append(seg.name)
        return warnings

    def _detect_network_loops(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
    ) -> List[str]:
        warnings: List[str] = []
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(name: str) -> None:
            if name in stack:
                warnings.append(f"Loop detected in sanitary network at segment '{name}'.")
                return
            if name in visited:
                return
            visited.add(name)
            stack.add(name)
            seg = segment_lookup.get(name)
            if seg is not None:
                for child in seg.connected_segment_names:
                    if child in segment_lookup:
                        dfs(child)
            stack.remove(name)

        for seg in segments:
            dfs(seg.name)
        return warnings

    def _auto_promote_hierarchy(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
    ) -> None:
        for seg in segments:
            downstream_count = len([x for x in seg.connected_segment_names if x in segment_lookup])
            upstream_count = len([x for x in seg.upstream_segment_names if x in segment_lookup])
            if seg.segment_type == "branch" and downstream_count >= 2:
                seg.segment_type = "main"
            elif seg.segment_type == "main" and downstream_count >= 3:
                seg.segment_type = "trunk"
            elif seg.segment_type == "site_connection" and upstream_count >= 2:
                seg.segment_type = "trunk"

    def _propagate_network_demands(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
    ) -> None:
        for _ in range(60):
            changed = False
            for seg in segments:
                downstream_dfu = 0.0
                downstream_flow = 0.0
                for child_name in seg.connected_segment_names:
                    child = segment_lookup.get(child_name)
                    if child is None:
                        seg.warnings.append(f"Missing connected segment '{child_name}'.")
                        continue
                    downstream_dfu += child.assigned_dfu
                    downstream_flow += child.assigned_flow_gpm
                new_dfu = round(max(seg.assigned_dfu, seg.assigned_dfu + downstream_dfu), 3)
                new_flow = round(max(seg.assigned_flow_gpm, seg.assigned_flow_gpm + downstream_flow), 3)
                if new_dfu > seg.assigned_dfu or new_flow > seg.assigned_flow_gpm:
                    seg.assigned_dfu = new_dfu
                    seg.assigned_flow_gpm = new_flow
                    changed = True
            if not changed:
                break

    # =========================================================================
    # GEOMETRY / LENGTHS
    # =========================================================================

    def _apply_geometry_lengths(self, segments: Sequence[SanitaryPipeSegment], request: SanitarySizingRequest) -> None:
        if not request.use_geometry_length_if_available:
            return
        for seg in segments:
            if len(seg.geometry_points) >= 2:
                length = 0.0
                for i in range(1, len(seg.geometry_points)):
                    x1, y1 = seg.geometry_points[i - 1]
                    x2, y2 = seg.geometry_points[i]
                    length += math.hypot(x2 - x1, y2 - y1)
                if length > 0:
                    seg.length = max(seg.length, round(length * request.geometry_length_factor, 3))

    # =========================================================================
    # SIZING / SLOPES
    # =========================================================================

    def _pick_pipe_size(self, dfu: float, min_size: float) -> Dict[str, float]:
        eligible = [row for row in self.CAPACITY_TABLE if row["size_in"] >= min_size]
        if not eligible:
            return self.CAPACITY_TABLE[-1]
        for row in eligible:
            if dfu <= row["max_dfu"]:
                return row
        return eligible[-1]

    def _default_slope_for_segment(
        self,
        seg: SanitaryPipeSegment,
        request: SanitarySizingRequest,
        min_table_slope: float,
    ) -> float:
        attr = self.TYPE_SLOPE_MAP.get(seg.segment_type, "default_main_slope")
        default_value = getattr(request, attr, request.default_main_slope)
        return max(default_value, seg.min_slope, min_table_slope)

    def _manning_full_flow_capacity_cfs(self, diameter_in: float, slope_ft_ft: float, mannings_n: float = 0.013) -> float:
        diameter_ft = max(0.01, diameter_in / 12.0)
        slope = max(0.000001, slope_ft_ft)
        n = max(0.001, mannings_n)
        area = math.pi * diameter_ft * diameter_ft / 4.0
        radius = diameter_ft / 4.0
        return (1.486 / n) * area * (radius ** (2.0 / 3.0)) * (slope ** 0.5)

    def _assign_manning_capacity(self, seg: SanitaryPipeSegment) -> None:
        capacity_cfs = self._manning_full_flow_capacity_cfs(seg.assigned_size_in, seg.slope, seg.mannings_n)
        flow_cfs = max(0.0, seg.assigned_flow_gpm) * 0.00222800926
        diameter_ft = max(0.01, seg.assigned_size_in / 12.0)
        area = math.pi * diameter_ft * diameter_ft / 4.0
        seg.capacity_cfs = round(capacity_cfs, 4)
        seg.capacity_gpm = round(capacity_cfs / 0.00222800926, 3)
        seg.capacity_ratio = round(flow_cfs / max(capacity_cfs, 1e-9), 4)
        seg.velocity_fps = round(flow_cfs / max(area, 1e-9), 3)
        seg.flow_depth_ratio = round(min(1.0, seg.capacity_ratio), 4)

    # =========================================================================
    # RELATIVE INVERT SYSTEM (A-MODE)
    # =========================================================================

    def _assign_relative_inverts(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
        request: SanitarySizingRequest,
    ) -> List[str]:
        warnings: List[str] = []

        # roots are segments with no explicit upstream references
        roots = [seg for seg in segments if not seg.upstream_segment_names]
        if not roots:
            roots = list(segments)

        base = request.start_reference_invert_ft
        ordered = self._topological_like_order(segments, segment_lookup)

        # initialize roots
        for idx, seg in enumerate(roots):
            if seg.upstream_invert_ft is None:
                seg.upstream_invert_ft = base + idx * 0.25
            if seg.downstream_invert_ft is None:
                seg.downstream_invert_ft = seg.upstream_invert_ft - seg.invert_drop

        # propagate through network
        for seg in ordered:
            if seg.upstream_invert_ft is None:
                if seg.upstream_segment_names:
                    parent_outs = []
                    for up_name in seg.upstream_segment_names:
                        up = segment_lookup.get(up_name)
                        if up and up.downstream_invert_ft is not None:
                            parent_outs.append(up.downstream_invert_ft)
                    if parent_outs:
                        seg.upstream_invert_ft = min(parent_outs)
                if seg.upstream_invert_ft is None:
                    seg.upstream_invert_ft = base

            seg.downstream_invert_ft = seg.upstream_invert_ft - seg.invert_drop

            # downstream child continuity
            for child_name in seg.connected_segment_names:
                child = segment_lookup.get(child_name)
                if child is None:
                    continue
                proposed_up = seg.downstream_invert_ft
                if child.upstream_invert_ft is None:
                    child.upstream_invert_ft = proposed_up
                else:
                    child.upstream_invert_ft = min(child.upstream_invert_ft, proposed_up)

        # rim elevations
        if request.assign_relative_rims:
            for seg in segments:
                if seg.rim_elev_ft is None and seg.upstream_invert_ft is not None:
                    seg.rim_elev_ft = seg.upstream_invert_ft + max(3.0, seg.assigned_size_in / 12.0)

        # consistency checks
        for seg in segments:
            if seg.upstream_invert_ft is not None and seg.downstream_invert_ft is not None:
                if seg.downstream_invert_ft >= seg.upstream_invert_ft:
                    seg.warnings.append("Downstream invert is not lower than upstream invert.")
            for child_name in seg.connected_segment_names:
                child = segment_lookup.get(child_name)
                if child and seg.downstream_invert_ft is not None and child.upstream_invert_ft is not None:
                    if child.upstream_invert_ft > seg.downstream_invert_ft + 1e-6:
                        child.warnings.append(f"Upstream invert of '{child.name}' is above parent downstream invert.")
                        warnings.append(f"Invert mismatch between '{seg.name}' and '{child.name}'.")
        return warnings

    def _topological_like_order(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
    ) -> List[SanitaryPipeSegment]:
        indegree: Dict[str, int] = {seg.name: 0 for seg in segments}
        for seg in segments:
            for child_name in seg.connected_segment_names:
                if child_name in indegree:
                    indegree[child_name] += 1

        queue = [segment_lookup[name] for name, deg in indegree.items() if deg == 0]
        ordered: List[SanitaryPipeSegment] = []
        seen: Set[str] = set()

        while queue:
            seg = queue.pop(0)
            if seg.name in seen:
                continue
            seen.add(seg.name)
            ordered.append(seg)
            for child_name in seg.connected_segment_names:
                if child_name in indegree:
                    indegree[child_name] -= 1
                    if indegree[child_name] <= 0:
                        queue.append(segment_lookup[child_name])

        for seg in segments:
            if seg.name not in seen:
                ordered.append(seg)
        return ordered

    # =========================================================================
    # CLEANOUT / MANHOLE / JUNCTION
    # =========================================================================

    def _requires_cleanout(self, seg: SanitaryPipeSegment) -> bool:
        if seg.segment_type in {"building_drain", "main", "grease", "site_connection", "trunk"}:
            return True
        return seg.length >= seg.cleanout_spacing_ft

    def _estimate_cleanout_count(self, length: float, spacing_ft: float) -> int:
        if spacing_ft <= 0.0:
            return 1
        count = int(length // spacing_ft)
        return max(1, count + 1)

    def _assign_manhole_and_junction_logic(
        self,
        segments: Sequence[SanitaryPipeSegment],
        segment_lookup: Dict[str, SanitaryPipeSegment],
        request: SanitarySizingRequest,
    ) -> None:
        downstream_map: Dict[str, int] = {seg.name: 0 for seg in segments}
        upstream_map: Dict[str, int] = {seg.name: len([x for x in seg.upstream_segment_names if x in segment_lookup]) for seg in segments}

        for seg in segments:
            for child_name in seg.connected_segment_names:
                if child_name in downstream_map:
                    downstream_map[seg.name] += 1

        for seg in segments:
            if seg.segment_type in {"main", "trunk", "site_connection"} or seg.length >= request.max_manhole_spacing_ft:
                seg.has_manhole_upstream = True
                seg.has_manhole_downstream = True

            if upstream_map.get(seg.name, 0) >= 2:
                seg.junction_count = upstream_map.get(seg.name, 0)
                seg.has_manhole_upstream = True

            base_manhole_count = 0
            if seg.has_manhole_upstream:
                base_manhole_count += 1
            if seg.has_manhole_downstream:
                base_manhole_count += 1
            if seg.length > request.max_manhole_spacing_ft:
                base_manhole_count += int(seg.length // request.max_manhole_spacing_ft)
            seg.manhole_count = max(seg.manhole_count, base_manhole_count)

    # =========================================================================
    # SUMMARY / EXPLAIN / HOOKS
    # =========================================================================

    def _build_summary(
        self,
        segments: Sequence[SanitaryPipeSegment],
        fixtures: Sequence[SanitaryFixture],
        grease_fixture_count: int,
        warnings: Sequence[str],
    ) -> SanitarySystemSummary:
        summary = SanitarySystemSummary()
        summary.segment_count = len(segments)
        summary.fixture_count = len(fixtures)
        summary.total_dfu = max((seg.assigned_dfu for seg in segments), default=0.0)
        summary.total_flow_gpm = max((seg.assigned_flow_gpm for seg in segments), default=0.0)
        summary.total_length_ft = sum(seg.length for seg in segments)
        summary.max_depth_drop_ft = max((seg.invert_drop for seg in segments), default=0.0)
        summary.cleanout_count = sum(seg.cleanout_count for seg in segments)
        summary.manhole_count = sum(seg.manhole_count for seg in segments)
        summary.junction_count = sum(seg.junction_count for seg in segments)
        summary.grease_fixture_count = grease_fixture_count
        summary.issue_count = len(warnings) + sum(len(seg.warnings) for seg in segments)
        for seg in segments:
            summary.by_segment_type[seg.segment_type] = summary.by_segment_type.get(seg.segment_type, 0) + 1
        return summary

    def _build_explain_payload(
        self,
        segments: Sequence[SanitaryPipeSegment],
        request: SanitarySizingRequest,
        summary: SanitarySystemSummary,
    ) -> Dict[str, Any]:
        return {
            "system_type": "sanitary",
            "design_mode": "relative_invert_system",
            "summary": summary.to_dict(),
            "key_logic": [
                "Fixture demand converted to DFU and GPM.",
                "Demand propagated through downstream sanitary network.",
                "Pipe size selected from simplified DFU capacity table.",
                "Relative invert elevations assigned to maintain downhill continuity.",
                "Cleanouts and manholes estimated from segment role and spacing.",
            ],
            "critical_segments": [
                {
                    "name": seg.name,
                    "segment_type": seg.segment_type,
                    "assigned_dfu": seg.assigned_dfu,
                    "assigned_size_in": seg.assigned_size_in,
                    "capacity_gpm": seg.capacity_gpm,
                    "velocity_fps": seg.velocity_fps,
                    "capacity_ratio": seg.capacity_ratio,
                    "slope": seg.slope,
                    "upstream_invert_ft": seg.upstream_invert_ft,
                    "downstream_invert_ft": seg.downstream_invert_ft,
                    "warning_count": len(seg.warnings),
                }
                for seg in sorted(segments, key=lambda s: (len(s.warnings), s.assigned_dfu), reverse=True)[:5]
            ],
        }

    def _build_optimize_hooks(
        self,
        segments: Sequence[SanitaryPipeSegment],
        summary: SanitarySystemSummary,
    ) -> Dict[str, Any]:
        return {
            "weighted_penalties": {
                "warning_penalty": sum(len(seg.warnings) for seg in segments) * 3.0,
                "length_penalty": round(summary.total_length_ft / 100.0, 3),
                "depth_drop_penalty": round(summary.max_depth_drop_ft / 10.0, 3),
            },
            "candidate_improvements": [
                "reduce route length",
                "reduce excessive depth drops",
                "improve slope consistency",
                "reduce cleanout/manhole count where feasible",
            ],
        }

    def _build_conflict_hooks(self, segments: Sequence[SanitaryPipeSegment]) -> Dict[str, Any]:
        return {
            "linework_candidates": [
                {
                    "name": seg.name,
                    "segment_type": seg.segment_type,
                    "geometry_points": list(seg.geometry_points),
                    "assigned_size_in": seg.assigned_size_in,
                    "capacity_gpm": seg.capacity_gpm,
                    "velocity_fps": seg.velocity_fps,
                    "capacity_ratio": seg.capacity_ratio,
                    "upstream_invert_ft": seg.upstream_invert_ft,
                    "downstream_invert_ft": seg.downstream_invert_ft,
                    "route_system_type": "sanitary",
                }
                for seg in segments
                if len(seg.geometry_points) >= 2
            ]
        }


def size_sanitary_system(request: SanitarySizingRequest) -> SanitarySizingResult:
    return SanitaryEngine().size(request)
