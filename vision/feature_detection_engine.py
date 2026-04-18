from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
from PIL import Image


@dataclass
class FeatureDetection:
    kind: str
    bbox: Tuple[float, float, float, float]
    confidence: float
    geometry_type: str
    geometry: List[Tuple[float, float]]


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
            # Merge nearby fragments before component extraction so adjacent detections become a single shape.
            if kind in {"road", "parking", "driveway", "sidewalk", "open_space"}:
                mask = self._close_mask(mask, iterations=2)
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

        detections = self._merge_overlaps(detections)

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
                component_points: List[Tuple[int, int]] = []
                while stack:
                    cy, cx = stack.pop()
                    count += 1
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    component_points.append((cx, cy))
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if count < min_area:
                    continue
                component_mask = np.zeros((max_y - min_y + 1, max_x - min_x + 1), dtype=bool)
                for px, py in component_points:
                    component_mask[py - min_y, px - min_x] = True
                bbox = self._scale_bbox(
                    (min_x, min_y, max_x - min_x, max_y - min_y),
                    resized_width,
                    resized_height,
                    original_width,
                    original_height,
                )
                confidence = min(0.6, max(0.2, count / float(mask.size)))
                geometry_type, geometry = self._derive_geometry(
                    kind=kind,
                    points=component_points,
                    component_mask=component_mask,
                    component_offset=(min_x, min_y),
                    resized_width=resized_width,
                    resized_height=resized_height,
                    original_width=original_width,
                    original_height=original_height,
                )
                detections.append(
                    FeatureDetection(
                        kind=kind,
                        bbox=bbox,
                        confidence=confidence,
                        geometry_type=geometry_type,
                        geometry=geometry,
                    )
                )
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

    @staticmethod
    def _scale_points(
        points: List[Tuple[float, float]],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> List[Tuple[float, float]]:
        scale_x = original_width / max(resized_width, 1)
        scale_y = original_height / max(resized_height, 1)
        return [(round(px * scale_x, 3), round(py * scale_y, 3)) for px, py in points]

    @staticmethod
    def _convex_hull(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(points) <= 3:
            return points
        pts = sorted(set(points))
        if len(pts) <= 3:
            return pts

        def cross(o: Tuple[int, int], a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: List[Tuple[int, int]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper: List[Tuple[int, int]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        return lower[:-1] + upper[:-1]

    def _derive_geometry(
        self,
        *,
        kind: str,
        points: List[Tuple[int, int]],
        component_mask: Optional[np.ndarray],
        component_offset: Tuple[int, int],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> Tuple[str, List[Tuple[float, float]]]:
        if not points:
            return "rect", []
        line_kinds = {"sidewalk", "path"}
        if kind in line_kinds and len(points) >= 2:
            arr = np.asarray(points, dtype=np.float32)
            mean = arr.mean(axis=0)
            centered = arr - mean
            cov = np.cov(centered.T)
            eig_vals, eig_vecs = np.linalg.eig(cov)
            axis = eig_vecs[:, int(np.argmax(eig_vals))]
            projections = centered @ axis
            min_proj = projections.min()
            max_proj = projections.max()
            p1 = mean + min_proj * axis
            p2 = mean + max_proj * axis
            scaled = self._scale_points(
                [(float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))],
                resized_width,
                resized_height,
                original_width,
                original_height,
            )
            return "polyline", scaled

        contour = None
        if component_mask is not None:
            contour = self._trace_contour(component_mask)
        if contour:
            offset_x, offset_y = component_offset
            shifted = [(pt[0] + offset_x, pt[1] + offset_y) for pt in contour]
            simplified = self._simplify_path(shifted, epsilon=2.2)
            if len(simplified) >= 3:
                if simplified[0] != simplified[-1]:
                    simplified.append(simplified[0])
                scaled = self._scale_points(simplified, resized_width, resized_height, original_width, original_height)
                return "polygon", scaled

        hull = self._convex_hull(points)
        if len(hull) < 3:
            scaled = self._scale_points(hull, resized_width, resized_height, original_width, original_height)
            return "rect", scaled
        if len(hull) > 64:
            step = max(1, len(hull) // 64)
            hull = hull[::step]
        if hull[0] != hull[-1]:
            hull.append(hull[0])
        scaled = self._scale_points(hull, resized_width, resized_height, original_width, original_height)
        return "polygon", scaled

    @staticmethod
    def _trace_contour(component_mask: np.ndarray) -> List[Tuple[int, int]]:
        height, width = component_mask.shape
        if height == 0 or width == 0:
            return []

        def is_boundary(y: int, x: int) -> bool:
            if not component_mask[y, x]:
                return False
            for ny, nx in (
                (y - 1, x),
                (y + 1, x),
                (y, x - 1),
                (y, x + 1),
            ):
                if ny < 0 or ny >= height or nx < 0 or nx >= width:
                    return True
                if not component_mask[ny, nx]:
                    return True
            return False

        start: Optional[Tuple[int, int]] = None
        for y in range(height):
            for x in range(width):
                if is_boundary(y, x):
                    start = (x, y)
                    break
            if start is not None:
                break
        if start is None:
            return []

        dirs = [
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
            (0, -1),
            (1, -1),
        ]
        contour: List[Tuple[int, int]] = []
        current = start
        dir_idx = 0
        max_steps = height * width * 4
        steps = 0
        while steps < max_steps:
            contour.append(current)
            found = False
            search_start = (dir_idx + 6) % 8
            for i in range(8):
                idx = (search_start + i) % 8
                dx, dy = dirs[idx]
                nx = current[0] + dx
                ny = current[1] + dy
                if 0 <= ny < height and 0 <= nx < width and component_mask[ny, nx]:
                    current = (nx, ny)
                    dir_idx = idx
                    found = True
                    break
            if not found:
                break
            steps += 1
            if current == start and steps > 3:
                break
        return contour

    @staticmethod
    def _simplify_path(points: List[Tuple[int, int]], epsilon: float) -> List[Tuple[int, int]]:
        if len(points) < 4:
            return points

        def perpendicular_distance(pt: Tuple[int, int], start: Tuple[int, int], end: Tuple[int, int]) -> float:
            if start == end:
                return float(np.hypot(pt[0] - start[0], pt[1] - start[1]))
            sx, sy = start
            ex, ey = end
            px, py = pt
            num = abs((ey - sy) * px - (ex - sx) * py + ex * sy - ey * sx)
            den = np.hypot(ey - sy, ex - sx)
            return float(num / den)

        def rdp(seq: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
            if len(seq) < 3:
                return seq
            start = seq[0]
            end = seq[-1]
            max_dist = 0.0
            index = 0
            for i in range(1, len(seq) - 1):
                dist = perpendicular_distance(seq[i], start, end)
                if dist > max_dist:
                    max_dist = dist
                    index = i
            if max_dist > epsilon:
                left = rdp(seq[: index + 1])
                right = rdp(seq[index:])
                return left[:-1] + right
            return [start, end]

        closed = points[0] == points[-1]
        seq = points[:-1] if closed else points
        simplified = rdp(seq)
        if closed and simplified[0] != simplified[-1]:
            simplified.append(simplified[0])
        return simplified

    @staticmethod
    def _merge_overlaps(detections: List[FeatureDetection]) -> List[FeatureDetection]:
        if not detections:
            return detections
        output: List[FeatureDetection] = []
        for det in sorted(detections, key=lambda d: d.confidence, reverse=True):
            should_keep = True
            for kept in output:
                if det.kind != kept.kind:
                    continue
                if FeatureDetectionEngine._iou(det.bbox, kept.bbox) > 0.5:
                    should_keep = False
                    break
            if should_keep:
                output.append(det)
        return output

    @staticmethod
    def _iou(
        a: Tuple[float, float, float, float],
        b: Tuple[float, float, float, float],
    ) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ax2 = ax + aw
        ay2 = ay + ah
        bx2 = bx + bw
        by2 = by + bh
        inter_x1 = max(ax, bx)
        inter_y1 = max(ay, by)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = aw * ah
        area_b = bw * bh
        return inter_area / max(area_a + area_b - inter_area, 1e-6)

    @staticmethod
    def _close_mask(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        if iterations <= 0:
            return mask
        result = mask.copy()
        for _ in range(iterations):
            # Dilate
            padded = np.pad(result, 1, mode="edge")
            dilated = np.zeros_like(result, dtype=bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    dilated |= padded[1 + dy : 1 + dy + result.shape[0], 1 + dx : 1 + dx + result.shape[1]]
            # Erode
            padded = np.pad(dilated, 1, mode="edge")
            eroded = np.ones_like(result, dtype=bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    eroded &= padded[1 + dy : 1 + dy + result.shape[0], 1 + dx : 1 + dx + result.shape[1]]
            result = eroded
        return result
