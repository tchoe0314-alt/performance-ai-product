from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image


@dataclass
class FeatureDetection:
    kind: str
    bbox: Tuple[float, float, float, float]
    confidence: float


@dataclass
class FeatureDetectionResult:
    success: bool
    message: str
    image_width: int
    image_height: int
    detections: List[FeatureDetection]
    warnings: List[str]
    meta: Dict[str, Any]


class FeatureDetectionEngine:
    """
    First-pass heuristic feature detector for imagery.

    This is intentionally approximate and should be treated as "suggested" only.
    """

    def __init__(self, max_size: int = 512) -> None:
        self.max_size = max(128, int(max_size))

    def detect(self, image_path: str) -> FeatureDetectionResult:
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            return FeatureDetectionResult(
                success=False,
                message=f"Unable to open image: {exc}",
                image_width=0,
                image_height=0,
                detections=[],
                warnings=["Image could not be read."],
                meta={},
            )

        width, height = image.size
        scale = min(1.0, float(self.max_size) / max(width, height))
        if scale < 1.0:
            image = image.resize((int(round(width * scale)), int(round(height * scale))), Image.Resampling.BILINEAR)
        resized_width, resized_height = image.size

        arr = np.asarray(image).astype(np.float32)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return FeatureDetectionResult(
                success=False,
                message="Image array format unsupported for detection.",
                image_width=width,
                image_height=height,
                detections=[],
                warnings=["Unsupported image format."],
                meta={},
            )

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        gray = 0.299 * r + 0.587 * g + 0.114 * b

        detections: List[FeatureDetection] = []
        warnings: List[str] = [
            "Detected features are approximate and must be confirmed by the user.",
        ]

        total_pixels = gray.size
        min_area = max(40, int(total_pixels * 0.002))
        max_components = 12

        green_mask = (g > r * 1.2) & (g > b * 1.2) & (g > 80)
        blue_mask = (b > r * 1.2) & (b > g * 1.1) & (b > 80)
        light_mask = gray >= 205
        driveway_mask = (gray >= 90) & (gray < 120)

        for kind, mask in (
            ("building", gray < 70),
            ("road", (gray >= 70) & (gray < 130)),
            ("parking", (gray >= 130) & (gray < 205)),
            ("driveway", driveway_mask),
            ("sidewalk", light_mask),
            ("open_space", green_mask),
            ("basin", blue_mask),
            ("pool", blue_mask),
        ):
            detections.extend(
                self._components_to_detections(
                    mask=mask,
                    kind=kind,
                    min_area=min_area,
                    max_components=max_components,
                    resized_width=resized_width,
                    resized_height=resized_height,
                    original_width=width,
                    original_height=height,
                )
            )

        if not detections:
            warnings.append("No strong feature regions detected. Try a clearer map or topo image.")

        return FeatureDetectionResult(
            success=True,
            message="Feature detection completed (heuristic).",
            image_width=width,
            image_height=height,
            detections=detections,
            warnings=warnings,
            meta={"scale": scale},
        )

    def _components_to_detections(
        self,
        *,
        mask: np.ndarray,
        kind: str,
        min_area: int,
        max_components: int,
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> List[FeatureDetection]:
        detections: List[FeatureDetection] = []
        visited = np.zeros(mask.shape, dtype=bool)
        height, width = mask.shape
        for y in range(height):
            for x in range(width):
                if not mask[y, x] or visited[y, x]:
                    continue
                stack = [(y, x)]
                visited[y, x] = True
                min_x = max_x = x
                min_y = max_y = y
                count = 0
                while stack:
                    cy, cx = stack.pop()
                    count += 1
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if count < min_area:
                    continue
                bbox = self._scale_bbox(
                    (min_x, min_y, max_x - min_x, max_y - min_y),
                    resized_width,
                    resized_height,
                    original_width,
                    original_height,
                )
                confidence = min(0.6, max(0.2, count / float(mask.size)))
                detections.append(FeatureDetection(kind=kind, bbox=bbox, confidence=confidence))
                if len(detections) >= max_components:
                    return detections
        return detections

    @staticmethod
    def _scale_bbox(
        bbox: Tuple[int, int, int, int],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> Tuple[float, float, float, float]:
        x, y, w, h = bbox
        scale_x = original_width / max(resized_width, 1)
        scale_y = original_height / max(resized_height, 1)
        return (
            round(x * scale_x, 3),
            round(y * scale_y, 3),
            round(w * scale_x, 3),
            round(h * scale_y, 3),
        )
