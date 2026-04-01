
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class ExplainResult:
    success: bool
    summary: str = ""
    bullets: List[str] = field(default_factory=list)

def explain_plan(plan: Dict[str, Any]) -> ExplainResult:
    meta = plan.get("meta") or {}
    layout_decisions = meta.get("layout_decisions") or {}
    bullets = []
    if layout_decisions.get("strategy"):
        bullets.append(f"Layout strategy: {layout_decisions['strategy']}.")
    if layout_decisions.get("parking_actual") is not None:
        bullets.append(f"Concept parking count: {layout_decisions['parking_actual']}.")
    if meta.get("qa"):
        bullets.append("QA metadata is attached for issue review.")
    return ExplainResult(success=True, summary="Generated explanation for the plan.", bullets=bullets)
