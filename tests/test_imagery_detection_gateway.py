import os
import json
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend.scripts.imagery_detection_gateway import (
    build_mapbox_static_image_url,
    gateway_health_status,
    normalize_generic_response,
    normalize_roboflow_response,
    run_detection_gateway,
)


class _Response:
    def __init__(self, payload, *, content=b"", headers=None):
        self.payload = payload
        self.content = content
        self.headers = headers or {}

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


class _CivoraImageSession:
    def __init__(self):
        self.calls = []
        image = Image.new("RGB", (256, 256), (112, 150, 96))
        draw = ImageDraw.Draw(image)
        draw.rectangle((24, 24, 74, 66), fill=(38, 38, 38))
        draw.rectangle((102, 28, 158, 82), fill=(45, 45, 45))
        draw.rectangle((0, 186, 256, 218), fill=(95, 95, 95))
        draw.rectangle((42, 108, 188, 158), fill=(165, 165, 165))
        draw.ellipse((196, 40, 238, 82), fill=(40, 120, 190))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        self.content = buffer.getvalue()

    def get(self, url, timeout=None):
        self.calls.append({"url": url, "timeout": timeout, "method": "get"})
        return _Response({}, content=self.content, headers={"content-type": "image/png"})


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
    @patch.dict(
        os.environ,
        {
            "CIVORA_GATEWAY_DETECTOR_KIND": "civora",
            "CIVORA_GATEWAY_MODEL_NAME": "civora-vision",
            "CIVORA_GATEWAY_MODEL_VERSION": "v2-test",
            "CIVORA_GATEWAY_SOURCE_LICENSE": "unconfirmed",
            "CIVORA_GATEWAY_TRAINING_USE_ALLOWED": "false",
        },
        clear=False,
    )
    def test_health_reports_contract_model_and_source_rights_posture(self) -> None:
        status = gateway_health_status()

        self.assertEqual(status["detector_kind"], "civora")
        self.assertEqual(status["provider"], "civora_heuristic")
        self.assertEqual(status["imagery_frame_version"], "civora_imagery_frame_v2")
        self.assertEqual(status["detection_contract_version"], "civora_vision_detection_report_v2")
        self.assertEqual(status["model_name"], "civora-vision")
        self.assertEqual(status["model_version"], "v2-test")
        self.assertFalse(status["source_rights"]["training_use_allowed"])

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

    def test_gateway_redacts_source_credentials_and_does_not_trust_public_rights_claims(self) -> None:
        session = _GenericSession()
        with patch.dict(
            os.environ,
            {
                "CIVORA_GATEWAY_DETECTOR_KIND": "generic",
                "CIVORA_GATEWAY_SOURCE_MODE": "direct",
                "CIVORA_GATEWAY_GENERIC_DETECTOR_URL": "https://detector.example/detect",
                "CIVORA_GATEWAY_GENERIC_DETECTOR_TOKEN": "detector-secret",
                "CIVORA_GATEWAY_TRAINING_USE_ALLOWED": "false",
                "CIVORA_GATEWAY_SOURCE_STORAGE_ALLOWED": "false",
                "CIVORA_GATEWAY_TRUST_REQUEST_SOURCE_RIGHTS": "false",
            },
            clear=False,
        ):
            result = run_detection_gateway(
                {
                    "image_url": "https://imagery.example/source.png?access_token=source-secret",
                    "bbox": {"west": -96.2, "south": 41.1, "east": -96.1, "north": 41.2},
                    "source_rights": {
                        "license": "self-asserted",
                        "training_use_allowed": True,
                        "storage_allowed": True,
                    },
                },
                session=session,
            )

        serialized = json.dumps(result)
        frame = result["civora_vision_detection_report_v2"]["imagery_frame"]
        self.assertNotIn("source-secret", serialized)
        self.assertNotIn("detector-secret", serialized)
        self.assertEqual(result["source_url"], "https://imagery.example/source.png")
        self.assertEqual(result["detections"][0]["source_url"], "https://imagery.example/source.png")
        self.assertFalse(frame["source_rights"]["training_use_allowed"])
        self.assertFalse(frame["source_rights"]["storage_allowed"])
        self.assertFalse(frame["source_rights"]["request_attestation_trusted"])

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

    def test_gateway_can_run_civora_local_detector_without_external_model(self) -> None:
        session = _CivoraImageSession()
        with patch.dict(
            os.environ,
            {
                "CIVORA_GATEWAY_DETECTOR_KIND": "civora",
                "CIVORA_GATEWAY_SOURCE_MODE": "direct",
            },
            clear=False,
        ):
            result = run_detection_gateway({"image_url": "https://imagery.example/source.png"}, session=session)

        kinds = {item["kind"] for item in result["detections"]}

        self.assertEqual(result["provider"], "civora_heuristic")
        self.assertEqual(result["status"], "detected")
        self.assertTrue(kinds.intersection({"building", "road", "parking", "basin", "open_space"}))
        self.assertTrue(all(item["provider"] == "civora_heuristic" for item in result["detections"]))
        self.assertFalse(
            any(
                item["kind"] in {"parking", "open_space"} and (item["bbox"][2] * item["bbox"][3]) > 0.32 * 256 * 256
                for item in result["detections"]
            )
        )


if __name__ == "__main__":
    unittest.main()
