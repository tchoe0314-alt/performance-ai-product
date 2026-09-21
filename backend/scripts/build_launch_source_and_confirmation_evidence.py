from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.major_change_confirmation import build_confirmation_evidence
from backend.application.source_infrastructure_evidence import build_source_infrastructure_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic source-inventory and major-change confirmation evidence.")
    parser.add_argument("--rights-review", default="reports/release/source-rights-review.json")
    parser.add_argument("--source-output", default="reports/release/source-infrastructure-evidence.json")
    parser.add_argument("--confirmation-output", default="reports/release/major-change-confirmation-evidence.json")
    parser.add_argument("--confirmation-tests-passed", action="store_true")
    parser.add_argument("--integration-evidence", default="reports/release/major-change-integration-evidence.json")
    args = parser.parse_args()
    rights_path = (ROOT / args.rights_review).resolve()
    rights = json.loads(rights_path.read_text(encoding="utf-8")) if rights_path.is_file() else {}
    source = build_source_infrastructure_evidence(rights_review=rights)
    integration_path = (ROOT / args.integration_evidence).resolve()
    integration = json.loads(integration_path.read_text(encoding="utf-8")) if integration_path.is_file() else {}
    confirmation = build_confirmation_evidence(
        tests_passed=args.confirmation_tests_passed,
        integrated_actions=integration.get("integrated_actions") or [],
        browser_verified_actions=integration.get("browser_verified_actions") or [],
    )
    for path_value, payload in ((args.source_output, source), (args.confirmation_output, confirmation)):
        path = (ROOT / path_value).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"markets": source["market_count"], "queryable_sources": source["queryable_source_count"], "rights_review_recorded": bool(rights), "confirmation_action_count": len(confirmation["covered_actions"]), "confirmation_tests_passed": confirmation["tests_passed"], "confirmation_integration_complete": confirmation["integration_complete"], "confirmation_browser_verification_complete": confirmation["browser_verification_complete"]}, sort_keys=True))


if __name__ == "__main__":
    main()
