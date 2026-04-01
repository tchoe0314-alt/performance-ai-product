from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class VentFixture:
    name: str
    fixture_type: str
    trap_arm_length_ft: float = 0.0
    max_trap_arm_ft: float = 6.0
    requires_individual_vent: bool = False
    wet_vent_eligible: bool = True
    floor_level: str = "Level 1"
    drainage_segment_name: Optional[str] = None
    vent_segment_name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VentSegment:
    name: str
    segment_type: str  # individual | branch_vent | stack_vent | vent_header | relief_vent | wet_vent
    connected_fixture_names: List[str] = field(default_factory=list)
    connected_segment_names: List[str] = field(default_factory=list)
    length: float = 0.0
    min_size_in: float = 1.5
    assigned_size_in: float = 0.0
    floor_level: str = "Level 1"
    rises_to_roof: bool = False
    serves_wet_vent: bool = False
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VentSizingRequest:
    fixtures: List[VentFixture] = field(default_factory=list)
    segments: List[VentSegment] = field(default_factory=list)
    minimum_vent_size_in: float = 1.5
    roof_penetration_min_in: float = 2.0
    allow_wet_venting: bool = True
    require_roof_termination: bool = True
    conservative: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VentSizingResult:
    success: bool
    message: str = ""
    segments: List[VentSegment] = field(default_factory=list)
    individually_vented_count: int = 0
    wet_vented_count: int = 0
    roof_termination_count: int = 0
    warnings: List[str] = field(default_factory=list)


class VentEngine:
    """
    Early-stage vent system logic engine.

    Current behavior:
    - checks trap arm lengths
    - assigns fixtures to vent segments
    - sizes vents with simple rules
    - flags missing roof terminations
    - flags fixtures lacking vent assignment
    - tracks individual vent vs wet vent usage

    This is concept vent logic, not final code-certified vent design.
    """

    DEFAULT_MAX_TRAP_ARM = {
        "lav": 5.0,
        "sink": 5.0,
        "kitchen_sink": 5.0,
        "wc": 6.0,
        "urinal": 6.0,
        "shower": 8.0,
        "floor_drain": 5.0,
        "mop_sink": 5.0,
    }

    DEFAULT_MIN_VENT_SIZE = {
        "individual": 1.5,
        "branch_vent": 2.0,
        "stack_vent": 2.0,
        "vent_header": 2.0,
        "relief_vent": 2.0,
        "wet_vent": 2.0,
    }

    def size(self, request: VentSizingRequest) -> VentSizingResult:
        if not request.segments:
            return VentSizingResult(False, message="No vent segments provided.")

        fixtures = self._normalize_fixtures(request.fixtures)
        segments = [self._clone_segment(seg) for seg in request.segments]

        fixture_lookup = {fx.name: fx for fx in fixtures}
        segment_lookup = {seg.name: seg for seg in segments}

        warnings: List[str] = []
        individually_vented = 0
        wet_vented = 0

        for fx in fixtures:
            max_trap = fx.max_trap_arm_ft
            if max_trap <= 0.0:
                max_trap = self.DEFAULT_MAX_TRAP_ARM.get(fx.fixture_type.strip().lower(), 6.0)

            if fx.trap_arm_length_ft > max_trap:
                warnings.append(
                    f"Fixture '{fx.name}' trap arm length exceeds recommended maximum ({fx.trap_arm_length_ft} > {max_trap})."
                )

            if not fx.vent_segment_name:
                warnings.append(f"Fixture '{fx.name}' has no assigned vent segment.")

        for seg in segments:
            if seg.assigned_size_in <= 0.0:
                seg.assigned_size_in = max(
                    request.minimum_vent_size_in,
                    self.DEFAULT_MIN_VENT_SIZE.get(seg.segment_type, 1.5),
                    seg.min_size_in,
                )

            served_fixtures = []
            for fx_name in seg.connected_fixture_names:
                fx = fixture_lookup.get(fx_name)
                if fx is None:
                    seg.warnings.append(f"Missing fixture '{fx_name}'.")
                    continue
                served_fixtures.append(fx)

            if seg.segment_type == "individual":
                individually_vented += len(served_fixtures)

            if seg.segment_type == "wet_vent":
                if not request.allow_wet_venting:
                    seg.warnings.append("Wet vent segment provided but wet venting is disabled.")
                else:
                    seg.serves_wet_vent = True
                    wet_vented += len(served_fixtures)
                    for fx in served_fixtures:
                        if not fx.wet_vent_eligible:
                            seg.warnings.append(
                                f"Fixture '{fx.name}' may not be eligible for wet venting."
                            )

            if seg.segment_type in {"stack_vent", "vent_header"} and request.require_roof_termination:
                if seg.assigned_size_in < request.roof_penetration_min_in and seg.rises_to_roof:
                    seg.warnings.append(
                        "Roof-terminating vent is smaller than requested roof penetration minimum."
                    )

            if seg.length > 150.0 and seg.segment_type in {"branch_vent", "vent_header"}:
                seg.warnings.append("Long vent run; consider relief venting or additional stack support.")

            warnings.extend(seg.warnings)

        roof_termination_count = sum(1 for seg in segments if seg.rises_to_roof)
        if request.require_roof_termination and roof_termination_count == 0:
            warnings.append("No roof-terminating vent segments were identified.")

        for seg in segments:
            for child_name in seg.connected_segment_names:
                if child_name not in segment_lookup:
                    seg.warnings.append(f"Missing connected vent segment '{child_name}'.")
                    warnings.append(f"Missing connected vent segment '{child_name}' referenced by '{seg.name}'.")

        return VentSizingResult(
            success=True,
            message="Vent system evaluated.",
            segments=segments,
            individually_vented_count=individually_vented,
            wet_vented_count=wet_vented,
            roof_termination_count=roof_termination_count,
            warnings=sorted(set(warnings)),
        )

    def _normalize_fixtures(self, fixtures: Sequence[VentFixture]) -> List[VentFixture]:
        normalized: List[VentFixture] = []
        for fx in fixtures:
            max_trap = fx.max_trap_arm_ft
            if max_trap <= 0.0:
                max_trap = self.DEFAULT_MAX_TRAP_ARM.get(fx.fixture_type.strip().lower(), 6.0)

            normalized.append(
                VentFixture(
                    name=fx.name,
                    fixture_type=fx.fixture_type,
                    trap_arm_length_ft=fx.trap_arm_length_ft,
                    max_trap_arm_ft=max_trap,
                    requires_individual_vent=fx.requires_individual_vent,
                    wet_vent_eligible=fx.wet_vent_eligible,
                    floor_level=fx.floor_level,
                    drainage_segment_name=fx.drainage_segment_name,
                    vent_segment_name=fx.vent_segment_name,
                    meta=dict(fx.meta),
                )
            )
        return normalized

    def _clone_segment(self, seg: VentSegment) -> VentSegment:
        return VentSegment(
            name=seg.name,
            segment_type=seg.segment_type,
            connected_fixture_names=list(seg.connected_fixture_names),
            connected_segment_names=list(seg.connected_segment_names),
            length=seg.length,
            min_size_in=seg.min_size_in,
            assigned_size_in=seg.assigned_size_in,
            floor_level=seg.floor_level,
            rises_to_roof=seg.rises_to_roof,
            serves_wet_vent=seg.serves_wet_vent,
            warnings=list(seg.warnings),
            meta=dict(seg.meta),
        )


def size_vent_system(request: VentSizingRequest) -> VentSizingResult:
    return VentEngine().size(request)