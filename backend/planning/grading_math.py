from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Dict, List, Sequence, Tuple


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


def summarize_drainage_aware_repair(
    before_points: Sequence[Tuple[float, float, float]],
    after_points: Sequence[Tuple[float, float, float]],
    *,
    reason: str,
    drainage_target: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for index, (before, after) in enumerate(zip(before_points, after_points), start=1):
        rows.append(
            {
                "point_index": index,
                "x": round(after[0], 3),
                "y": round(after[1], 3),
                "before_z": round(before[2], 4),
                "after_z": round(after[2], 4),
                "delta_z": round(after[2] - before[2], 4),
                "reason": reason,
            }
        )
    total_adjustment = round(sum(abs(row["delta_z"]) for row in rows), 4)
    return {
        "valid": bool(rows) and bool(reason),
        "changed_point_count": sum(1 for row in rows if abs(row["delta_z"]) > 1e-9),
        "total_abs_adjustment_ft": total_adjustment,
        "changes": rows,
        "drainage_target": dict(drainage_target or {}),
        "reason": reason,
        "truth_label": "Drainage-aware grading repair records each elevation change and the drainage reason for it.",
    }


__all__ = ["AdaRepairPoint", "repair_ada_profile", "summarize_drainage_aware_repair"]
