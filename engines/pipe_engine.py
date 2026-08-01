
from __future__ import annotations

"""
pipe_engine.py (REAL MAX MERGED INTEGRATED VERSION)

Purpose
-------
Commercial-grade concept pipe backend for the AI civil engineering design platform.

This version keeps the uploaded file as the base and expands it to better serve as:
- the shared storm drainage pipe backend
- a reusable gravity-pipe coordinator for future sanitary / utility workflows
- a stronger planner/project-manager/system-runner integration surface

Preserved public helpers
------------------------
- make_inlet_node
- make_outlet_node
- rational_flow_cfs
- full_flow_capacity_cfs
- choose_diameter
- design_segment
- design_network_to_outlets
- summary_rows
- to_actions

Key upgrades
------------
- stronger diameter/capacity selection logic
- concept branch + trunk and sequential trunk helpers
- system summary + validation helpers
- downstream continuity validation
- planner/project-manager-friendly export hooks
- optional utility/conflict-ready metadata export
- stronger network graph support without breaking base compatibility

Notes
-----
- This remains concept-level, not final permit / production hydraulics software
- The goal is strong engineering logic, repeatability, planner compatibility,
  and a unified pipe backend for the broader stack
"""

import math
from dataclasses import dataclass, field
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Tuple
from collections import defaultdict

from geometry.geometry_actions import polyline_action, text_action


EPS = 1e-9


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class PipeNode:
    name: str
    x: float
    y: float
    rim_elev: float
    kind: str  # inlet | junction | outlet
    invert_elev: Optional[float] = None
    max_depth_ft: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipeSegment:
    name: str
    start_node: PipeNode
    end_node: PipeNode

    length_ft: float
    area_ac: float
    runoff_c: float
    intensity_in_hr: float
    flow_cfs: float
    upstream_flow_cfs: float
    local_flow_cfs: float

    diameter_in: int
    slope_ft_ft: float

    start_invert: float
    end_invert: float
    cover_start_ft: float
    cover_end_ft: float

    velocity_fps: float
    full_capacity_cfs: float
    capacity_ratio: float

    hgl_start: float
    hgl_end: float
    egl_start: float
    egl_end: float

    path: List[Tuple[float, float]] = field(default_factory=list)
    system_type: str = "storm"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipeSystemSummary:
    pipe_count: int = 0
    total_length_ft: float = 0.0
    total_local_area_ac: float = 0.0
    total_local_flow_cfs: float = 0.0
    total_capacity_cfs: float = 0.0
    max_capacity_ratio: float = 0.0
    worst_segment_name: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# ENGINE
# =============================================================================

