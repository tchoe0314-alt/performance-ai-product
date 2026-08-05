from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai.hybrid_renderer_engine import build_hybrid_renderer_engine
from backend.application.internal_assurance import build_internal_assurance_bundle


def _load_json(path_value: str) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"JSON evidence file not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"JSON evidence must contain an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a tamper-evident Civora internal assurance bundle without storing credentials.",
    )
    parser.add_argument("--validation-report", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--survey-control-json", default="")
    parser.add_argument("--interop-json", action="append", default=[])
    parser.add_argument("--hosted-report", default="")
    parser.add_argument("--renderer-status-json", default="")
    parser.add_argument("--external-evidence-json", default="")
    parser.add_argument("--output", default="reports/validation/internal-assurance-bundle.json")
    args = parser.parse_args()

    renderer_status = _load_json(args.renderer_status_json)
    if not renderer_status:
        renderer_status = dict(build_hybrid_renderer_engine().status())
    bundle = build_internal_assurance_bundle(
        validation_report=_load_json(args.validation_report),
        artifact_paths=args.artifact,
        survey_control_package=_load_json(args.survey_control_json),
        interoperability_reports=[_load_json(path) for path in args.interop_json],
        hosted_report=_load_json(args.hosted_report),
        renderer_status=renderer_status,
        external_evidence=_load_json(args.external_evidence_json),
    )
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "internal_software_assurance_complete": bundle["internal_software_assurance_complete"],
                "external_evidence_complete": bundle["external_evidence_complete"],
                "bundle_sha256": bundle["bundle_sha256"],
                "output_path": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
