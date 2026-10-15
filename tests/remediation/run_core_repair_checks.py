"""Create-only offline repair evidence. Does not certify release/PE acceptance."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(ROOT))
from p01_evidence import encoded, publish_bundle, verify_bundle
from test_oct15_audit import run_audit
from test_core_repairs import run_tests
from test_p02 import CompatibilityTests
from test_outbound_http_security import OutboundSecurityTests
from test_session_security import SessionSecurityTests
from test_numerical_repair_contracts import NumericalRepairContracts
from test_email_delivery import EmailDeliveryTests


def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


def fingerprint():
    paths=[p for p in git("ls-files").splitlines() if p.endswith(".py") or p=="core/data/site_object_definitions_v1.json"]
    paths+= [str(p.relative_to(ROOT)) for p in (HERE/"test_core_repairs.py",HERE/Path(__file__).name)]
    rows=[(p,hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in sorted(set(paths))]
    return {"files":len(rows),"sha256":hashlib.sha256(encoded(rows)).hexdigest()}


def summary(result):
    return {"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"passed":result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args()
    import re
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}",args.run_id):raise ValueError("Invalid run ID")
    target=ROOT/"docs/remediation/core-repair-evidence"
    if (target/args.run_id).exists():raise FileExistsError("Evidence already exists")
    head=git("rev-parse","HEAD"); before=fingerprint(); log=io.StringIO()
    with redirect_stderr(log),redirect_stdout(log):
        original=run_audit(); core=run_tests()
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in
            (CompatibilityTests,OutboundSecurityTests,SessionSecurityTests,NumericalRepairContracts,EmailDeliveryTests))
        additional=unittest.TextTestRunner(verbosity=2).run(suite)
    if fingerprint()!=before or git("rev-parse","HEAD")!=head:raise RuntimeError("Candidate changed during checks")
    lanes={"original_reconstructed_audit":original,"core":summary(core),"additional":summary(additional)}
    metadata={"application_revision":head,"branch":git("branch","--show-current"),"timestamp_utc":datetime.now(timezone.utc).isoformat(),
        "python_source_fingerprint":before,"scope":"Synthetic offline focused checks; no release/engineering/security certification",
        "working_tree_status":git("status","--short"),"gate_disposition":"FULL AUDIT STILL OPEN"}
    digest=publish_bundle(target,args.run_id,{"results.json":encoded(lanes),"verification.log":log.getvalue().encode()},metadata)
    verify_bundle(target/args.run_id,expected_source_sha=head,expected_manifest_sha=digest)
    print(json.dumps({"run_id":args.run_id,"manifest_sha256":digest,"original":{k:original[k] for k in ("tests","passed","failed","errors","skipped")},"core":summary(core),"additional":summary(additional)},indent=2))
    return int(bool(original["exit_code"] or not core.wasSuccessful() or not additional.wasSuccessful()))


if __name__=="__main__":raise SystemExit(main())