class PipeEngine:
    """
    Expanded concept pipe backend.

    Uses:
    - Rational Method: Q = 1.008 * C * I * A
    - Manning full-flow capacity for circular pipe

    Adds:
    - branch/trunk accumulation
    - concept junction support
    - capacity ratio checks
    - HGL/EGL proxy values
    - annotation/export helpers
    - validation/report helpers
    """

    STANDARD_DIAMETERS_IN = [12, 15, 18, 21, 24, 27, 30, 36, 42, 48, 54, 60]

    def __init__(
        self,
        runoff_c: float = 0.85,
        intensity_in_hr: float = 4.0,
        min_pipe_slope: float = 0.003,
        mannings_n: float = 0.013,
        min_cover_ft: float = 3.0,
        min_velocity_fps: float = 2.0,
        max_velocity_fps: float = 12.0,
        max_capacity_ratio: float = 0.95,
        default_capture_fraction: float = 0.35,
        max_junction_spacing_ft: float = 500.0,
    ) -> None:
        self.runoff_c = runoff_c
        self.intensity_in_hr = intensity_in_hr
        self.min_pipe_slope = min_pipe_slope
        self.mannings_n = mannings_n
        self.min_cover_ft = min_cover_ft
        self.min_velocity_fps = min_velocity_fps
        self.max_velocity_fps = max_velocity_fps
        self.max_capacity_ratio = max_capacity_ratio
        self.default_capture_fraction = default_capture_fraction
        self.max_junction_spacing_ft = max_junction_spacing_ft

    # =========================================================================
    # BASIC HYDRAULIC HELPERS
    # =========================================================================

    @staticmethod
    def distance(a: PipeNode, b: PipeNode) -> float:
        return math.hypot(b.x - a.x, b.y - a.y)

    @staticmethod
    def rational_flow_cfs(area_ac: float, runoff_c: float, intensity_in_hr: float) -> float:
        return 1.008 * area_ac * runoff_c * intensity_in_hr

    @staticmethod
    def full_flow_capacity_cfs(
        diameter_in: int,
        slope_ft_ft: float,
        mannings_n: float,
    ) -> float:
        d_ft = diameter_in / 12.0
        area = math.pi * (d_ft ** 2) / 4.0
        wetted_perimeter = math.pi * d_ft
        hydraulic_radius = area / wetted_perimeter

        return (
            (1.486 / mannings_n)
            * area
            * (hydraulic_radius ** (2.0 / 3.0))
            * (max(slope_ft_ft, EPS) ** 0.5)
        )

    @staticmethod
    def full_flow_velocity_fps(
        diameter_in: int,
        slope_ft_ft: float,
        mannings_n: float,
    ) -> float:
        d_ft = diameter_in / 12.0
        area = math.pi * (d_ft ** 2) / 4.0
        if area <= 0.0:
            return 0.0
        q = PipeEngine.full_flow_capacity_cfs(diameter_in, slope_ft_ft, mannings_n)
        return q / area

    @staticmethod
    def area_of_pipe_ft2(diameter_in: int) -> float:
        d_ft = diameter_in / 12.0
        return math.pi * (d_ft ** 2) / 4.0

    def choose_diameter(self, flow_cfs: float, slope_ft_ft: float) -> int:
        """
        Choose the smallest standard diameter whose full-flow capacity exceeds
        the target flow divided by max_capacity_ratio, while preferring
        reasonable velocities.
        """
        slope_ft_ft = max(slope_ft_ft, self.min_pipe_slope)
        required_capacity = flow_cfs / max(self.max_capacity_ratio, EPS)

        best_velocity_candidate: Optional[int] = None
        for dia in self.STANDARD_DIAMETERS_IN:
            capacity = self.full_flow_capacity_cfs(dia, slope_ft_ft, self.mannings_n)
            velocity = self.full_flow_velocity_fps(dia, slope_ft_ft, self.mannings_n)
            if capacity >= required_capacity:
                if self.min_velocity_fps <= velocity <= self.max_velocity_fps:
                    return dia
                if best_velocity_candidate is None:
                    best_velocity_candidate = dia

        if best_velocity_candidate is not None:
            return best_velocity_candidate
        return self.STANDARD_DIAMETERS_IN[-1]

    def estimate_area_ac(self, basin_area_sf: float, capture_fraction: Optional[float] = None) -> float:
        capture = self.default_capture_fraction if capture_fraction is None else capture_fraction
        return max((max(basin_area_sf, 0.0) * capture) / 43560.0, 0.01)

    # =========================================================================
    # NODE HELPERS
    # =========================================================================

    def make_inlet_node(self, name: str, x: float, y: float, rim_elev: float) -> PipeNode:
        return PipeNode(
            name=name,
            x=float(x),
            y=float(y),
            rim_elev=float(rim_elev),
            kind="inlet",
        )

    def make_outlet_node(self, name: str, x: float, y: float, rim_elev: float) -> PipeNode:
        return PipeNode(
            name=name,
            x=float(x),
            y=float(y),
            rim_elev=float(rim_elev),
            kind="outlet",
        )

    def make_junction_node(self, name: str, x: float, y: float, rim_elev: float) -> PipeNode:
        return PipeNode(
            name=name,
            x=float(x),
            y=float(y),
            rim_elev=float(rim_elev),
            kind="junction",
        )

    # =========================================================================
    # HGL / EGL PROXY HELPERS
    # =========================================================================

    def estimate_hgl_offset_ft(self, capacity_ratio: float, velocity_fps: float) -> float:
        """
        Concept surcharge / energy proxy.
        """
        surcharge = max(0.0, capacity_ratio - 0.75) * 2.5
        velocity_head = (velocity_fps ** 2) / (2.0 * 32.2)
        return surcharge + velocity_head * 0.35

    # =========================================================================
    # SEGMENT DESIGN
    # =========================================================================

    def design_segment(
        self,
        name: str,
        start_node: PipeNode,
        end_node: PipeNode,
        area_ac: float,
        runoff_c: Optional[float] = None,
        intensity_in_hr: Optional[float] = None,
        slope_ft_ft: Optional[float] = None,
        upstream_flow_cfs: float = 0.0,
        path: Optional[List[Tuple[float, float]]] = None,
        system_type: str = "storm",
    ) -> PipeSegment:
        runoff_c = self.runoff_c if runoff_c is None else runoff_c
        intensity_in_hr = self.intensity_in_hr if intensity_in_hr is None else intensity_in_hr

        length_ft = self.distance(start_node, end_node)
        if path and len(path) >= 2:
            length_ft = self._polyline_length(path)

        if length_ft <= 0.0:
            raise ValueError(f"{name} has zero length.")

        if slope_ft_ft is None:
            raw_slope = (start_node.rim_elev - end_node.rim_elev) / max(length_ft, EPS)
            slope_ft_ft = max(raw_slope, self.min_pipe_slope)
        else:
            slope_ft_ft = max(slope_ft_ft, self.min_pipe_slope)

        local_flow_cfs = self.rational_flow_cfs(area_ac, runoff_c, intensity_in_hr)
        flow_cfs = upstream_flow_cfs + local_flow_cfs

        diameter_in = self.choose_diameter(flow_cfs, slope_ft_ft)
        full_capacity = self.full_flow_capacity_cfs(diameter_in, slope_ft_ft, self.mannings_n)
        velocity = self.full_flow_velocity_fps(diameter_in, slope_ft_ft, self.mannings_n)
        capacity_ratio = flow_cfs / max(full_capacity, EPS)

        if start_node.invert_elev is not None:
            start_invert = float(start_node.invert_elev)
        else:
            start_invert = start_node.rim_elev - self.min_cover_ft

        end_invert = start_invert - slope_ft_ft * length_ft

        outlet_cover_target = end_node.rim_elev - self.min_cover_ft
        if end_invert > outlet_cover_target:
            end_invert = outlet_cover_target
            slope_ft_ft = max((start_invert - end_invert) / max(length_ft, EPS), self.min_pipe_slope)
            full_capacity = self.full_flow_capacity_cfs(diameter_in, slope_ft_ft, self.mannings_n)
            velocity = self.full_flow_velocity_fps(diameter_in, slope_ft_ft, self.mannings_n)
            capacity_ratio = flow_cfs / max(full_capacity, EPS)

        cover_start = start_node.rim_elev - start_invert
        cover_end = end_node.rim_elev - end_invert

        hgl_offset = self.estimate_hgl_offset_ft(capacity_ratio, velocity)
        hgl_start = start_node.rim_elev - max(0.5, cover_start * 0.35) + hgl_offset
        hgl_end = end_node.rim_elev - max(0.5, cover_end * 0.35) + hgl_offset
        egl_start = hgl_start + (velocity ** 2) / (2.0 * 32.2)
        egl_end = hgl_end + (velocity ** 2) / (2.0 * 32.2)

        meta: Dict[str, Any] = {
            "capacity_ok": capacity_ratio <= 1.0 + 1e-9,
            "preferred_capacity_ok": capacity_ratio <= self.max_capacity_ratio + 1e-9,
            "velocity_ok": self.min_velocity_fps <= velocity <= self.max_velocity_fps,
            "cover_ok": cover_start >= self.min_cover_ft and cover_end >= self.min_cover_ft,
        }

        seg = PipeSegment(
            name=name,
            start_node=start_node,
            end_node=end_node,
            length_ft=length_ft,
            area_ac=area_ac,
            runoff_c=runoff_c,
            intensity_in_hr=intensity_in_hr,
            flow_cfs=flow_cfs,
            upstream_flow_cfs=upstream_flow_cfs,
            local_flow_cfs=local_flow_cfs,
            diameter_in=diameter_in,
            slope_ft_ft=slope_ft_ft,
            start_invert=start_invert,
            end_invert=end_invert,
            cover_start_ft=cover_start,
            cover_end_ft=cover_end,
            velocity_fps=velocity,
            full_capacity_cfs=full_capacity,
            capacity_ratio=capacity_ratio,
            hgl_start=hgl_start,
            hgl_end=hgl_end,
            egl_start=egl_start,
            egl_end=egl_end,
            path=list(path) if path else [(start_node.x, start_node.y), (end_node.x, end_node.y)],
            system_type=system_type,
            meta=meta,
        )

        end_node.invert_elev = seg.end_invert
        return seg

    # =========================================================================
    # NETWORK DESIGN
    # =========================================================================

    def design_network_to_outlets(
        self,
        inlets: List[PipeNode],
        outlets: List[PipeNode],
        basin_area_map_sf: Optional[Dict[str, float]] = None,
        *,
        branch_group_size: int = 3,
        force_trunks: bool = True,
        system_type: str = "storm",
    ) -> List[PipeSegment]:
        """
        Build a concept branch + trunk network:
        - group nearby inlets
        - create optional junctions/trunks
        - accumulate upstream flow into downstream segments

        Keeps the original method name/signature compatibility while becoming
        more sophisticated than pure nearest-outlet routing.
        """
        if not inlets or not outlets:
            return []

        inlets_sorted = sorted(inlets, key=lambda n: (n.x, n.y, n.name))
        group_size = max(2, int(branch_group_size))
        groups: List[List[PipeNode]] = []
        for idx in range(0, len(inlets_sorted), group_size):
            groups.append(inlets_sorted[idx: idx + group_size])

        segments: List[PipeSegment] = []
        junctions: List[PipeNode] = []

        for g_idx, group in enumerate(groups, start=1):
            if not group:
                continue

            group_area_sf = 0.0
            for inlet in group:
                if basin_area_map_sf and inlet.name in basin_area_map_sf:
                    group_area_sf += max(0.0, basin_area_map_sf[inlet.name])
                else:
                    group_area_sf += 5000.0

            outlet_hint = min(outlets, key=lambda o: min(self.distance(n, o) for n in group))
            group_junction = None

            if force_trunks and len(group) > 1:
                jx = sum(n.x for n in group) / len(group)
                jy = sum(n.y for n in group) / len(group)
                rim_guess = sum(n.rim_elev for n in group) / len(group) - 0.25
                group_junction = self.make_junction_node(f"J-{g_idx}", jx, jy, rim_guess)
                junctions.append(group_junction)

            for inlet in group:
                local_area_sf = basin_area_map_sf.get(inlet.name, 5000.0) if basin_area_map_sf else 5000.0
                target_node = group_junction if group_junction is not None else outlet_hint
                segment = self.design_segment(
                    name=f"P-{len(segments)+1}",
                    start_node=inlet,
                    end_node=target_node,
                    area_ac=self.estimate_area_ac(local_area_sf),
                    upstream_flow_cfs=0.0,
                    system_type=system_type,
                )
                segments.append(segment)

            if group_junction is not None:
                upstream_group_flow = sum(seg.flow_cfs for seg in segments if seg.end_node.name == group_junction.name)
                segment = self.design_segment(
                    name=f"T-{g_idx}",
                    start_node=group_junction,
                    end_node=outlet_hint,
                    area_ac=0.01,
                    upstream_flow_cfs=upstream_group_flow,
                    system_type=system_type,
                )
                segments.append(segment)

        return segments

    def design_sequential_trunk_network(
        self,
        nodes: List[PipeNode],
        outlet: PipeNode,
        basin_area_map_sf: Optional[Dict[str, float]] = None,
        system_type: str = "storm",
    ) -> List[PipeSegment]:
        """
        Alternate helper for sequential trunk accumulation along sorted inlet order.
        """
        if not nodes:
            return []

        inlets_sorted = sorted(nodes, key=lambda n: (n.x, n.y, n.name))
        segments: List[PipeSegment] = []
        running_upstream = 0.0
        prev_node: Optional[PipeNode] = None

        for idx, node in enumerate(inlets_sorted, start=1):
            area_sf = basin_area_map_sf.get(node.name, 5000.0) if basin_area_map_sf else 5000.0

            if prev_node is None:
                prev_node = node
                running_upstream += self.rational_flow_cfs(self.estimate_area_ac(area_sf), self.runoff_c, self.intensity_in_hr)
                continue

            seg = self.design_segment(
                name=f"TRUNK-{idx-1}",
                start_node=prev_node,
                end_node=node,
                area_ac=self.estimate_area_ac(area_sf),
                upstream_flow_cfs=running_upstream,
                system_type=system_type,
            )
            segments.append(seg)
            running_upstream = seg.flow_cfs
            prev_node = node

        if prev_node is not None:
            seg = self.design_segment(
                name=f"OUT-{len(segments)+1}",
                start_node=prev_node,
                end_node=outlet,
                area_ac=0.01,
                upstream_flow_cfs=running_upstream,
                system_type=system_type,
            )
            segments.append(seg)

        return segments

    # =========================================================================
    # VALIDATION / ANALYSIS
    # =========================================================================

    def validate_segments(self, segments: List[PipeSegment]) -> PipeSystemSummary:
        """
        Stronger validation pass for planner/system-runner hardening.
        """
        summary = self.system_summary(segments)

        if not segments:
            summary.warnings.append("No pipe segments were created.")
            return summary

        for seg in segments:
            if seg.capacity_ratio > 1.0 + 1e-9:
                summary.errors.append(f"{seg.name} exceeds full-flow capacity.")
            elif seg.capacity_ratio > self.max_capacity_ratio + 1e-9:
                summary.warnings.append(f"{seg.name} exceeds preferred capacity ratio.")

            if seg.cover_start_ft < self.min_cover_ft or seg.cover_end_ft < self.min_cover_ft:
                summary.warnings.append(f"{seg.name} has shallow cover.")

            if seg.velocity_fps < self.min_velocity_fps:
                summary.warnings.append(f"{seg.name} is below preferred self-cleansing velocity.")
            elif seg.velocity_fps > self.max_velocity_fps:
                summary.warnings.append(f"{seg.name} exceeds preferred velocity.")

            if seg.length_ft > self.max_junction_spacing_ft:
                summary.warnings.append(f"{seg.name} is long and may need an intermediate junction/structure.")

        continuity = self.check_network_continuity(segments)
        if continuity["broken_count"] > 0:
            summary.errors.extend(continuity["messages"])

        summary.warnings = list(dict.fromkeys(summary.warnings))
        summary.errors = list(dict.fromkeys(summary.errors))
        return summary

    def check_network_continuity(self, segments: List[PipeSegment]) -> Dict[str, Any]:
        """
        Check simple downstream continuity using node-name connectivity.
        """
        outgoing: DefaultDict[str, List[PipeSegment]] = defaultdict(list)
        incoming: DefaultDict[str, List[PipeSegment]] = defaultdict(list)

        for seg in segments:
            outgoing[seg.start_node.name].append(seg)
            incoming[seg.end_node.name].append(seg)

        broken: List[str] = []
        for seg in segments:
            if seg.start_node.kind != "inlet" and len(incoming.get(seg.start_node.name, [])) == 0:
                broken.append(f"{seg.name} starts at {seg.start_node.name} but no upstream segment connects into it.")
            if seg.end_node.kind != "outlet" and len(outgoing.get(seg.end_node.name, [])) == 0:
                broken.append(f"{seg.name} ends at {seg.end_node.name} but no downstream segment leaves it.")

        return {
            "broken_count": len(broken),
            "messages": broken,
        }

    def export_conflict_hooks(self, segments: List[PipeSegment]) -> Dict[str, Any]:
        return {
            "pipe_segments": [
                {
                    "name": seg.name,
                    "system_type": seg.system_type,
                    "path": list(seg.path),
                    "diameter_in": seg.diameter_in,
                    "start_invert": seg.start_invert,
                    "end_invert": seg.end_invert,
                    "cover_start_ft": seg.cover_start_ft,
                    "cover_end_ft": seg.cover_end_ft,
                    "capacity_ratio": seg.capacity_ratio,
                }
                for seg in segments
            ]
        }

    def export_manager_metrics(self, segments: List[PipeSegment]) -> Dict[str, float]:
        summary = self.system_summary(segments)
        return {
            "pipe_count": float(summary.pipe_count),
            "pipe_total_length_ft": float(summary.total_length_ft),
            "pipe_total_local_flow_cfs": float(summary.total_local_flow_cfs),
            "pipe_total_capacity_cfs": float(summary.total_capacity_cfs),
            "pipe_max_capacity_ratio": float(summary.max_capacity_ratio),
        }

    # =========================================================================
    # REPORTING / OUTPUT
    # =========================================================================

    def summary_rows(self, segments: List[PipeSegment]) -> List[Dict]:
        rows: List[Dict[str, Any]] = []

        for seg in segments:
            rows.append(
                {
                    "pipe": seg.name,
                    "from": seg.start_node.name,
                    "to": seg.end_node.name,
                    "length_ft": round(seg.length_ft, 1),
                    "local_area_ac": round(seg.area_ac, 3),
                    "local_flow_cfs": round(seg.local_flow_cfs, 3),
                    "upstream_flow_cfs": round(seg.upstream_flow_cfs, 3),
                    "flow_cfs": round(seg.flow_cfs, 3),
                    "capacity_cfs": round(seg.full_capacity_cfs, 3),
                    "capacity_ratio": round(seg.capacity_ratio, 3),
                    "velocity_fps": round(seg.velocity_fps, 2),
                    "diameter_in": seg.diameter_in,
                    "slope_pct": round(seg.slope_ft_ft * 100.0, 3),
                    "start_invert": round(seg.start_invert, 2),
                    "end_invert": round(seg.end_invert, 2),
                    "cover_start_ft": round(seg.cover_start_ft, 2),
                    "cover_end_ft": round(seg.cover_end_ft, 2),
                    "hgl_start": round(seg.hgl_start, 2),
                    "hgl_end": round(seg.hgl_end, 2),
                    "egl_start": round(seg.egl_start, 2),
                    "egl_end": round(seg.egl_end, 2),
                }
            )

        return rows

    def system_summary(self, segments: List[PipeSegment]) -> PipeSystemSummary:
        summary = PipeSystemSummary()
        summary.pipe_count = len(segments)
        summary.total_length_ft = round(sum(seg.length_ft for seg in segments), 2)
        summary.total_local_area_ac = round(sum(seg.area_ac for seg in segments), 3)
        summary.total_local_flow_cfs = round(sum(seg.local_flow_cfs for seg in segments), 3)
        summary.total_capacity_cfs = round(sum(seg.full_capacity_cfs for seg in segments), 3)

        if segments:
            worst = max(segments, key=lambda s: s.capacity_ratio)
            summary.max_capacity_ratio = round(worst.capacity_ratio, 3)
            summary.worst_segment_name = worst.name
            if worst.capacity_ratio > 1.0:
                summary.warnings.append(
                    f"Worst segment {worst.name} exceeds full-flow capacity ratio ({worst.capacity_ratio:.3f})."
                )
            if any(seg.cover_end_ft < self.min_cover_ft for seg in segments):
                summary.warnings.append("One or more segments appear to have low outlet cover.")
            if any(seg.velocity_fps > self.max_velocity_fps for seg in segments):
                summary.warnings.append("One or more segments exceed preferred concept velocity.")
            if any(seg.velocity_fps < self.min_velocity_fps for seg in segments):
                summary.warnings.append("One or more segments fall below preferred self-cleansing velocity.")

        summary.warnings = list(dict.fromkeys(summary.warnings))
        return summary

    def to_actions(
        self,
        segments: List[PipeSegment],
        layer_pipe: str = "PIPE",
        layer_anno: str = "ANNO",
        show_pipe_labels: bool = True,
        show_invert_labels: bool = True,
        show_hgl_labels: bool = False,
    ) -> List[Dict]:
        actions: List[Dict[str, Any]] = []

        for seg in segments:
            if seg.path and len(seg.path) >= 2:
                points = [[float(x), float(y)] for x, y in seg.path]
            else:
                points = [[seg.start_node.x, seg.start_node.y], [seg.end_node.x, seg.end_node.y]]

            actions.append(
                polyline_action(
                    points=points,
                    layer=layer_pipe,
                    label=seg.name,
                    closed=False,
                )
            )

            mx, my = self._midpoint_of_path(points)

            if show_pipe_labels:
                actions.append(
                    text_action(
                        x=mx,
                        y=my + 0.6,
                        text=f'{seg.name} {seg.diameter_in}" S={seg.slope_ft_ft:.3f}',
                        layer=layer_anno,
                        height=0.9,
                    )
                )

            if show_invert_labels:
                actions.append(
                    text_action(
                        x=mx,
                        y=my - 0.6,
                        text=f'INV {seg.start_invert:.2f}->{seg.end_invert:.2f}',
                        layer=layer_anno,
                        height=0.8,
                    )
                )

            if show_hgl_labels:
                actions.append(
                    text_action(
                        x=mx,
                        y=my - 1.4,
                        text=f'HGL {seg.hgl_start:.2f}->{seg.hgl_end:.2f}',
                        layer=layer_anno,
                        height=0.8,
                    )
                )

        return actions

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _polyline_length(self, path: Sequence[Tuple[float, float]]) -> float:
        if len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(path)):
            x1, y1 = path[i - 1]
            x2, y2 = path[i]
            total += math.hypot(x2 - x1, y2 - y1)
        return total

    def _midpoint_of_path(self, points: Sequence[Sequence[float]]) -> Tuple[float, float]:
        if not points:
            return 0.0, 0.0
        if len(points) == 1:
            return float(points[0][0]), float(points[0][1])
        mid_idx = len(points) // 2
        if len(points) % 2 == 1:
            return float(points[mid_idx][0]), float(points[mid_idx][1])
        x = (float(points[mid_idx - 1][0]) + float(points[mid_idx][0])) / 2.0
        y = (float(points[mid_idx - 1][1]) + float(points[mid_idx][1])) / 2.0
        return x, y
