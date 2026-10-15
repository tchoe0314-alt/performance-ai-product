"""Create a new P01 evidence bundle; exit nonzero for ANY failed product assertion.

Only reads tracked source/planning/historical test reports; writes new package evidence
and a new private historical archive. Never reads .env, initializes app or calls APIs.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p01_evidence import ROOT, encoded, inventory, publish_bundle, sha, tracked_source_paths, verify_bundle
from test_oct15_audit import CASES, run_audit
from test_p01_evidence import run_integrity

BASELINE = "ab7db888e85fb9b6125551ecff769d08e0ca7322"
HISTORICAL = [
    ("/tmp/civora-requested-clean-backend-20261014.xml", "cc1b82d9d336cb085c005bbf5da1c8811d79de329d6035149481d5ce9ace13f6"),
    ("/tmp/civora-full-browser-20261014.xml", "be9bf0d3912af0ff7c3e51934807c19de213b3cc3e310d23e1bf6addcd5df99c"),
    ("/tmp/civora-backend-bandit-20261014.json", "d114accc59528f3ed7c55dbb483a287afb0e88d1431b8757873153781b1fe6d0"),
    ("/tmp/civora-python-dependency-audit-20261014.json", "2578926764c6e8f9f99d0f41c494d1237cdb5976a7295467e3decdb7658cb7a6"),
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def junit(report):
    suite = ET.Element("testsuite", name="P01 reconstructed October15 product assertions", tests=str(report["tests"]),
                       failures=str(report["failed"]), errors=str(report["errors"]), skipped=str(report["skipped"]))
    for row in report["cases"]:
        case = ET.SubElement(suite, "testcase", classname="P01.ReconstructedAudit", name=row["id"])
        if row["outcome"] in {"FAIL", "ERROR"}:
            ET.SubElement(case, "failure" if row["outcome"] == "FAIL" else "error", message=row["expected"]).text = row["detail"]
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def families():
    catalog = json.loads((Path(__file__).parent / "p01_feature_families.json").read_text())
    result = []
    for key, title, source, status, issues, mode in catalog["families"]:
        result.append({"id": key, "feature": title, "source": source, "source_exists": (ROOT / source).is_file(),
                       "implementation_status": "PARTIAL_IMPLEMENTATION" if status == "PARTIAL" else "KNOWN_DEFECT_OR_MISSING_CAPABILITY",
                       "verification_status": status, "enablement_conditions": "Inspect referenced source and configuration-reference records; effective state UNKNOWN; not enabled by P01",
                       "permissions": "Project ownership/role and provider/operator conditions must be separately verified",
                       "units_and_sources": "Engine/source-specific; see engineering validation plan; UNKNOWN unless explicitly provided",
                       "side_effects_and_safe_mode": mode, "expected": "Functioning scope without false engineering/provider claims",
                       "observed": "Code inspection and limited linked A-series assertions only; no full runtime verification",
                       "issues": issues.split(",")})
    # Individual optional/provider/format statuses: existence never means usable or enabled.
    variants = [
        ("provider_openai", "backend/ai/provider.py", "IMPLEMENTED_NOT_VERIFIED", "Real paid provider blocked; fake only", "AI-01,AI-02"),
        ("provider_ollama", "backend/ai/provider.py", "IMPLEMENTED_NOT_VERIFIED", "Optional local service not started", "AI-02"),
        ("provider_disabled", "backend/ai/provider.py", "IMPLEMENTED_NOT_VERIFIED", "Fallback path not executed by P01", "AI-01"),
        ("provider_mapbox", "apps/web/package.json", "IMPLEMENTED_NOT_VERIFIED", "No map/token/API calls; current subscription/config UNKNOWN", "GOV-01"),
        ("provider_arcgis", "backend/planning/gis_provider_registry.py", "PARTIAL_IMPLEMENTATION", "A21 fake loopback transport only", "SEC-01,GOV-01"),
        ("provider_stripe", "backend/services/billing.py", "PLACEHOLDER_STUB", "Charging disabled/status hooks; no sandbox or real payments", "COM-01,COM-02"),
        ("imagery_mock", "backend/application/ai_visualization_workflows.py", "MOCK_MODE_NOT_REAL_PROVIDER_VERIFICATION", "Do not equate mock result with image quality", "AI-02"),
        ("native_dwg", "backend/planning/dwg_compatibility.py", "MISSING_IMPLEMENTATION", "External converter hooks not native writer", "EXP-02"),
        ("native_civil3d", "backend/planning/dwg_compatibility.py", "MISSING_IMPLEMENTATION", "Unsupported native object package", "EXP-02"),
    ]
    for key, source, status, mode, issues in variants:
        row = dict(result[0])
        row.update(id=key, feature=key, source=source, source_exists=(ROOT/source).is_file(), implementation_status=status,
                   verification_status="NOT TESTED" if status == "IMPLEMENTED_NOT_VERIFIED" else "PARTIAL",
                   side_effects_and_safe_mode=mode, issues=issues.split(","))
        result.append(row)
    for fmt in ("csv", "geojson", "geotiff", "las", "landxml", "pdf", "dxf", "json"):
        row = dict(result[0])
        source = "backend/planning/landxml_io.py" if fmt == "landxml" else "backend/planning/existing_conditions_importers.py"
        row.update(id="format_"+fmt, feature="Import/export format " + fmt + " (direction/scope requires source review)", source=source,
                   source_exists=(ROOT/source).is_file(), implementation_status="SOURCE_PRESENT_RUNTIME_UNVERIFIED",
                   verification_status="NOT TESTED", side_effects_and_safe_mode="No files imported/exported; synthetic isolated fixtures later; units/compatibility NOT VERIFIED",
                   issues=["TEST-03", "EXP-01", "ENG-06"])
        row["direction_and_scope"] = {
            "csv": "Survey-point CSV import; not general spreadsheet analysis",
            "geojson": "GIS feature import; JSON extension may represent GeoJSON rather than canonical project",
            "geotiff": "Raster terrain import with optional rasterio/GDAL dependency",
            "las": "Point-cloud import with optional laspy/coordinate metadata requirements; LAZ dependency must be checked",
            "landxml": "Import and review export; advertised units/content limited; see EXP-03",
            "pdf": "Document extraction/context import and drawing/report export; not native editable CAD model",
            "dxf": "Existing-condition geometry import and drawing/calculated exports; external CAD acceptance pending",
            "json": "Structured project/report/account export and GIS JSON imports are distinct contracts",
        }[fmt]
        row["additional_source_evidence"] = {
            "pdf": ["backend/services/artifact_service.py", "backend/application/file_workflows.py"],
            "dxf": ["output/dxf_exporter.py", "backend/application/current_geometry_export.py"],
            "json": ["backend/services/data_lifecycle.py", "backend/services/canonical_project.py"],
        }.get(fmt, [])
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    output = ROOT / "docs/release/p01/evidence"
    if (output / args.run_id).exists():
        raise FileExistsError("Run ID already exists; choose a new run, never overwrite")
    head, branch = git("rev-parse", "HEAD"), git("branch", "--show-current")
    if head != BASELINE:
        # Later commits may include only P01 files; do not silently call a new application baseline original.
        changed = git("diff", "--name-only", BASELINE, "HEAD").splitlines()
        if any(not p.startswith(("tests/remediation/", "docs/release/p01/")) for p in changed):
            raise RuntimeError("Application revision changed; explicitly reconcile a new baseline first")
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    dirty = [line for line in status.splitlines() if not line[3:].strip('"').startswith(("docs/remediation/", "tests/remediation/", "docs/release/p01/"))]
    if dirty:
        raise RuntimeError("Unexpected pre-existing changes; stop and preserve them")
    plans = sorted((ROOT / "docs/remediation").glob("CIVORA_*.md"))
    if len(plans) != 8:
        raise RuntimeError("Expected all eight pre-existing planning documents")
    planning = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size} for p in plans]
    paths = tracked_source_paths()
    scanned = inventory(paths)
    family_records = families()
    config_paths = [p for p in git("ls-files").splitlines() if (
        p.startswith("requirements_") or p.startswith("Dockerfile") or p in {
            "apps/web/package.json", "apps/web/package-lock.json", "apps/web/next.config.ts", "railway.toml",
            "railway.imagery-gateway.toml", "vercel.json", "compose.ai-renderer.yaml", ".env.example"
        } or p.startswith(".github/workflows/"))]
    configs = [{"path": p, "sha256": sha((ROOT/p).read_bytes()), "bytes": (ROOT/p).stat().st_size} for p in config_paths]
    harness = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes())} for p in sorted(Path(__file__).parent.glob("*")) if p.is_file()]
    # Private originals: unique external directory; never committed or printed contents.
    archive_root = ROOT.parent / ".civora-p01-evidence"
    if archive_root.is_symlink():
        raise ValueError("Private archive root must not be a symlink")
    archive_root.mkdir(mode=0o700, exist_ok=True)
    archive = Path(tempfile.mkdtemp(prefix="original-evidence-", dir=archive_root)).resolve()
    archive.chmod(0o700)
    historical = []
    for name, expected_hash in HISTORICAL:
        source = Path(name)
        record = {"source": name, "expected_sha256_from_preflight": expected_hash, "available": source.is_file()}
        if source.is_file():
            raw = source.read_bytes(); record.update(sha256=sha(raw), bytes=len(raw), hash_matches_preflight=sha(raw)==expected_hash)
            if not record["hash_matches_preflight"]:
                raise RuntimeError("Historical artifact changed since preflight; do not overwrite evidence")
            with (archive/source.name).open("xb") as stream: stream.write(raw)
            (archive/source.name).chmod(0o600)
            if source.suffix == ".xml":
                xml = ET.fromstring(raw); cases = list(xml.iter("testcase"))
                record["xml_root_attributes"] = xml.attrib
                record["testcase_counts"] = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                                             "errors": sum(c.find("error") is not None for c in cases), "skipped": sum(c.find("skipped") is not None for c in cases)}
        historical.append(record)
    for source in plans:
        with (archive/source.name).open("xb") as stream: stream.write(source.read_bytes())
        (archive/source.name).chmod(0o600)
    private_record = {"archive_directory": str(archive), "historical": historical, "planning": planning}
    with (archive/"PRIVATE_CUSTODY.json").open("xb") as stream: stream.write(encoded(private_record))
    (archive/"PRIVATE_CUSTODY.json").chmod(0o600)
    logs = io.StringIO()
    with redirect_stdout(logs), redirect_stderr(logs):
        integrity = run_integrity()
        report = run_audit()
    if git("rev-parse", "HEAD") != head:
        raise RuntimeError("HEAD changed during verification; stop")
    changed_inputs = [r["path"] for r in scanned["files"] + configs + planning + harness if sha((ROOT/r["path"]).read_bytes()) != r["sha256"]]
    if changed_inputs:
        raise RuntimeError("Source/evidence inputs changed during verification: " + str(changed_inputs))
    gaps = ["Original complete October15 executable and raw stdout are not available as standalone recovered artifacts",
            "October15 audit supplied in conversation; not a recovered signed/immutable source document",
            "A21 reconstructs check_provider_health with minimal provider record, not full builder/API path",
            "A11 uses synthetic configured intensity4; effective hosted/environment values not accessed",
            "Numeric diagnostic tolerances are reconstruction precision, NOT PE-approved design tolerances",
            "Historical browser XML has701/23fail/0error/15skip versus pasted700/21fail/1error/16skip; cause unknown",
            "External QA/release-engineer acceptance and PE review pending; no release gate passes",
            "Local append-only-by-tool bundles and hashes are not independently protected immutable storage"]
    metadata = {"application_revision": BASELINE, "checkout_head_at_execution": head, "branch": branch,
                "application_baseline_tree": git("rev-parse", BASELINE + "^{tree}"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                "python_executable": sys.executable, "platform": platform.platform(),
                "configuration": "Static declared source fingerprints only; effective/local/production environment not read",
                "paid_apis": "NOT CALLED", "production_customer_storage": "NOT ACCESSED",
                "private_archive": str(archive), "gate_disposition": "NO GATE PASSED"}
    sources = {
        "ENG-01": ["backend/planning/runtime.py::_compute_hydrology_metrics", "backend/planning/common.py", "engines/hydrology_engine.py"],
        "ENG-02": ["engines/hydrology_engine.py::compute_rational_method"],
        "ENG-03": ["engines/detention_engine.py::basin_storage_cf", "engines/detention_engine.py::generate_stage_storage_curve",
                   "engines/detention_engine.py::compute_required_storage_cf", "engines/detention_engine.py::estimate_drawdown_hours"],
        "CAN-01": ["backend/services/canonical_project.py::validate_project_document"],
        "CAN-02": ["backend/services/dependency_graph.py::validate_dependency_graph"],
        "SEC-01": ["backend/planning/gis_provider_registry.py::check_provider_health"],
        "ENG-04": ["engines/earthwork_engine.py::compute_earthwork", "engines/surface_engine.py::GridSurface"],
        "ENG-05": ["engines/earthwork_engine.py::validate_compatible_surfaces"],
        "SEC-02": ["backend/api/app.py::_request_rate_limit_key", "backend/api/app.py::_bearer_token"],
    }
    packages = {"ENG-01": "P03", "ENG-02": "P03", "ENG-03": "P04", "ENG-04": "P06", "ENG-05": "P05",
                "CAN-01": "P02", "CAN-02": "P15", "SEC-01": "P07", "SEC-02": "P08"}
    catalog = [{"id": c[0], "issue": c[1], "input": c[2], "expected": c[3], "reported_original_outcome": c[4],
                "provenance": "reconstructed_from_transcript_and_plan", "original_source_recovered": False,
                "source_functions": sources[c[1]], "repair_or_qualification_package": packages[c[1]],
                "test": "tests/remediation/test_oct15_audit.py::AuditCases.test_" + c[0],
                "acceptance_limit": "Baseline diagnostic, not approved engineering release tolerance or integration proof"} for c in CASES]
    artifacts = {"source_inventory.json": encoded(scanned), "feature_families.json": encoded(family_records),
                 "source_and_configuration.json": encoded({"application_revision": BASELINE, "configuration_and_dependencies": configs,
                     "planning_documents_preserved": planning, "harness": harness, "working_tree_before": status}),
                 "case_catalog.json": encoded(catalog), "audit_results.json": encoded(report), "audit_results.xml": junit(report),
                 "harness_integrity.json": encoded(integrity), "verification.log": logs.getvalue().encode(),
                 "historical_custody.json": encoded({"artifacts": historical, "private_archive": str(archive),
                    "raw_reports_committed": False, "reason": "Raw logs can contain identifiers; preserve privately, publish hashes/counts only"}),
                 "evidence_gaps.json": encoded(gaps)}
    table = ["# P01 feature-family inventory", "", "Static characterization only; no features activated. Full fields and per-entry locators are in the adjacent JSON files.", "",
             "| ID | Capability | Status | Source | Linked issues |", "|---|---|---|---|---|"]
    table.extend(f"| {r['id']} | {r['feature']} | {r['verification_status']} / {r['implementation_status']} | `{r['source']}` | {', '.join(r['issues'])} |" for r in family_records)
    table.extend(["", "Source locators: " + json.dumps(scanned["counts"], sort_keys=True), "",
                  "All discovered locators are NOT TESTED at runtime. Family PARTIAL/FAIL labels describe scoped code/evidence status, not completed end-to-end verification.",
                  "Dynamic constructs and custom UI tags can escape lexical discovery; this is not a claim of 100% feature coverage."])
    artifacts["feature_inventory.md"] = ("\n".join(table) + "\n").encode()
    digest = publish_bundle(output, args.run_id, artifacts, metadata)
    verify_bundle(output/args.run_id, expected_source_sha=BASELINE, expected_manifest_sha=digest)
    result = {"run_id": args.run_id, "manifest_sha256": digest, "bundle_verified": True, "inventory_files": len(paths),
              "inventory_counts": scanned["counts"], "parse_errors": len(scanned["parse_errors"]), "feature_families": len(family_records),
              "missing_family_source": [f["source"] for f in family_records if not f["source_exists"]],
              "audit": {k: report[k] for k in ("tests", "passed", "failed", "errors", "skipped", "exit_code")},
              "harness": integrity, "private_archive": str(archive)}
    print(json.dumps(result, indent=2))
    return 1 if report["exit_code"] or integrity["exit_code"] or scanned["parse_errors"] or result["missing_family_source"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
