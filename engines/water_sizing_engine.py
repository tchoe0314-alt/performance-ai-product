from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class WaterFixture:
    name: str
    fixture_type: str
    demand_fu: float
    branch_length: float = 0.0
    required_pressure: float = 15.0
    diversity_group: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WaterPipeSegment:
    name: str
    segment_type: str  # service | main | branch | riser | return
    connected_fixture_names: List[str] = field(default_factory=list)
    connected_segment_names: List[str] = field(default_factory=list)
    length: float = 0.0
    elevation_gain: float = 0.0
    min_size_in: float = 0.5
    max_velocity_fps: float = 8.0
    target_pressure_loss_per_100ft: float = 8.0
    assigned_fixture_units: float = 0.0
    assigned_flow_gpm: float = 0.0
    assigned_size_in: float = 0.0
    pressure_loss_per_100ft: float = 0.0
    velocity_fps: float = 0.0
    friction_loss_psi: float = 0.0
    residual_pressure_psi: float = 0.0
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WaterSizingRequest:
    fixtures: List[WaterFixture] = field(default_factory=list)
    segments: List[WaterPipeSegment] = field(default_factory=list)
    available_pressure_psi: float = 60.0
    meter_loss_psi: float = 5.0
    backflow_loss_psi: float = 8.0
    heater_loss_psi: float = 4.0
    static_loss_per_ft_psi: float = 0.433
    hazen_williams_c: float = 130.0
    hot_water: bool = False
    conservative: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WaterSizingResult:
    success: bool
    message: str = ""
    segments: List[WaterPipeSegment] = field(default_factory=list)
    total_fixture_units: float = 0.0
    estimated_total_flow_gpm: float = 0.0
    estimated_remaining_pressure_psi: float = 0.0
    warnings: List[str] = field(default_factory=list)


