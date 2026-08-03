from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.planning.vision_public_bootstrap import build_public_review_sprint


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a verified public weak-supervision package into a zero-ground-truth Civora review sprint."
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = _read_object(args.package)
    sprint = build_public_review_sprint(package)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "imagery_frames": sprint["imagery_frame_count"],
                "pending_candidates": sprint["pending_candidate_count"],
                "ground_truth_annotations": sprint["ground_truth_annotation_count"],
                "promotion_eligible": False,
            },
            indent=2,
        )
    )
    return 0


def _read_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Package is missing or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit("Package must contain a JSON object.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
