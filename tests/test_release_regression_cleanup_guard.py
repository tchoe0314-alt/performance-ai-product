import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseCleanupGuardTests(unittest.TestCase):
    def run_guard(self, target):
        env = {**os.environ, "NEXT_RELEASE_DIST_DIR": target}
        return subprocess.run(["bash", str(ROOT / "scripts/release_regression.sh")], env=env, capture_output=True, text=True, timeout=5)

    def test_broad_traversal_and_absolute_targets_fail_before_running_steps(self):
        for target in (".", "..", "../..", "/", "../../data", ".next-release-regression-../data", ".next-release-regression-safe/../../data"):
            with self.subTest(target=target):
                result = self.run_guard(target)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Invalid release output directory", result.stderr)
                self.assertNotIn("[run]", result.stdout)

    def test_existing_directory_and_its_contents_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix=".next-release-regression-guard-", dir=ROOT / "apps/web") as directory:
            sentinel = Path(directory) / "user-work.txt"
            sentinel.write_text("preserve existing work")
            result = self.run_guard(Path(directory).name)
            self.assertEqual(result.returncode, 2)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(sentinel.read_text(), "preserve existing work")

    def test_existing_symlink_is_not_followed_or_deleted(self):
        with tempfile.TemporaryDirectory(prefix=".next-release-regression-guard-", dir=ROOT / "apps/web") as directory:
            link = Path(directory + "-link")
            link.symlink_to(directory, target_is_directory=True)
            try:
                result = self.run_guard(link.name)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(link.is_symlink())
                self.assertTrue(Path(directory).is_dir())
            finally:
                link.unlink()


if __name__ == "__main__":
    unittest.main()
