from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.planning.common import safe_dict
from backend.planning.vision_ai_review_assist import (
    build_ai_assisted_vision_triage,
    render_ai_triage_contact_sheets,
    verify_ai_assisted_vision_triage,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate non-human visual triage recommendations and evidence sheets for a verified public-image "
            "review sprint. This output cannot append ground-truth labels."
        )
    )
    parser.add_argument("--review-sprint", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overrides", type=Path)
    args = parser.parse_args()

    review_sprint = _read_object(args.review_sprint)
    overrides = _read_object(args.overrides) if args.overrides else None
    output_root = args.output_root.expanduser().resolve()
    crop_root = output_root / "crops"
    contact_sheet_root = output_root / "contact-sheets"
    output_root.mkdir(parents=True, exist_ok=True)
    _remove_generated_files(crop_root, "*.png")
    _remove_generated_files(contact_sheet_root, "triage-contact-sheet-*.jpg")

    triage = build_ai_assisted_vision_triage(
        review_sprint,
        image_root=args.image_root,
        crop_root=crop_root,
        overrides=overrides,
    )
    validation = verify_ai_assisted_vision_triage(triage, review_sprint=review_sprint)
    if not validation["valid"]:
        raise ValueError("Generated AI triage failed verification: " + ", ".join(validation["blockers"]))
    contact_sheets = render_ai_triage_contact_sheets(
        triage,
        crop_root=crop_root,
        output_root=contact_sheet_root,
    )
    triage_path = output_root / "ai-assisted-triage.json"
    summary_path = output_root / "triage-summary.json"
    triage_path.write_text(json.dumps(triage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary: Dict[str, Any] = {
        "success": True,
        "status": "recommendations_only_human_review_required",
        "candidate_count": triage["candidate_count"],
        "override_count": triage["override_count"],
        "recommendation_counts": safe_dict(triage.get("recommendation_counts")),
        "review_priority_counts": safe_dict(triage.get("review_priority_counts")),
        "contact_sheet_count": len(contact_sheets),
        "triage_fingerprint": triage["triage_fingerprint"],
        "triage_path": str(triage_path),
        "crop_root": str(crop_root),
        "contact_sheets": contact_sheets,
        "human_attestation_present": False,
        "ground_truth_eligible": False,
        "ledger_append_allowed": False,
        "promotion_eligible": False,
        "next_action": "A human reviewer must inspect each recommendation against its registered source frame.",
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _read_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


def _remove_generated_files(root: Path, pattern: str) -> None:
    if not root.is_dir():
        return
    for path in root.glob(pattern):
        if path.is_file() or path.is_symlink():
            path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
