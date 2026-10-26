"""Offline point-file regressions; synthetic files only, no app/DB/providers."""
import tempfile
import unittest
from pathlib import Path

from backend.planning.existing_conditions_importers import (
    classify_existing_conditions_file, import_survey_csv, import_surface_grid_csv,
)


class TextPointImportTests(unittest.TestCase):
    def test_headered_csv_and_tab_txt_preserve_coordinates(self):
        for delimiter in (",", "\t"):
            with self.subTest(delimiter=delimiter), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "survey.txt"
                path.write_text("\n".join(delimiter.join(row) for row in (
                    ("x", "y", "z"), ("0", "0", "100"), ("220", "0", "102.2"),
                    ("0", "160", "100.8"), ("220", "160", "103"),
                )), encoding="utf-8")
                self.assertTrue(classify_existing_conditions_file(path)["supported"])
                survey = import_survey_csv(path)
                self.assertTrue(survey["success"])
                self.assertEqual(survey["point_count"], 4)
                for point in survey["points"]:
                    self.assertAlmostEqual(point["z"], 100 + .01 * point["x"] + .005 * point["y"])
                self.assertTrue(import_surface_grid_csv(path)["success"])

    def test_nonfinite_and_non_survey_text_cannot_form_terrain(self):
        for text in ("not a survey", "x,y,z\n0,0,NaN\n220,0,Infinity\n0,160,-Infinity\n220,160,103"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.txt"
                path.write_text(text, encoding="utf-8")
                self.assertFalse(import_survey_csv(path)["success"])
                self.assertFalse(import_surface_grid_csv(path)["success"])


if __name__ == "__main__":
    unittest.main()
