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

    PIPE_CAPACITY_TABLE = [
        {"size_in": 0.5, "max_gpm": 4.0, "loss_100ft": 14.0},
        {"size_in": 0.75, "max_gpm": 8.0, "loss_100ft": 8.5},
        {"size_in": 1.0, "max_gpm": 16.0, "loss_100ft": 4.5},
        {"size_in": 1.25, "max_gpm": 28.0, "loss_100ft": 2.5},
        {"size_in": 1.5, "max_gpm": 42.0, "loss_100ft": 1.6},
        {"size_in": 2.0, "max_gpm": 75.0, "loss_100ft": 0.8},
        {"size_in": 2.5, "max_gpm": 120.0, "loss_100ft": 0.45},
        {"size_in": 3.0, "max_gpm": 180.0, "loss_100ft": 0.25},
        {"size_in": 4.0, "max_gpm": 320.0, "loss_100ft": 0.12},
    ]

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
            )
            seg.assigned_size_in = size_row["size_in"]
            seg.pressure_loss_per_100ft = size_row["loss_100ft"]

            if seg.assigned_flow_gpm > size_row["max_gpm"]:
                seg.warnings.append("Assigned flow exceeds nominal capacity table value.")
            if seg.pressure_loss_per_100ft > seg.target_pressure_loss_per_100ft:
                seg.warnings.append("Pressure loss target exceeded.")
            if seg.assigned_size_in < seg.min_size_in:
                seg.warnings.append("Assigned size is smaller than minimum requested.")
            warnings.extend(seg.warnings)

        total_flow = max((seg.assigned_flow_gpm for seg in segments), default=0.0)
        remaining_pressure = self._estimate_remaining_pressure(request, segments)

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

    def _pick_pipe_size(self, flow_gpm: float, min_size: float, target_loss: float) -> Dict[str, float]:
        eligible = [row for row in self.PIPE_CAPACITY_TABLE if row["size_in"] >= min_size]
        if not eligible:
            return self.PIPE_CAPACITY_TABLE[-1]

        for row in eligible:
            if flow_gpm <= row["max_gpm"] and row["loss_100ft"] <= target_loss:
                return row

        for row in eligible:
            if flow_gpm <= row["max_gpm"]:
                return row

        return eligible[-1]

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
            variable_losses += (seg.length / 100.0) * seg.pressure_loss_per_100ft
            static_losses += max(0.0, seg.elevation_gain) * request.static_loss_per_ft_psi

        return available - fixed_losses - variable_losses - static_losses


def size_water_system(request: WaterSizingRequest) -> WaterSizingResult:
    return WaterSizingEngine().size(request)