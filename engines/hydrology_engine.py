
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class RationalArea:
    name: str
    area_ac: float
    runoff_c: float
    intensity_in_hr: float

    @property
    def flow_cfs(self) -> float:
        return 1.008 * self.area_ac * self.runoff_c * self.intensity_in_hr

@dataclass
class HydrologyResult:
    success: bool
    total_runoff_cfs: float = 0.0
    area_rows: List[Dict[str, float]] = field(default_factory=list)

def compute_rational_method(areas: List[RationalArea]) -> HydrologyResult:
    rows = []
    total = 0.0
    for area in areas:
        q = area.flow_cfs
        total += q
        rows.append({
            "name": area.name,
            "area_ac": area.area_ac,
            "runoff_c": area.runoff_c,
            "intensity_in_hr": area.intensity_in_hr,
            "flow_cfs": q,
        })
    return HydrologyResult(success=True, total_runoff_cfs=total, area_rows=rows)
