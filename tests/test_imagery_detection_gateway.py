import os
import unittest
from unittest.mock import patch

from backend.scripts.imagery_detection_gateway import (
    build_mapbox_static_image_url,
    normalize_generic_response,
    normalize_roboflow_response,
    run_detection_gateway,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _GenericSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _Response(
            {
                "detections": [
                    {"kind": "building", "bbox": [10, 20, 30, 40], "confidence": 0.84},
                    {"kind": "parking lot", "bbox": [50, 60, 70, 80], "confidence": 0.72},
                ]
            }
        )


class _RoboflowSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _Response(
            {
                "predictions": [
                    {"class": "building roof", "x": 25, "y": 30, "width": 20, "height": 10, "confidence": 0.91},
                    {
                        "class": "tree canopy",
                        "confidence": 0.62,
                        "points": [{"x": 1, "y": 1}, {"x": 4, "y": 1}, {"x": 4, "y": 3}],
                    },
                ]
            }
        )


class ImageryDetectionGatewayTests(unittest.TestCase):
    def test_mapbox_static_url_uses_active_site_boundary_bbox(self) -> None:
        url = build_mapbox_static_image_url(
            {"active_site_boundary": {"west": -96.2, "south": 41.1, "east": -96.1, "north": 41.2}},
            token="token-123",
            style="mapbox/satellite-v9",
            size="1024x768",
        )

        self.assertIn("mapbox/satellite-v9/static/[-96.2,41.1,-96.1,41.2]/1024x768", url)
        self.assertIn("access_token=token-123", url)

    def test_roboflow_predictions_normalize_to_civora_kinds(self) -> None:
        detections = normalize_roboflow_response(
            {
                "predictions": [
                    {"class": "building roof", "x": 25, "y": 30, "width": 20, "height": 10, "confidence": 0.91},
                    {"class": "tree canopy", "confidence": 0.62, "points": [{"x": 1, "y": 1}, {"x": 4, "y": 1}, {"x": 4, "y": 3}]},
                ]
            },
            source_url="https://source.example/image.png",
        )

        self.assertEqual(detections[0]["kind"], "building")
        self.assertEqual(detections[0]["bbox"], [15.0, 25.0, 20.0, 10.0])
        self.assertEqual(detections[1]["kind"], "tree")
        self.assertEqual(detections[1]["geometry"]["type"], "Polygon")

    def test_generic_predictions_normalize_common_labels(self) -> None:
        detections = normalize_generic_response(
            {"objects": [{"label": "parking stall field", "bbox": [1, 2, 3, 4], "confidence": 0.7}]},
            source_url="https://source.example/image.png",
            provider="generic",
        )

        self.assertEqual(detections[0]["kind"], "parking")
        self.assertEqual(detections[0]["source_url"], "https://source.example/image.png")

    def test_gateway_calls_generic_detector_with_mapbox_source_image(self) -> None:
        session = _GenericSession()
        with patch.dict(
            os.environ,
            {
                "CIVORA_GATEWAY_DETECTOR_KIND": "generic",
                "CIVORA_GATEWAY_GENERIC_DETECTOR_URL": "https://detector.example/detect",
                "CIVORA_GATEWAY_GENERIC_DETECTOR_TOKEN": "detector-token",
                "CIVORA_GATEWAY_MAPBOX_TOKEN": "mapbox-token",
            },
            clear=False,
        ):
            result = run_detection_gateway(
                {"bbox": {"west": -96.2, "south": 41.1, "east": -96.1, "north": 41.2}},
                session=session,
            )

        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["detection_count"], 2)
        self.assertEqual(result["detections"][0]["kind"], "building")
        self.assertIn("api.mapbox.com", session.calls[0]["json"]["image_url"])
        self.assertEqual(session.calls[0]["headers"]["Authorization"], "Bearer detector-token")

    def test_gateway_calls_roboflow_detector(self) -> None:
        session = _RoboflowSession()
        with patch.dict(
            os.environ,
            {
                "CIVORA_GATEWAY_DETECTOR_KIND": "roboflow",
                "ROBOFLOW_API_URL": "https://serverless.roboflow.com/model/1",
                "ROBOFLOW_API_KEY": "rf-key",
                "CIVORA_GATEWAY_MAPBOX_TOKEN": "mapbox-token",
            },
            clear=False,
        ):
            result = run_detection_gateway(
                {"bbox": {"west": -96.2, "south": 41.1, "east": -96.1, "north": 41.2}},
                session=session,
            )

        self.assertEqual(result["status"], "detected")
        self.assertEqual({item["kind"] for item in result["detections"]}, {"building", "tree"})
        self.assertIn("api_key=rf-key", session.calls[0]["url"])


if __name__ == "__main__":
    unittest.main()