class WaterSizingEngine:
    """
    Early-stage domestic water sizing engine.

    Current behavior:
    - sums fixture units onto segments
    - converts fixture units to probable demand flow
    - assigns a nominal pipe size from a simplified capacity table
    - estimates pressure loss per 100 ft
    - provides a rough remaining pressure check

    This is concept sizing support, not code-certified final hydraulic design.
    """

    NOMINAL_SIZES_IN = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    DEFAULT_FIXTURE_UNIT_TABLE = {
        "lav": 1.0,
        "sink": 1.5,
        "kitchen_sink": 1.5,
        "wc_tank": 2.5,
        "wc_flush_valve": 10.0,
        "urinal": 5.0,
        "shower": 2.0,
        "floor_drain_primer": 0.5,
        "hose_bib": 2.5,
        "water_heater": 3.0,
        "service": 0.0,
    }

    def size(self, request: WaterSizingRequest) -> WaterSizingResult:
        if not request.segments:
            return WaterSizingResult(False, message="No water pipe segments provided.")

        fixtures = self._normalize_fixtures(request.fixtures)
        segments = [self._clone_segment(seg) for seg in request.segments]
        fixture_lookup = {fx.name: fx for fx in fixtures}
        segment_lookup = {seg.name: seg for seg in segments}

        for seg in segments:
            fu = 0.0
            for fx_name in seg.connected_fixture_names:
                fx = fixture_lookup.get(fx_name)
                if fx is None:
                    seg.warnings.append(f"Missing fixture '{fx_name}'.")
                    continue
                fu += fx.demand_fu
            seg.assigned_fixture_units = round(fu, 3)

        changed = True
        safety_iter = 0
        while changed and safety_iter < 25:
            changed = False
            safety_iter += 1
            for seg in segments:
                downstream_fu = sum(
                    segment_lookup[name].assigned_fixture_units
                    for name in seg.connected_segment_names
                    if name in segment_lookup
                )
                total_fu = round(seg.assigned_fixture_units + downstream_fu, 3)
                if total_fu > seg.assigned_fixture_units:
                    seg.assigned_fixture_units = total_fu
                    changed = True

        warnings: List[str] = []
        total_fu = max((seg.assigned_fixture_units for seg in segments), default=0.0)

        for seg in segments:
            seg.assigned_flow_gpm = round(
                self._fixture_units_to_gpm(seg.assigned_fixture_units, request.conservative),
                3,
            )
            size_row = self._pick_pipe_size(
                flow_gpm=seg.assigned_flow_gpm,
                min_size=seg.min_size_in,
                target_loss=seg.target_pressure_loss_per_100ft,
                max_velocity=seg.max_velocity_fps,
                c_factor=request.hazen_williams_c,
            )
            seg.assigned_size_in = size_row["size_in"]
            seg.pressure_loss_per_100ft = size_row["loss_100ft"]
            seg.velocity_fps = size_row["velocity_fps"]
            seg.friction_loss_psi = round((max(seg.length, 0.0) / 100.0) * seg.pressure_loss_per_100ft, 3)

            if seg.pressure_loss_per_100ft > seg.target_pressure_loss_per_100ft:
                seg.warnings.append("Pressure loss target exceeded.")
            if seg.velocity_fps > seg.max_velocity_fps:
                seg.warnings.append("Water velocity exceeds maximum requested velocity.")
            if seg.assigned_size_in < seg.min_size_in:
                seg.warnings.append("Assigned size is smaller than minimum requested.")
            warnings.extend(seg.warnings)

        total_flow = max((seg.assigned_flow_gpm for seg in segments), default=0.0)
        remaining_pressure = self._estimate_remaining_pressure(request, segments)
        for seg in segments:
            seg.residual_pressure_psi = round(
                request.available_pressure_psi
                - request.meter_loss_psi
                - request.backflow_loss_psi
                - (request.heater_loss_psi if request.hot_water else 0.0)
                - seg.friction_loss_psi
                - max(0.0, seg.elevation_gain) * request.static_loss_per_ft_psi,
                3,
            )

        if remaining_pressure < 15.0:
            warnings.append("Estimated remaining pressure is low.")
        if total_fu <= 0.0:
            warnings.append("No effective fixture unit demand was assigned.")

        return WaterSizingResult(
            success=True,
            message="Water system sized.",
            segments=segments,
            total_fixture_units=round(total_fu, 3),
            estimated_total_flow_gpm=round(total_flow, 3),
            estimated_remaining_pressure_psi=round(remaining_pressure, 3),
            warnings=sorted(set(warnings)),
        )

    def _normalize_fixtures(self, fixtures: Sequence[WaterFixture]) -> List[WaterFixture]:
        normalized: List[WaterFixture] = []
        for fx in fixtures:
            if fx.demand_fu <= 0:
                fx_type = fx.fixture_type.strip().lower()
                demand_fu = self.DEFAULT_FIXTURE_UNIT_TABLE.get(fx_type, 1.5)
                normalized.append(
                    WaterFixture(
                        name=fx.name,
                        fixture_type=fx.fixture_type,
                        demand_fu=demand_fu,
                        branch_length=fx.branch_length,
                        required_pressure=fx.required_pressure,
                        diversity_group=fx.diversity_group,
                        meta=dict(fx.meta),
                    )
                )
            else:
                normalized.append(fx)
        return normalized

    def _clone_segment(self, seg: WaterPipeSegment) -> WaterPipeSegment:
        return WaterPipeSegment(
            name=seg.name,
            segment_type=seg.segment_type,
            connected_fixture_names=list(seg.connected_fixture_names),
            connected_segment_names=list(seg.connected_segment_names),
            length=seg.length,
            elevation_gain=seg.elevation_gain,
            min_size_in=seg.min_size_in,
            max_velocity_fps=seg.max_velocity_fps,
            target_pressure_loss_per_100ft=seg.target_pressure_loss_per_100ft,
            assigned_fixture_units=seg.assigned_fixture_units,
            assigned_flow_gpm=seg.assigned_flow_gpm,
            assigned_size_in=seg.assigned_size_in,
            pressure_loss_per_100ft=seg.pressure_loss_per_100ft,
            velocity_fps=seg.velocity_fps,
            friction_loss_psi=seg.friction_loss_psi,
            residual_pressure_psi=seg.residual_pressure_psi,
            warnings=list(seg.warnings),
            meta=dict(seg.meta),
        )

    def _fixture_units_to_gpm(self, fu: float, conservative: bool) -> float:
        if fu <= 0:
            return 0.0
        if fu <= 4:
            gpm = fu * 1.5
        elif fu <= 10:
            gpm = 6.0 + (fu - 4.0) * 1.2
        elif fu <= 20:
            gpm = 13.2 + (fu - 10.0) * 1.0
        elif fu <= 50:
            gpm = 23.2 + (fu - 20.0) * 0.8
        else:
            gpm = 47.2 + (fu - 50.0) * 0.6
        if conservative:
            gpm *= 1.1
        return gpm

    def _pick_pipe_size(self, flow_gpm: float, min_size: float, target_loss: float, max_velocity: float, c_factor: float) -> Dict[str, float]:
        rows = [
            {
                "size_in": size,
                "loss_100ft": self._hazen_williams_loss_psi_per_100ft(flow_gpm, size, c_factor=c_factor),
                "velocity_fps": self._velocity_fps(flow_gpm, size),
            }
            for size in self.NOMINAL_SIZES_IN
        ]
        eligible = [row for row in rows if row["size_in"] >= min_size]
        if not eligible:
            return rows[-1]

        for row in eligible:
            if row["loss_100ft"] <= target_loss and row["velocity_fps"] <= max_velocity:
                return row

        return eligible[-1]

    def _velocity_fps(self, flow_gpm: float, diameter_in: float) -> float:
        if flow_gpm <= 0.0 or diameter_in <= 0.0:
            return 0.0
        area_sf = 3.141592653589793 * (diameter_in / 12.0) ** 2 / 4.0
        return round((flow_gpm * 0.00222800926) / max(area_sf, 1e-9), 3)

    def _hazen_williams_loss_psi_per_100ft(self, flow_gpm: float, diameter_in: float, *, c_factor: float) -> float:
        if flow_gpm <= 0.0 or diameter_in <= 0.0:
            return 0.0
        c = max(1.0, c_factor)
        headloss_ft_per_100ft = 4.52 * 100.0 * (flow_gpm ** 1.85) / ((c ** 1.85) * (diameter_in ** 4.87))
        return round(headloss_ft_per_100ft * 0.433, 3)

    def _estimate_remaining_pressure(
        self,
        request: WaterSizingRequest,
        segments: Sequence[WaterPipeSegment],
    ) -> float:
        available = request.available_pressure_psi
        fixed_losses = request.meter_loss_psi + request.backflow_loss_psi
        if request.hot_water:
            fixed_losses += request.heater_loss_psi

        variable_losses = 0.0
        static_losses = 0.0
        for seg in segments:
            variable_losses += seg.friction_loss_psi or (seg.length / 100.0) * seg.pressure_loss_per_100ft
            static_losses += max(0.0, seg.elevation_gain) * request.static_loss_per_ft_psi

        return available - fixed_losses - variable_losses - static_losses


