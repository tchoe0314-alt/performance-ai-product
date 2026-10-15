"""Read-only application audit; new local evidence only, no repairs or services.

Pure assertion audit hook reused from P01. Original selected unittest bodies execute
with main/startup code excluded; selected TIN tests omit provider-dependent imports.
This is not whole-suite/browser or independent professional acceptance.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests/remediation")); sys.path.insert(0, str(ROOT))
from p01_evidence import encoded, publish_bundle, readonly_assertions, sha, verify_bundle
# Reviewed pure imports preload the static repository object-definition JSON only.
from test_p02 import CompatibilityTests
from backend.services.canonical_canvas import resolve_canvas_input, with_canvas_snapshot
from backend.services.canonical_project import ProjectDocumentError
from backend.services.canonical_record import OWNER

BASELINE = "ab7db888e85fb9b6125551ecff769d08e0ca7322"


class Followup(unittest.TestCase):
    def run(self, result=None):
        with readonly_assertions(): return super().run(result)
    def invalid_hydrology(self, area=2, c=.8, intensity=4):
        from engines.hydrology_engine import RationalArea, compute_rational_method
        try: result = compute_rational_method([RationalArea("SYNTHETIC", area, c, intensity)])
        except (ValueError, TypeError): return
        self.assertFalse(result.success, f"Invalid input accepted: {result}")
    def test_E01_negative_rainfall(self): self.invalid_hydrology(intensity=-1)
    def test_E02_infinite_rainfall(self): self.invalid_hydrology(intensity=float("inf"))
    def test_E03_boolean_area(self): self.invalid_hydrology(area=True)
    def test_E04_negative_runoff_coefficient(self): self.invalid_hydrology(c=-.1)
    def test_E05_stage_storage_must_not_decrease(self):
        from engines.detention_engine import BasinGeometry, generate_stage_storage_curve
        curve = generate_stage_storage_curve(BasinGeometry(100, 20, 5.01, 4))
        self.assertTrue(all(b.storage_cf >= a.storage_cf for a, b in zip(curve, curve[1:])),
                        f"Terminal storage decreased: {[(p.elevation,p.storage_cf) for p in curve[-2:]]}")
    def test_E06_routing_must_not_hide_excess_storage(self):
        from engines.detention_engine import BasinGeometry, generate_stage_storage_curve, route_detention_level_pool
        curve = generate_stage_storage_curve(BasinGeometry(100, 20, 5, 4))
        # Zero outlet, huge constant inflow: a supported result cannot silently cap
        # elevation with excess stored water and no overflow/unsupported indication.
        try: rows = route_detention_level_pool([(0,100),(1,100)], curve, outlet_area_sf=0)
        except (ValueError, TypeError): return
        last = rows[-1]
        self.assertFalse(last.storage_cf > curve[-1].storage_cf and last.water_surface_elev_ft <= curve[-1].elevation,
                         f"storage={last.storage_cf}, curve_max={curve[-1].storage_cf}, capped_stage={last.water_surface_elev_ft}")
    def surfaces(self, shift=0):
        from engines.surface_engine import GridSurface
        return GridSurface(0,0,20,20,10,3,3,[[100.]*3 for _ in range(3)]), GridSurface(shift,0,shift+20,20,10,3,3,[[101.]*3 for _ in range(3)])
    def test_E07_grading_independent_uniform_volume(self):
        from engines.grading_engine import GradingEngine
        existing, proposed = self.surfaces()
        self.assertAlmostEqual(GradingEngine(existing)._compute_earthwork(proposed)[1], 400, places=6)
    def test_E08_surface_helper_independent_uniform_volume(self):
        from engines.surface_engine import compare_surfaces
        self.assertAlmostEqual(compare_surfaces(*self.surfaces())["fill_cf"], 400, places=6)
    def test_E09_surface_helper_must_reject_shifted_domain(self):
        from engines.surface_engine import compare_surfaces
        try: result = compare_surfaces(*self.surfaces(1000))
        except (ValueError, TypeError): return
        self.assertTrue(result.get("success") is False or bool(result.get("errors")), "Unrelated spatial domains compared as aligned")
    def test_E10_boolean_model_adapter_version_rejected(self):
        inputs = CompatibilityTests().sealed()["project_input"]
        inputs["canonical_project_v1"]["extensions"][OWNER]["version"] = True
        with self.assertRaises(ProjectDocumentError): resolve_canvas_input(inputs)
    def test_E11_explicit_stale_revision_positive_control(self):
        from backend.services.project_revision import check_revision, ProjectRevisionConflict
        with self.assertRaises(ProjectRevisionConflict): check_revision({"project_input":{}}, "wrong-revision")
    def test_E12_boolean_canvas_version_positive_control(self):
        inputs = with_canvas_snapshot(CompatibilityTests().legacy())
        inputs["canonical_project_v1"]["extensions"]["canvas_workspace_v1"]["version"] = True
        with self.assertRaises(ProjectDocumentError): resolve_canvas_input(inputs)


class Recorder(unittest.TextTestResult):
    def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs); self.rows=[]
    def addSuccess(self,test): super().addSuccess(test); self.rows.append({"test":test.id(),"status":"PASS"})
    def addFailure(self,test,err): super().addFailure(test,err); self.rows.append({"test":test.id(),"status":"FAIL","detail":self._exc_info_to_string(err,test)})
    def addError(self,test,err): super().addError(test,err); self.rows.append({"test":test.id(),"status":"ERROR","detail":self._exc_info_to_string(err,test)})


def selected_original_tests(relative, class_name, *, select=None, exclude_import=None):
    """Use actual existing test bodies; no expectation changes or pytest fixtures."""
    tree = ast.parse((ROOT/relative).read_text(encoding="utf-8-sig"), filename=relative)
    nodes=[]
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            if exclude_import and isinstance(node,ast.ImportFrom) and node.module==exclude_import: continue
            nodes.append(node)
        elif isinstance(node,ast.ClassDef) and node.name==class_name: nodes.append(node)
    namespace={"__name__":"audit_selected_"+class_name,"__file__":str(ROOT/relative)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(ROOT/relative),"exec"),namespace)
    cls=namespace[class_name]
    # Tests execute behind same guard as imports. Dynamic subclass adds no behavior changes.
    class Guarded(cls):
        def run(self,result=None):
            with readonly_assertions(): return super().run(result)
    names=select or unittest.defaultTestLoader.getTestCaseNames(cls)
    return unittest.TestSuite(Guarded(name) for name in names)


def suite_report(suite):
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recorder).run(suite)
    return {"tests":result.testsRun,"passed":result.testsRun-len(result.failures)-len(result.errors),
            "failed":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "exit_code":0 if result.wasSuccessful() else 1,"cases":result.rows}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}",args.run_id):raise ValueError("Unsafe run ID")
    if (HERE/"evidence"/args.run_id).exists():raise FileExistsError("Do not overwrite an evidence run")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    if head!="ef22d42c4647e15cd0d6815b9d3816702cf9dbb4":raise RuntimeError("Reconcile changed candidate first")
    tracked_dirty=subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True).strip()
    if tracked_dirty:raise RuntimeError("Preserve/reconcile tracked changes first")
    previous=ROOT/"docs/release/p01/evidence/p01-20261015-03"
    verify_bundle(previous,expected_source_sha=BASELINE,expected_manifest_sha="c3dbaba66d3db25d1f602ca0afed595a1dee767f6a1cbfd97fa65b079962c8f9")
    sources=json.loads((previous/"source_inventory.json").read_text())["files"]
    for row in sources:
        if sha((ROOT/row["path"]).read_bytes())!=row["sha256"]:raise RuntimeError("Application source changed: "+row["path"])
    test_files=sorted((ROOT/"tests").glob("test_*.py"))
    test_inventory=[]
    for p in test_files:
        tree=ast.parse(p.read_text(encoding="utf-8-sig"))
        tests=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test_")]
        test_inventory.append({"source":str(p.relative_to(ROOT)),"sha256":sha(p.read_bytes()),"test_functions":len(tests),
                               "fixture_or_parameter_dependent":sum(bool(n.args.args and n.args.args[0].arg!="self") for n in tests),
                               "status":"DISCOVERED_STATICALLY_NOT_FULL_SUITE_EXECUTED"})
    log=io.StringIO()
    with redirect_stderr(log),redirect_stdout(log):
        extra=suite_report(unittest.defaultTestLoader.loadTestsFromTestCase(Followup))
        with readonly_assertions():
            real=selected_original_tests("tests/test_real_math_big_pass.py","RealMathBigPassTests")
            tin=selected_original_tests("tests/test_tin_surface_engine.py","TinSurfaceEngineTests",
                  select=["test_tin_interpolates_triangle_plane_and_generates_artifacts","test_breaklines_are_sampled_and_boundary_clips_tin","test_surface_comparison_reports_cut_fill_cells"],
                  exclude_import="backend.planning.grading_support")
        existing=suite_report(unittest.TestSuite([real,tin]))
    historical={"status":"NOT AVAILABLE"}
    old=Path("/tmp/civora-full-browser-20261014.xml")
    if old.is_file():
        raw=old.read_bytes()
        if sha(raw)=="be9bf0d3912af0ff7c3e51934807c19de213b3cc3e310d23e1bf6addcd5df99c":
            xml=ET.fromstring(raw);cases=list(xml.iter("testcase"))
            clean=lambda s: re.sub(r"[\w.+-]+@[\w.-]+", "<redacted-email>",s)[:260]
            def failed_row(c):
                fail=c.find("failure")
                if fail is None:fail=c.find("error")
                text=re.sub(r"\x1b\[[0-9;]*m","",fail.text or "")
                status=re.search(r"Expected:\s*200\s+Received:\s*429",text)
                return {"class":clean(c.attrib.get("classname","")),"name":clean(c.attrib.get("name","")),
                        "historical_failure_signal":"ACCOUNT_SETUP_HTTP_429" if status else "NEEDS_CASE_TRIAGE_NO_ROOT_CAUSE_ASSUMED"}
            historical={"status":"HISTORICAL_NOT_RERUN","sha256":sha(raw),"tests":len(cases),
                        "failed":[failed_row(c) for c in cases if c.find("failure") is not None or c.find("error") is not None],
                        "skipped":[{"class":clean(c.attrib.get("classname","")),"name":clean(c.attrib.get("name",""))} for c in cases if c.find("skipped") is not None]}
        else:historical={"status":"HASH_MISMATCH_NOT_REINTERPRETED","sha256":sha(raw)}
    for row in sources:
        if sha((ROOT/row["path"]).read_bytes())!=row["sha256"]:raise RuntimeError("Source changed during audit")
    inputs=[HERE/"run_audit.py",ROOT/"tests/test_real_math_big_pass.py",ROOT/"tests/test_tin_surface_engine.py",ROOT/"tests/remediation/test_p02.py"]
    metadata={"application_revision":BASELINE,"checkout_revision":head,"timestamp_utc":datetime.now(timezone.utc).isoformat(),
              "scope":"Failure-focused repository audit + selected pure offline verification; not complete runtime/live audit", "repairs":"NONE"}
    artifacts={"expanded_probes.json":encoded(extra),"selected_existing_tests.json":encoded(existing),"verification.log":log.getvalue().encode(),
               "test_discovery.json":encoded({"files":test_inventory,"test_functions":sum(r["test_functions"] for r in test_inventory),
                  "browser_spec_files":len(list((ROOT/"apps/web/tests").rglob("*.spec.ts")))}),
               "historical_browser_failures.json":encoded(historical),
               "inputs.json":encoded({"unchanged_application_source_files":len(sources),"inputs":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p.read_bytes())} for p in inputs],
                    "source_inventory_anchor":"c3dbaba66d3db25d1f602ca0afed595a1dee767f6a1cbfd97fa65b079962c8f9",
                    "guard_limit":"Reviewed pure Python audit hook, not a hostile-code OS sandbox; no API/DB/browser startup"})}
    digest=publish_bundle(HERE/"evidence",args.run_id,artifacts,metadata)
    verify_bundle(HERE/"evidence"/args.run_id,expected_source_sha=BASELINE,expected_manifest_sha=digest)
    print(json.dumps({"manifest_sha256":digest,"expanded":{k:v for k,v in extra.items() if k!="cases"},
                     "selected_existing":{k:v for k,v in existing.items() if k!="cases"},"python_test_files":len(test_files),
                     "test_functions":sum(r["test_functions"] for r in test_inventory),"historical_browser":historical["status"]},indent=2))
    return int(bool(extra["exit_code"] or existing["exit_code"]))


if __name__=="__main__":raise SystemExit(main())
