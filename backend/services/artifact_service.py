from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json
import re
import time
import uuid
import shutil

PREVIEW_RENDER_VERSION = "2026-04-17-preview-modes-v1"


def render_plan_preview_png(final_plan: Dict[str, Any], **kwargs: Any) -> bytes:
    """Module-level hook kept patchable for preview cache tests."""
    from output.preview import render_plan_preview_png as _render_plan_preview_png

    return _render_plan_preview_png(final_plan, **kwargs)


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

    def _sidecar_path(self, artifact_path: Path) -> Path:
        return artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")

    def _ensure_export_package_report(self, final_plan: Dict[str, Any], *, export_type: str) -> Dict[str, Any]:
        from backend.planning.export_package_report import build_export_package_report_v1

        meta = final_plan.setdefault("meta", {})
        report = build_export_package_report_v1(final_plan, export_type=export_type)
        meta["export_package_report_v1"] = report
        return report

    def _ids_from_payload(self, value: Any) -> list[str]:
        ids: list[str] = []
        if isinstance(value, dict):
            for key in (
                "canonical_id",
                "canonical_source_id",
                "canonical_model_id",
                "source_object_id",
                "quantity_source_id",
                "alignment_id",
                "alignment_owner",
            ):
                raw = value.get(key)
                text = str(raw).strip() if raw is not None else ""
                if text:
                    ids.append(text)
            for key in ("canonical_ids", "canonical_source_ids", "source_object_ids", "quantity_source_ids"):
                raw_list = value.get(key)
                if isinstance(raw_list, list):
                    ids.extend(str(item).strip() for item in raw_list if str(item).strip())
            for child in value.values():
                ids.extend(self._ids_from_payload(child))
        elif isinstance(value, list):
            for child in value:
                ids.extend(self._ids_from_payload(child))
        out: list[str] = []
        seen = set()
        for item in ids:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    def _report_line_items(self, report_payload: Dict[str, Any], package_report: Dict[str, Any]) -> list[Dict[str, Any]]:
        rows: list[Dict[str, Any]] = []
        package_ids = list(package_report.get("canonical_ids_included") or [])
        for index, section in enumerate(report_payload.get("sections") or [], start=1):
            if not isinstance(section, dict):
                continue
            ids = self._ids_from_payload(section)
            if not ids:
                ids = package_ids
            rows.append(
                {
                    "record_type": "report_section",
                    "record_id": str(section.get("section_id") or f"section-{index}"),
                    "title": str(section.get("title") or ""),
                    "canonical_ids": ids,
                    "engineer_review_required": True,
                    "civora_signoff_allowed": False,
                    "construction_release_allowed": False,
                    "review_package_only": True,
                }
            )
        return rows

    def _write_export_sidecar(
        self,
        *,
        artifact_path: Path,
        export_type: str,
        final_plan: Dict[str, Any],
        report_payload: Optional[Dict[str, Any]] = None,
    ) -> Path:
        package_report = self._ensure_export_package_report(final_plan, export_type=export_type)
        sidecar_path = self._sidecar_path(artifact_path)
        payload: Dict[str, Any] = {
            "source": "export_artifact_sidecar_v1",
            "artifact_path": str(artifact_path),
            "artifact_filename": artifact_path.name,
            "export_type": export_type,
            "export_package_report_ref": {
                "source": package_report.get("source"),
                "export_type": package_report.get("export_type"),
                "source_project_id": package_report.get("source_project_id"),
                "source_canonical_revision": package_report.get("source_canonical_revision"),
                "source_canonical_hash": package_report.get("source_canonical_hash"),
                "generated_at": package_report.get("generated_at"),
            },
            "export_package_report_v1": deepcopy(package_report),
            "quantity_line_items": deepcopy(package_report.get("quantity_line_items") or []),
            "engineer_review_required": True,
            "civora_signoff_allowed": False,
            "construction_release_allowed": False,
            "construction_release_blocked": True,
        }
        if report_payload is not None:
            payload["report_line_items"] = self._report_line_items(report_payload, package_report)
        sidecar_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        final_plan.setdefault("meta", {}).setdefault("artifact_sidecars", []).append(
            {
                "artifact_path": str(artifact_path),
                "sidecar_metadata_path": str(sidecar_path),
                "export_type": export_type,
                "export_package_report_ref": deepcopy(payload["export_package_report_ref"]),
            }
        )
        return sidecar_path

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
        project_id = str((final_plan.get("meta") or {}).get("project_id") or "")
        payload = json.dumps(
            {
                "render_version": self.preview_cache_version,
                "project_id": project_id,
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

    def delete_preview_cache_for_project(self, *, user_id: str, project_id: str) -> int:
        if not project_id:
            return 0
        target = self.preview_cache_dir / str(project_id)
        if not target.exists():
            return 0
        removed = 0
        for path in target.glob("*.png"):
            try:
                path.unlink()
                removed += 1
            except Exception:
                continue
        try:
            shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass
        return removed

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
        project_id = str((final_plan.get("meta") or {}).get("project_id") or "").strip()
        cache_root = self.preview_cache_dir / project_id if project_id else self.preview_cache_dir
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_path = cache_root / f"{self._preview_cache_key(final_plan, render_labels=render_labels, quality=quality, preview_style=preview_style, label_density=label_density, include_layers=include_layers, preview_mode=preview_mode)}.png"
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
        from output.dxf_exporter import save_dxf

        path = self._user_dir(user_id) / self._artifact_name(stem, "dxf")
        save_dxf(final_plan, filename=str(path))
        self._write_export_sidecar(artifact_path=path, export_type="dxf", final_plan=final_plan)
        return path

    def export_report_json(
        self,
        *,
        user_id: str,
        result_data: Dict[str, Any],
        stem: Optional[str] = None,
    ) -> Path:
        import report_builder

        final_plan = dict(result_data.get("final_plan") or {})
        package_report = self._ensure_export_package_report(final_plan, export_type="report")
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
        report["export_package_report_v1"] = deepcopy(package_report)

        path = self._user_dir(user_id) / self._artifact_name(stem, "json")
        sidecar_path = self._write_export_sidecar(
            artifact_path=path,
            export_type="report",
            final_plan=final_plan,
            report_payload=report,
        )
        report["export_package_report_v1"] = deepcopy(final_plan["meta"]["export_package_report_v1"])
        report["artifact_metadata"] = {
            "sidecar_metadata_path": str(sidecar_path),
            "export_package_report_ref": deepcopy(report["export_package_report_v1"]),
        }
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path
