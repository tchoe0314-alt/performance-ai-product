from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import List, Sequence, Tuple


@dataclass
class AdaRepairPoint:
    x: float
    y: float
    existing_z: float
    repaired_z: float
    running_slope: float
    adjusted_ft: float


def repair_ada_profile(
    points: Sequence[Tuple[float, float, float]],
    *,
    max_running_slope: float = 0.0833,
) -> List[AdaRepairPoint]:
    if not points:
        return []
    max_slope = max(0.0001, max_running_slope)
    repaired: List[AdaRepairPoint] = [
        AdaRepairPoint(points[0][0], points[0][1], points[0][2], points[0][2], 0.0, 0.0)
    ]
    for idx in range(1, len(points)):
        x, y, z = points[idx]
        prev = repaired[-1]
        run = max(1e-9, hypot(x - prev.x, y - prev.y))
        raw_slope = (z - prev.repaired_z) / run
        clamped_slope = max(-max_slope, min(max_slope, raw_slope))
        repaired_z = prev.repaired_z + clamped_slope * run
        repaired.append(
            AdaRepairPoint(
                x=x,
                y=y,
                existing_z=z,
                repaired_z=round(repaired_z, 4),
                running_slope=round(clamped_slope, 5),
                adjusted_ft=round(repaired_z - z, 4),
            )
        )
    return repaired


__all__ = ["AdaRepairPoint", "repair_ada_profile"]
