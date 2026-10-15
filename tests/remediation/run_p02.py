"""P02 preparation evidence only; retain real P01 product failures and exit1.

No app startup, DB, network, dependency install, migration or engineering repair.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from p01_evidence import encoded, publish_bundle, sha, verify_bundle
from test_oct15_audit import run_audit
from test_p01_evidence import run_integrity
from test_p02 import CompatibilityTests

BASELINE = "ab7db888e85fb9b6125551ecff769d08e0ca7322"
P01 = "ef22d42c4647e15cd0d6815b9d3816702cf9dbb4"
ANCHORS = {
    "p01-20261015-01": "ddd13d740bcef0c4a32a77172a0618234d06ae88b5dfb699d40c29490d56a5a3",
    "p01-20261015-02": "c7fbace2295db4d2784039cea935cabe61431a56c707504f9816c6b63a373577",
    "p01-20261015-03": "c3dbaba66d3db25d1f602ca0afed595a1dee767f6a1cbfd97fa65b079962c8f9",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


class CaseResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.records = []
    def addSuccess(self, test):
        super().addSuccess(test); self.records.append({"case": test._testMethodName, "outcome": "PASS"})
    def addFailure(self, test, err):
        super().addFailure(test, err); self.records.append({"case": test._testMethodName, "outcome": "FAIL", "detail": self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err); self.records.append({"case": test._testMethodName, "outcome": "ERROR", "detail": self._exc_info_to_string(err, test)})


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", required=True); args = parser.parse_args()
    # Validate run identity before touching any output namespace.
    import re
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", args.run_id):
        raise ValueError("Invalid run ID")
    target = ROOT / "docs/remediation/p02/evidence"
    if (target / args.run_id).exists(): raise FileExistsError("Evidence run already exists")
    head = git("rev-parse", "HEAD")
    if head != P01:
        raise RuntimeError("Candidate changed: explicitly reconcile P02 input revision first")
    if git("diff", "--name-only") or git("diff", "--cached", "--name-only"):
        raise RuntimeError("Tracked changes present: preserve and reconcile before execution")
    changed = git("diff", "--name-only", BASELINE, P01).splitlines()
    if len(changed) != 44 or any(not p.startswith(("tests/remediation/", "docs/release/p01/")) for p in changed):
        raise RuntimeError("P01 application scope mismatch")
    for run, digest in ANCHORS.items():
        verify_bundle(ROOT / "docs/release/p01/evidence" / run, expected_source_sha=BASELINE, expected_manifest_sha=digest)
    prior_root = ROOT / "docs/release/p01/evidence/p01-20261015-03"
    prior = json.loads((prior_root / "source_and_configuration.json").read_text())
    inventory = json.loads((prior_root / "source_inventory.json").read_text())
    protected = prior["planning_documents_preserved"] + prior["harness"] + prior["configuration_and_dependencies"] + inventory["files"]
    for row in protected:
        if sha((ROOT / row["path"]).read_bytes()) != row["sha256"]:
            raise RuntimeError("Protected source/evidence input changed: " + row["path"])
    # Explicitly fingerprint new synthetic fixtures, inspected source catalog and draft decisions.
    paths = [HERE / "test_p02.py", HERE / "run_p02.py", ROOT / "core/data/site_object_definitions_v1.json"]
    paths += sorted((HERE / "fixtures").glob("p02_*.json"))
    paths += [p for p in sorted((ROOT / "docs/remediation/p02").glob("*.md")) if p.name != "P02_PREPARATION_STATUS.md"]
    inputs = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size} for p in paths]
    log = io.StringIO()
    with redirect_stderr(log), redirect_stdout(log):
        integrity = run_integrity()
        compatible = unittest.TextTestRunner(verbosity=2, resultclass=CaseResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompatibilityTests))
        audit = run_audit()
    for row in protected + inputs:
        if sha((ROOT / row["path"]).read_bytes()) != row["sha256"]:
            raise RuntimeError("Input changed during execution: " + row["path"])
    if git("rev-parse", "HEAD") != head: raise RuntimeError("HEAD changed during execution")
    contracts = {"tests": compatible.testsRun, "passed": compatible.testsRun-len(compatible.failures)-len(compatible.errors),
                 "failed": len(compatible.failures), "errors": len(compatible.errors), "skipped": len(compatible.skipped),
                 "exit_code": 0 if compatible.wasSuccessful() else 1, "cases": compatible.records,
                 "scope": "Pure current Python compatibility gateways; C25 static TS section comparison only"}
    metadata = {"application_revision": BASELINE, "checkout_revision": head, "branch": git("branch", "--show-current"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                "authorization": "Internal P01 review and P02 drafts/compatibility preparation only",
                "professional_validation": "PENDING; not supplied by self-review", "application_changes": "NONE",
                "network_production_payments_customer_data": "NOT ACCESSED", "gate_disposition": "NO GATE PASSED"}
    artifacts = {"compatibility_results.json": encoded(contracts), "p01_integrity_results.json": encoded(integrity),
                 "p01_fresh_product_assertions.json": encoded(audit), "verification.log": log.getvalue().encode(),
                 "inputs.json": encoded({"p02_inputs": inputs, "p01_anchors": ANCHORS,
                     "outcome_document_excluded_from_test_inputs": "P02_PREPARATION_STATUS.md is written after evidence; it is not tested application/harness/decision input",
                     "protected_source_and_planning_count": len(protected), "protected_hashes_unchanged": True,
                     "static_type_catalog_preload": "Reviewed pure import reads repository core/data/site_object_definitions_v1.json, not customer data",
                     "full_application_runtime_integration": "NOT TESTED"})}
    digest = publish_bundle(target, args.run_id, artifacts, metadata)
    verify_bundle(target / args.run_id, expected_source_sha=BASELINE, expected_manifest_sha=digest)
    print(json.dumps({"run_id": args.run_id, "manifest_sha256": digest, "bundle_verified": True,
                      "compatibility": {k: v for k, v in contracts.items() if k != "cases"}, "integrity": integrity,
                      "product": {k: audit[k] for k in ("tests", "passed", "failed", "errors", "skipped", "exit_code")}}, indent=2))
    return int(bool(audit["exit_code"] or integrity["exit_code"] or contracts["exit_code"]))


if __name__ == "__main__":
    raise SystemExit(main())
