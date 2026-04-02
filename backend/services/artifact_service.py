from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json
import re
import time
import uuid

import report_builder
from output.dxf_exporter import save_dxf
from output.preview import render_plan_preview_png


def _slugify(value: str, default: str = "artifact") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or default


class ArtifactService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: str) -> Path:
        target = self.root_dir / str(user_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _artifact_name(self, stem: Optional[str], ext: str) -> str:
        prefix = _slugify(stem or "civora-ai")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{prefix}-{timestamp}-{suffix}.{ext}"

    def build_preview_png(self, final_plan: Dict[str, Any]) -> bytes:
        return render_plan_preview_png(final_plan)

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
            },
        )

        path = self._user_dir(user_id) / self._artifact_name(stem, "json")
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path
