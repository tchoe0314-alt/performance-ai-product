import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.phase0_inventory import classify, inventory, parse_status


class Phase0InventoryTests(unittest.TestCase):
    def test_sensitive_and_generated_files_are_metadata_only(self):
        for path in (".env.local", "apps/web/.env.production", "config/credentials.json", "server.pem", "private/site.json", "apps/web/.next-phase0-baseline/manifest.json"):
            self.assertNotEqual(classify(path), "source-or-documentation")
        self.assertEqual(classify("apps/web/app/utils/layoutAlternatives.ts"), "source-or-documentation")
        for domain in ("engines", "geometry", "parsers", "review", "vision"):
            self.assertEqual(classify(f"{domain}/example.py"), "source-or-documentation")

    def test_status_preserves_spaces_and_rename_paths(self):
        self.assertEqual(parse_status("R  docs/new name.md\0docs/old name.md\0?? draft\nnotes.txt\0"), [
            {"status": "R ", "path": "docs/new name.md", "original_path": "docs/old name.md"},
            {"status": "??", "path": "draft\nnotes.txt"},
        ])

    def test_inventory_is_read_only_and_fingerprint_tracks_uncommitted_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run(*args):
                return subprocess.check_output(["git", *args], cwd=root)
            run("init", "-q")
            run("config", "user.name", "Inventory Test")
            run("config", "user.email", "inventory@example.invalid")
            (root / "app.ts").write_text("initial\n")
            (root / ".env").write_text("DO_NOT_RECORD=private_value\n")
            (root / ".gitignore").write_text(".env\n")
            run("add", "app.ts", ".gitignore")
            run("commit", "-qm", "fixture")
            original_head = run("rev-parse", "HEAD")
            first = inventory(root)
            (root / "app.ts").write_text("changed\n")
            (root / "uncommitted.ts").write_text("new\n")
            before = run("status", "--porcelain=v1", "-z")
            second = inventory(root)
            self.assertEqual(before, run("status", "--porcelain=v1", "-z"))
            self.assertEqual(original_head, run("rev-parse", "HEAD"))
            self.assertNotEqual(first["source_fingerprint_sha256"], second["source_fingerprint_sha256"])
            self.assertIn("uncommitted.ts", [row["path"] for row in second["files"]])
            self.assertNotIn("private_value", json.dumps(second))
            self.assertTrue(all("initial" not in row and "changed" not in row for row in second["files"]))

    def test_unique_branch_patches_are_not_mistaken_for_integrated_features(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run(*args):
                return subprocess.check_output(["git", *args], cwd=root)
            run("init", "-q")
            run("config", "user.name", "Inventory Test")
            run("config", "user.email", "inventory@example.invalid")
            (root / "app.ts").write_text("initial\n")
            run("add", "app.ts")
            run("commit", "-qm", "base")
            base = run("rev-parse", "HEAD").decode().strip()
            run("checkout", "-qb", "experiment")
            (root / "app.ts").write_text("experiment\n")
            run("commit", "-qam", "experiment")
            experiment_sha = run("rev-parse", "HEAD").decode().strip()
            run("checkout", "-q", "--detach", base)
            report = inventory(root)
            branch = next(item for item in report["local_branches"] if item["name"] == "experiment")
            self.assertFalse(branch["contained_in_head"])
            self.assertEqual(branch["patch_comparison"], [{"commit": experiment_sha, "equivalent_patch_in_head": False}])


if __name__ == "__main__":
    unittest.main()
