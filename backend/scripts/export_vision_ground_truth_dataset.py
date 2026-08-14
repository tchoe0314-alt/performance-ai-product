from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.common import safe_dict
from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    build_ground_truth_coverage,
    build_ground_truth_dataset,
    build_privacy_safe_correction_aggregate,
    merge_ground_truth_datasets,
)


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _dataset_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("version") == DATASET_VERSION:
        return payload
    if isinstance(payload.get(DATASET_VERSION), dict):
        return safe_dict(payload.get(DATASET_VERSION))
    project = safe_dict(payload.get("project")) or payload
    project_input = safe_dict(project.get("project_input"))
    input_meta = safe_dict(project_input.get("meta"))
    site_inputs = safe_dict(input_meta.get("site_inputs"))
    latest = safe_dict(project.get("latest_result"))
    final_plan = safe_dict(latest.get("final_plan"))
    final_meta = safe_dict(final_plan.get("meta"))
    meta = {**site_inputs, **final_meta}
    if not meta:
        raise ValueError("Input is not a ground-truth dataset, vision-learning export, or Civora project record.")
    return build_ground_truth_dataset(meta)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge reviewed Civora vision labels while preserving immutable provenance and permanent frame splits."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Project exports or ground-truth dataset JSON files.")
    parser.add_argument("--output", type=Path, required=True, help="Destination aggregate dataset JSON.")
    parser.add_argument("--coverage-output", type=Path, help="Optional destination coverage report JSON.")
    parser.add_argument(
        "--privacy-aggregate-output",
        type=Path,
        help="Optional count-only correction telemetry JSON with no imagery, geometry, locations, or identifiers.",
    )
    parser.add_argument(
        "--learning-consent",
        action="append",
        default=[],
        type=Path,
        help="Consent JSON bound to a source dataset fingerprint. Repeat for each data owner/package.",
    )
    parser.add_argument("--allow-blocked", action="store_true", help="Write a blocked package instead of returning exit code 2.")
    args = parser.parse_args()

    datasets = [_dataset_from_payload(_read_json(path)) for path in args.inputs]
    consents = [_read_json(path) for path in args.learning_consent]
    aggregate = merge_ground_truth_datasets(datasets, learning_consents=consents)
    coverage = build_ground_truth_coverage(aggregate)
    privacy_aggregate = build_privacy_safe_correction_aggregate([aggregate])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.coverage_output:
        args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
        args.coverage_output.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.privacy_aggregate_output:
        args.privacy_aggregate_output.parent.mkdir(parents=True, exist_ok=True)
        args.privacy_aggregate_output.write_text(
            json.dumps(privacy_aggregate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "success": aggregate.get("export_ready") is True,
                "dataset_fingerprint": aggregate.get("dataset_fingerprint"),
                "annotation_count": aggregate.get("annotation_count"),
                "counts_by_split": aggregate.get("counts_by_split"),
                "blocked_classes": coverage.get("blocked_classes"),
                "blockers": aggregate.get("export_blockers"),
                "learning_consent_ready": coverage.get("learning_consent_ready"),
                "privacy_safe_aggregate_valid": (
                    coverage.get("privacy_safe_aggregate_validation") or {}
                ).get("valid"),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if aggregate.get("export_ready") is True or args.allow_blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
