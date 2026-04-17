from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json
import re
import time
import uuid

import report_builder
from output.dxf_exporter import save_dxf
from output.preview import render_plan_preview_png

PREVIEW_RENDER_VERSION = "2026-04-17-preview-modes-v1"


def _slugify(value: str, default: str = "artifact") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or default


class ArtifactService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.preview_cache_dir = self.root_dir / "_preview_cache"
        self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self.preview_cache_version = PREVIEW_RENDER_VERSION

    def _user_dir(self, user_id: str) -> Path:
        target = self.root_dir / str(user_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _artifact_name(self, stem: Optional[str], ext: str) -> str:
        prefix = _slugify(stem or "civora-ai")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{prefix}-{timestamp}-{suffix}.{ext}"

    def _preview_cache_key(
        self,
        final_plan: Dict[str, Any],
        *,
        render_labels: bool,
        quality: str,
        preview_style: Optional[str] = None,
        label_density: Optional[str] = None,
        include_layers: Optional[list[str]] = None,
        preview_mode: Optional[str] = None,
    ) -> str:
        payload = json.dumps(
            {
                "render_version": self.preview_cache_version,
                "render_labels": bool(render_labels),
                "quality": str(quality),
                "preview_style": str(preview_style or ""),
                "label_density": str(label_density or ""),
                "preview_mode": str(preview_mode or ""),
                "include_layers": sorted(set(include_layers or [])),
                "final_plan": final_plan or {},
            },
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def build_preview_png(
        self,
        final_plan: Dict[str, Any],
        *,
        render_labels: bool = True,
        quality: str = "standard",
        preview_style: Optional[str] = None,
        label_density: Optional[str] = None,
        include_layers: Optional[list[str]] = None,
        preview_mode: Optional[str] = None,
    ) -> bytes:
        cache_path = self.preview_cache_dir / f"{self._preview_cache_key(final_plan, render_labels=render_labels, quality=quality, preview_style=preview_style, label_density=label_density, include_layers=include_layers, preview_mode=preview_mode)}.png"
        if cache_path.exists():
            return cache_path.read_bytes()
        quality_key = str(quality).lower()
        dpi = 240 if quality_key == "high" else 160
        density = label_density
        if not density:
            density = "high" if quality_key == "high" else "standard"
        png_bytes = render_plan_preview_png(
            final_plan,
            render_labels=render_labels,
            dpi=dpi,
            include_layers=set(include_layers or []) if include_layers else None,
            preview_mode=preview_mode,
            preview_style=preview_style,
            label_density=density,
        )
        try:
            cache_path.write_bytes(png_bytes)
        except Exception:
            pass
        return png_bytes

    def export_dxf(self, *, user_id: str, final_plan: Dict[str, Any], stem: Optional[str] = None) -> Path:
        path = self._user_dir(user_id) / self._artifact_name(stem, "dxf")
        save_dxf(final_plan, filename=str(path))
        return path

    def export_report_json(
        self,
        *,
        user_id: str,
        result_data: Dict[str, Any],
        stem: Optional[str] = None,
    ) -> Path:
        final_plan = dict(result_data.get("final_plan") or {})
        report = report_builder.build_report(
            final_plan=final_plan,
            orchestrator_metadata=dict(result_data.get("metadata") or {}),
            assumptions=list(result_data.get("assumptions") or []),
            warnings=list(result_data.get("warnings") or []),
            errors=list(result_data.get("errors") or []),
            request_metadata={
                "parsed_payload": dict(result_data.get("parsed_payload") or {}),
                **dict(result_data.get("request_metadata") or {}),
            },
        )

        path = self._user_dir(user_id) / self._artifact_name(stem, "json")
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path