def size_water_system(request: WaterSizingRequest) -> WaterSizingResult:
    return WaterSizingEngine().size(request)


def analyze_water_pressure_graph(
    segments: Sequence[Dict[str, Any]],
    *,
    source_node: str,
    source_pressure_psi: float,
    hazen_williams_c: float = 130.0,
    static_loss_per_ft_psi: float = 0.433,
) -> Dict[str, Any]:
    engine = WaterSizingEngine()
    node_pressure: Dict[str, float] = {source_node: float(source_pressure_psi)}
    unresolved = [dict(seg) for seg in segments]
    solved: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for _ in range(len(unresolved) + 5):
        progressed = False
        remaining: List[Dict[str, Any]] = []
        for seg in unresolved:
            start = str(seg.get("start_node") or seg.get("from_node") or "")
            end = str(seg.get("end_node") or seg.get("to_node") or "")
            if not start or not end:
                warnings.append("Water pressure graph segment is missing start/end node.")
                continue
            if start not in node_pressure:
                remaining.append(seg)
                continue
            flow_gpm = float(seg.get("flow_gpm") or seg.get("assigned_flow_gpm") or 0.0)
            diameter_in = float(seg.get("diameter_in") or seg.get("assigned_size_in") or 1.0)
            length_ft = float(seg.get("length_ft") or seg.get("length") or 0.0)
            elevation_gain_ft = float(seg.get("elevation_gain_ft") or seg.get("elevation_gain") or 0.0)
            loss_100 = engine._hazen_williams_loss_psi_per_100ft(flow_gpm, diameter_in, c_factor=hazen_williams_c)
            friction_loss = (max(0.0, length_ft) / 100.0) * loss_100
            static_loss = max(0.0, elevation_gain_ft) * static_loss_per_ft_psi
            end_pressure = node_pressure[start] - friction_loss - static_loss
            if end not in node_pressure or end_pressure > node_pressure[end]:
                node_pressure[end] = end_pressure
            solved.append(
                {
                    "name": str(seg.get("name") or f"{start}-{end}"),
                    "start_node": start,
                    "end_node": end,
                    "flow_gpm": round(flow_gpm, 3),
                    "diameter_in": round(diameter_in, 3),
                    "velocity_fps": engine._velocity_fps(flow_gpm, diameter_in),
                    "friction_loss_psi": round(friction_loss, 3),
                    "static_loss_psi": round(static_loss, 3),
                    "start_pressure_psi": round(node_pressure[start], 3),
                    "end_pressure_psi": round(end_pressure, 3),
                }
            )
            progressed = True
        unresolved = remaining
        if not unresolved or not progressed:
            break

    if unresolved:
        warnings.append("Water pressure graph has unreachable segments from the source node.")
    return {
        "success": not unresolved,
        "source_node": source_node,
        "node_pressures_psi": {node: round(value, 3) for node, value in node_pressure.items()},
        "segments": solved,
        "min_pressure_psi": round(min(node_pressure.values()), 3) if node_pressure else 0.0,
        "warnings": warnings,
        "truth_label": "Hazen-Williams steady pressure graph; does not replace calibrated fire-flow modeling.",
    }
