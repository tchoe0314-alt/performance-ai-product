
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Dict, List

METHOD_VERSION = "rational_peak_v2"


class EngineeringInputError(ValueError):
    """An invalid physical input; safe to translate into an actionable stage error."""


class EngineeringComputationError(ValueError):
    """The calculation cannot produce a finite result in its supported domain."""


def _physical_number(value, field_name, *, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise EngineeringInputError(f"{field_name} must be a finite nonnegative number.")
    if maximum is not None and value > maximum:
        raise EngineeringInputError(f"{field_name} must not exceed {maximum}.")
    return float(value)

@dataclass
class RationalArea:
    name: str
    area_ac: float
    runoff_c: float
    intensity_in_hr: float

    @property
    def flow_cfs(self) -> float:
        area = _physical_number(self.area_ac, "area_ac")
        c = _physical_number(self.runoff_c, "runoff_c", maximum=1)
        intensity = _physical_number(self.intensity_in_hr, "intensity_in_hr")
        flow = 1.008 * area * c * intensity
        if not math.isfinite(flow):
            raise EngineeringComputationError("Rational-method runoff exceeds finite numeric range.")
        return flow

@dataclass
class HydrologyResult:
    success: bool
    total_runoff_cfs: float = 0.0
    area_rows: List[Dict[str, float]] = field(default_factory=list)
    status: str = "computed"
    method_version: str = METHOD_VERSION

def compute_rational_method(areas: List[RationalArea]) -> HydrologyResult:
    if not isinstance(areas, (list, tuple)) or any(not isinstance(area, RationalArea) for area in areas):
        raise EngineeringInputError("areas must contain RationalArea inputs.")
    if not areas:
        return HydrologyResult(success=False, status="no_catchments")
    rows = []
    total = 0.0
    for area in areas:
        q = area.flow_cfs
        total += q
        if not math.isfinite(total):
            raise EngineeringComputationError("Total runoff exceeds finite numeric range.")
        rows.append({
            "name": area.name,
            "area_ac": area.area_ac,
            "runoff_c": area.runoff_c,
            "intensity_in_hr": area.intensity_in_hr,
            "flow_cfs": q,
        })
    return HydrologyResult(success=True, total_runoff_cfs=total, area_rows=rows)
