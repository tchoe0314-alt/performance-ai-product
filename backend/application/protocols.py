from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class ArtifactServiceProtocol(Protocol):
    def build_preview_png(
        self,
        final_plan: Dict[str, Any],
        *,
        render_labels: bool = True,
        quality: str = "standard",
        include_layers: Optional[list[str]] = None,
        preview_style: Optional[str] = None,
        label_density: Optional[str] = None,
        preview_mode: Optional[str] = None,
    ) -> bytes:
        ...

    def export_dxf(self, *, user_id: str, final_plan: Dict[str, Any], stem: Optional[str] = None) -> Path:
        ...

    def export_report_json(
        self,
        *,
        user_id: str,
        result_data: Dict[str, Any],
        stem: Optional[str] = None,
    ) -> Path:
        ...

    def delete_preview_cache_for_project(self, *, user_id: str, project_id: str) -> int:
        ...
