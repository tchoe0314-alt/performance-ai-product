import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.artifact_service import ArtifactService


class ArtifactServiceTest(unittest.TestCase):
    def test_build_preview_png_reuses_cached_render(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_name": "Cache Demo",
                "units": "ft",
                "actions": [{"task": "rectangle", "layer": "BUILDING", "x": 0, "y": 0, "width": 10, "height": 10}],
            }

            with patch(
                "backend.services.artifact_service.render_plan_preview_png",
                return_value=b"preview-bytes",
            ) as render_mock:
                first = service.build_preview_png(final_plan)
                second = service.build_preview_png(final_plan)

            self.assertEqual(first, b"preview-bytes")
            self.assertEqual(second, b"preview-bytes")
            self.assertEqual(render_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
