"""24 reconstructed October 15 assertions. Expected values are NOT current output snapshots.

Original executable/transcript is unavailable as a standalone artifact. IDs/order are
reconstruction identifiers, not claimed originals. Normal assertions, no xfail/skip.
Run directly with -I -B; nonzero exit means current product assertions failed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from p01_evidence import ROOT, encoded, extracted, readonly_assertions
sys.path.insert(0, str(ROOT))

CASES = [
    ("A01", "ENG-02", "2 ac, C=.8, I=4 in/hr", "6.4512 cfs", "PASS"),
    ("A02", "ENG-02", "empty catchment list", "0 cfs", "PASS"),
    ("A03", "ENG-02", "-2 ac, C=.8, I=4", "reject invalid input or return success=False", "FAIL"),
    ("A04", "ENG-02", "2 ac, C=1.5, I=4", "reject invalid input or return success=False", "FAIL"),
    ("A05", "ENG-02", "2 ac, C=.8, I=NaN", "reject invalid input or return success=False", "FAIL"),
    ("A06", "ENG-03", "inflow10, release2 cfs, .5 hr", "14400 ft3", "PASS"),
    ("A07", "ENG-03", "14400 ft3, release2 cfs", "2 hr", "PASS"),
    ("A08", "ENG-03", "100x100 ft bottom, 5 ft depth, 4H:1V", "72666.666666667 ft3", "PASS"),
    ("A09", "ENG-03", "100x20 ft bottom, 5 ft depth, 4H:1V", "24666.666666667 ft3", "FAIL"),
    ("A10", "ENG-03", "same rectangular basin direct vs stage-curve endpoint", "consistent storage; separate analytical oracle 24666.666666667 ft3", "FAIL"),
    ("A11", "ENG-01", "208.710325571113 ft square, 21780 ft2 impervious, I=4", "2.52 cfs", "FAIL"),
    ("A12", "ENG-02", "repeat A01", "identical valid result", "PASS"),
    ("A13", "CAN-01", "new canonical synthetic project", "exact JSON roundtrip", "PASS"),
    ("A14", "CAN-01", "extra top-level canonical field", "reject", "PASS"),
    ("A15", "CAN-01", "canonical project.x=NaN", "reject", "PASS"),
    ("A16", "CAN-01", "missing units section", "reject", "PASS"),
    ("A17", "CAN-02", "road a follows cul-de-sac road b", "accept supported dependency", "PASS"),
    ("A18", "CAN-02", "dependency target missing", "reject", "PASS"),
    ("A19", "CAN-02", "a->b->a cycle", "reject", "PASS"),
    ("A20", "CAN-02", "a and b both drive c", "reject", "PASS"),
    ("A21", "SEC-01", "loopback provider URL with recording fake session", "zero outbound transport attempts", "FAIL"),
    ("A22", "ENG-04", "3x3 nodes,10ft spacing,20x20ft bounds,+1ft", "400 ft3 fill", "FAIL"),
    ("A23", "ENG-05", "same grids shifted1000ft", "incompatible", "FAIL"),
    ("A24", "SEC-02", "same IP, arbitrary bearer A vs B", "stable auth throttle identity", "FAIL"),
]


class AuditCases(unittest.TestCase):
    def run(self, result=None):
        with readonly_assertions():
            return super().run(result)

    def hydro(self, area=2, c=.8, intensity=4):
        from engines.hydrology_engine import RationalArea, compute_rational_method
        return compute_rational_method([RationalArea("SYNTHETIC", area, c, intensity)])

    def test_A01(self): self.assertAlmostEqual(self.hydro().total_runoff_cfs, 6.4512, places=8)
    def test_A02(self):
        from engines.hydrology_engine import compute_rational_method
        self.assertEqual(compute_rational_method([]).total_runoff_cfs, 0)

    def invalid_hydro(self, **kwargs):
        try:
            result = self.hydro(**kwargs)
        except (ValueError, TypeError):
            return
        self.assertFalse(result.success, f"invalid input accepted: {result}")

    def test_A03(self): self.invalid_hydro(area=-2)
    def test_A04(self): self.invalid_hydro(c=1.5)
    def test_A05(self): self.invalid_hydro(intensity=float("nan"))
    def test_A06(self):
        from engines.detention_engine import compute_required_storage_cf
        self.assertEqual(compute_required_storage_cf(10, 2, .5), 14400)
    def test_A07(self):
        from engines.detention_engine import estimate_drawdown_hours
        self.assertEqual(estimate_drawdown_hours(14400, 2), 2)
    def test_A08(self):
        from engines.detention_engine import basin_storage_cf
        self.assertAlmostEqual(basin_storage_cf(100, 100, 5, 4), 72666.666666667, places=6)
    def test_A09(self):
        from engines.detention_engine import basin_storage_cf
        self.assertAlmostEqual(basin_storage_cf(100, 20, 5, 4), 24666.666666667, places=6)
    def test_A10(self):
        from engines.detention_engine import BasinGeometry, basin_storage_cf, generate_stage_storage_curve
        curve = generate_stage_storage_curve(BasinGeometry(100, 20, 5, 4))
        self.assertAlmostEqual(basin_storage_cf(100, 20, 5, 4), curve[-1].storage_cf, places=6)
    def test_A11(self):
        from engines.hydrology_engine import RationalArea, compute_rational_method
        ns = {"RationalArea": RationalArea, "compute_rational_method": compute_rational_method,
              "PIPE_INTENSITY_IN_HR": 4.0}
        extracted("backend/planning/common.py", ["safe_float", "safe_dict", "clamp", "rect_area"], ns)
        extracted("backend/planning/runtime.py", ["_lot_area", "_compute_hydrology_metrics"], ns)
        result = ns["_compute_hydrology_metrics"]({"lot": {"w": 208.710325571113, "h": 208.710325571113}},
                                                {"estimated_impervious_area_sf": 21780})
        self.assertAlmostEqual(result["peak_runoff_cfs"], 2.52, places=3)
    def test_A12(self): self.assertEqual(self.hydro(), self.hydro())

    def document(self):
        from backend.services.canonical_project import new_project_document
        return new_project_document(name="SYNTHETIC AUDIT ONLY")
    def validate(self, doc):
        from backend.services.canonical_project import validate_project_document
        return validate_project_document(doc)
    def test_A13(self):
        doc = self.document()
        self.assertEqual(self.validate(json.loads(json.dumps(doc, allow_nan=False))), doc)
    def test_A14(self):
        doc = self.document(); doc["unexpected"] = {}
        with self.assertRaises(ValueError): self.validate(doc)
    def test_A15(self):
        doc = self.document(); doc["project"]["x"] = float("nan")
        with self.assertRaises(ValueError): self.validate(doc)
    def test_A16(self):
        doc = self.document(); del doc["units"]
        with self.assertRaises(ValueError): self.validate(doc)

    def roads(self, edges):
        objects = [{"id": name, "type": "road", "meta": {"cul_de_sac_v1": {"version": 1}}} for name in "abc"]
        for source, target in edges:
            obj = next(o for o in objects if o["id"] == source)
            obj["meta"].setdefault("dependency_links_v1", []).append(
                {"id": source + target, "kind": "road_culdesac", "target_id": target, "policy": "follow"})
        return objects
    def graph(self, edges):
        from backend.services.dependency_graph import validate_dependency_graph
        return validate_dependency_graph(self.roads(edges))
    def test_A17(self): self.graph([("a", "b")])
    def test_A18(self):
        with self.assertRaises(ValueError): self.graph([("a", "missing")])
    def test_A19(self):
        with self.assertRaises(ValueError): self.graph([("a", "b"), ("b", "a")])
    def test_A20(self):
        with self.assertRaises(ValueError): self.graph([("a", "c"), ("b", "c")])
    def test_A21(self):
        attempts = []
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"serviceDescription": "SYNTHETIC"})
        def get(*args, **kwargs):
            attempts.append((args, kwargs)); return response
        fake = SimpleNamespace(get=get)
        ns = {"requests": fake, "_utc_now_iso": lambda: "SYNTHETIC_TIME"}
        extracted("backend/planning/common.py", ["safe_dict", "safe_str", "safe_int", "safe_list"], ns)
        extracted("backend/planning/gis_provider_registry.py", ["check_provider_health"], ns)
        # Minimal provider record, not builder/API execution: documented reconstruction limit.
        ns["check_provider_health"]({"service_url": "http://127.0.0.1:9876/private/FeatureServer", "queryable": True}, session=fake)
        self.assertEqual(len(attempts), 0, "loopback reached recording transport (no network performed)")

    def surfaces(self, shift=0):
        from engines.surface_engine import GridSurface
        return (GridSurface(0, 0, 20, 20, 10, 3, 3, [[100.0] * 3 for _ in range(3)]),
                GridSurface(shift, 0, shift + 20, 20, 10, 3, 3, [[101.0] * 3 for _ in range(3)]))
    def test_A22(self):
        from engines.earthwork_engine import compute_earthwork
        result = compute_earthwork(*self.surfaces(), accepted_surfaces=True, existing_surface_id="EG", proposed_surface_id="FG", include_cell_maps=False)
        self.assertAlmostEqual(result["results"]["fill_cf"], 400, places=6)
    def test_A23(self):
        from engines.earthwork_engine import validate_compatible_surfaces
        self.assertFalse(validate_compatible_surfaces(*self.surfaces(1000))["success"])
    def test_A24(self):
        ns = {"hashlib": hashlib}
        extracted("backend/api/app.py", ["_bearer_token", "_request_rate_limit_key"], ns)
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.9"))
        self.assertEqual(ns["_request_rate_limit_key"](request, "Bearer unvalidated-token-A"),
                         ns["_request_rate_limit_key"](request, "Bearer unvalidated-token-B"))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.records = []
    def record(self, test, status, err=None):
        case = next(row for row in CASES if row[0] == test._testMethodName.removeprefix("test_"))
        self.records.append({"id": case[0], "issue": case[1], "input": case[2], "expected": case[3],
                             "historical_outcome_reported": case[4], "outcome": status,
                             "detail": self._exc_info_to_string(err, test) if err else "Assertion passed",
                             "provenance": "Reconstructed from pasted audit + remediation plan; original executable unavailable"})
    def addSuccess(self, test): super().addSuccess(test); self.record(test, "PASS")
    def addFailure(self, test, err): super().addFailure(test, err); self.record(test, "FAIL", err)
    def addError(self, test, err): super().addError(test, err); self.record(test, "ERROR", err)


def run_audit():
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(AuditCases))
    report = {"format": "p01_reconstructed_assertions_v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "provenance_limit": "24-case mapping reconstructed, not recovered original harness; A21 minimal provider record; A11 fixed synthetic intensity",
              "oracles": {"rational": "1.008*C*I*A", "basin": "L*W*d+s*(L+W)*d^2+(4/3)*s^2*d^3", "earthwork": "20*20*1 ft3"},
              "tests": result.testsRun, "passed": result.testsRun-len(result.failures)-len(result.errors),
              "failed": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "exit_code": 0 if result.wasSuccessful() else 1, "cases": result.records}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--report", type=Path)
    args = parser.parse_args(); report = run_audit()
    if args.report:
        with args.report.open("xb") as stream: stream.write(encoded(report))
    print(json.dumps({k: report[k] for k in ("tests", "passed", "failed", "errors", "skipped", "exit_code")}))
    raise SystemExit(report["exit_code"])
