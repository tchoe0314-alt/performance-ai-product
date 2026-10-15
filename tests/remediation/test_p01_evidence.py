"""Harness integrity checks; temp outputs only, no application startup."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p01_evidence import encoded, extracted, inventory, publish_bundle, readonly_assertions, verify_bundle
from test_oct15_audit import CASES


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="civora-p01-harness-")
        self.root = Path(self.temp.name).resolve()
        self.digest = publish_bundle(self.root, "one", {"report.json": encoded({"result": "FAIL"})}, {"application_revision": "baseline"})
    def tearDown(self): self.temp.cleanup()
    def verify(self, **kwargs):
        return verify_bundle(self.root / "one", expected_source_sha=kwargs.get("revision", "baseline"), expected_manifest_sha=kwargs.get("anchor", self.digest))
    def test_valid_bundle(self): self.assertEqual(self.verify()["run_id"], "one")
    def test_source_mismatch(self):
        with self.assertRaises(ValueError): self.verify(revision="newer")
    def test_duplicate_run_id(self):
        before = (self.root / "one/report.json").read_bytes()
        with self.assertRaises(FileExistsError): publish_bundle(self.root, "one", {}, {})
        self.assertEqual((self.root / "one/report.json").read_bytes(), before)
    def test_tampered_report(self):
        (self.root / "one/report.json").write_bytes(b"tampered")
        with self.assertRaises(ValueError): self.verify()
    def test_tampered_manifest(self):
        path = self.root / "one/manifest.json"
        value = json.loads(path.read_text()); value["metadata"]["application_revision"] = "newer"
        path.write_bytes(encoded(value))
        with self.assertRaises(ValueError): self.verify()
    def test_wrong_anchor(self):
        with self.assertRaises(ValueError): self.verify(anchor="0" * 64)
    def test_missing_artifact(self):
        (self.root / "one/report.json").unlink()
        with self.assertRaises(ValueError): self.verify()
    def test_extra_artifact(self):
        (self.root / "one/extra").write_text("unexpected")
        with self.assertRaises(ValueError): self.verify()
    def test_symlink_artifact(self):
        (self.root / "one/link").symlink_to(self.root / "one/report.json")
        with self.assertRaises(ValueError): self.verify()
    def test_path_traversal(self):
        for name in ("../outside", "/absolute", "x/../outside", "x\\outside"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                publish_bundle(self.root, "unsafe", {name: b"bad"}, {})
    def test_guard_write(self):
        with readonly_assertions(), self.assertRaises(PermissionError): (self.root / "forbidden").write_text("no")
        self.assertFalse((self.root / "forbidden").exists())
    def test_guard_network(self):
        with readonly_assertions(), self.assertRaises(PermissionError): socket.socket()
    def test_guard_database(self):
        import sqlite3
        with readonly_assertions(), self.assertRaises(PermissionError): sqlite3.connect(":memory:")
    def test_guard_subprocess(self):
        import subprocess
        with readonly_assertions(), self.assertRaises(PermissionError): subprocess.run(["true"])
    def test_case_mapping(self):
        self.assertEqual([c[0] for c in CASES], [f"A{i:02}" for i in range(1, 25)])
        self.assertEqual(sum(c[4] == "FAIL" for c in CASES), 10)
        self.assertEqual(sum(c[4] == "PASS" for c in CASES), 14)
    def test_extraction_does_not_start_app(self):
        ns = extracted("backend/api/app.py", ["_bearer_token"], {})
        self.assertNotIn("app", ns); self.assertEqual(ns["_bearer_token"]("Bearer synthetic"), "synthetic")
    def test_inventory_real_source(self):
        result = inventory(["engines/hydrology_engine.py", "backend/api/app.py"])
        self.assertEqual(result["parse_errors"], [])
        self.assertTrue(any(r["kind"] == "api_route" for r in result["records"]))
        self.assertEqual(result["counts"]["engine_module"], 1)
        self.assertTrue(all(r["verification_status"] == "NOT TESTED" for r in result["records"]))
        self.assertEqual(len({r["id"] for r in result["records"]}), len(result["records"]))
    def test_bom_source_is_not_product_syntax_failure(self):
        result = inventory(["core/config.py", "engines/subdivision_engine.py"])
        self.assertEqual(result["parse_errors"], [])
        self.assertEqual(result["counts"]["engine_module"], 1)


def run_integrity():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests))
    return {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "exit_code": 0 if result.wasSuccessful() else 1,
            "failure_details": [detail for _, detail in result.failures + result.errors]}


if __name__ == "__main__":
    raise SystemExit(run_integrity()["exit_code"])
