from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import requests


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_v3_readiness import build_vision_v3_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fail-closed Civora Vision V3 evidence and deployment report.")
    parser.add_argument("--evaluation-dataset", type=Path)
    parser.add_argument("--training-dataset", type=Path)
    parser.add_argument("--quality-report", type=Path)
    parser.add_argument("--correction-coverage", type=Path)
    parser.add_argument("--gateway-health-url", default="")
    parser.add_argument("--gateway-health-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--required-class", action="append", default=[])
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()

    health = _read(args.gateway_health_file) if args.gateway_health_file else {}
    if args.gateway_health_url:
        response = requests.get(args.gateway_health_url, timeout=20)
        response.raise_for_status()
        health = response.json()
    report = build_vision_v3_readiness_report(
        evaluation_dataset=_read(args.evaluation_dataset),
        training_dataset=_read(args.training_dataset),
        quality_report=_read(args.quality_report),
        correction_coverage=_read(args.correction_coverage),
        shadow_health=health,
        required_classes=tuple(args.required_class or ["building", "road", "surface_water"]),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["deployment_ready"],
        "status": report["status"],
        "blocker_count": len(report["blockers"]),
        "output": str(args.output),
    }, sort_keys=True))
    return 0 if report["deployment_ready"] or args.allow_blocked else 2


def _read(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
