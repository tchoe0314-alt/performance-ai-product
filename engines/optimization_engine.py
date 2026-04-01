
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from copy import deepcopy

@dataclass
class OptimizationResult:
    success: bool
    message: str = ""
    candidate_payloads: List[Dict[str, Any]] = field(default_factory=list)

def generate_layout_variants(payload: Dict[str, Any]) -> OptimizationResult:
    base = deepcopy(payload)
    variants: List[Dict[str, Any]] = []
    for strategy in ["front_parking", "rear_parking", "side_parking", "grading_friendly", "drainage_friendly"]:
        v = deepcopy(base)
        v["layout_strategy"] = strategy
        variants.append(v)
    return OptimizationResult(success=True, message="Generated optimization variants.", candidate_payloads=variants)
