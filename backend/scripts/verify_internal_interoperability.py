from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.internal_assurance import build_internal_interoperability_bundle


def _load_plan(path_value: str) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Plan JSON not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("Plan JSON must contain an object.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse, roundtrip, and hash DXF/LandXML artifacts using Civora's internal review contracts.",
    )
    parser.add_argument("--dxf", action="append", default=[])
    parser.add_argument("--landxml", action="append", default=[])
    parser.add_argument("--plan-json", default="")
    parser.add_argument("--output", default="reports/validation/internal-interoperability.json")
    args = parser.parse_args()
    if not args.dxf and not args.landxml:
        raise SystemExit("Provide at least one --dxf or --landxml artifact.")

    bundle = build_internal_interoperability_bundle(
        dxf_paths=args.dxf,
        landxml_paths=args.landxml,
        plan=_load_plan(args.plan_json),
    )
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "local_contract_verified": bundle["local_contract_verified"],
                "format_count": bundle["format_count"],
                "failures": bundle["failures"],
                "bundle_sha256": bundle["bundle_sha256"],
                "output_path": str(output),
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if bundle["local_contract_verified"] else 1)


if __name__ == "__main__":
    main()
