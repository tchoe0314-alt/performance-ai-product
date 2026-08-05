from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional
from io import BytesIO
import hashlib
import json
import re
import time
import uuid
import shutil

from backend.planning.dwg_compatibility import DWG_UNSUPPORTED_STATUS

PREVIEW_RENDER_VERSION = "2026-04-17-preview-modes-v1"
DEFAULT_HEAVY_EXPORT_TIMEOUT_SECONDS = 30.0


class HeavyExportBlockedError(RuntimeError):
    def __init__(self, *, code: str, detail: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.metadata = dict(metadata or {})


def render_plan_preview_png(final_plan: Dict[str, Any], **kwargs: Any) -> bytes:
    """Module-level hook kept patchable for preview cache tests."""
    from output.preview import render_plan_preview_png as _render_plan_preview_png

    return _render_plan_preview_png(final_plan, **kwargs)


def _slugify(value: str, default: str = "artifact") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or default


def _load_pdf_font(size: int, *, bold: bool = False) -> Any:
    from PIL import ImageFont

    candidates = (
        ("DejaVuSans-Bold.ttf", "Arial Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "Arial.ttf")
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_pdf_text(draw: Any, text: Any, font: Any, max_width: int, *, max_lines: int = 6) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines - 1:
            break
    if len(lines) < max_lines:
        lines.append(current)
    consumed = " ".join(lines)
    original = " ".join(words)
    if consumed != original and lines:
        lines[-1] = f"{lines[-1].rstrip('.')}..."
    return lines[:max_lines]


class ArtifactService:
    def __init__(self, root_dir: Path, *, heavy_export_timeout_seconds: float = DEFAULT_HEAVY_EXPORT_TIMEOUT_SECONDS) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.preview_cache_dir = self.root_dir / "_preview_cache"
        self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self.preview_cache_version = PREVIEW_RENDER_VERSION
        self.heavy_export_timeout_seconds = float(heavy_export_timeout_seconds)

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
        external_verification: Dict[str, Any] = {
            "source": "export_external_verification_v1",
            "format": export_type,
            "externally_verified": False,
            "civil3d_external_verification_status": "not_verified",
            "dwg_support_status": DWG_UNSUPPORTED_STATUS,
            "construction_release_allowed": False,
            "construction_release_blocked": True,
        }
        if export_type == "dxf":
            from backend.planning.export_external_verification import verify_dxf_export

            external_verification = verify_dxf_export(
                artifact_path,
                plan=final_plan,
                sidecar_path=None,
            )
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
            "external_artifact_verification": external_verification,
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

    def export_dxf(
        self,
        *,
        user_id: str,
        final_plan: Dict[str, Any],
        stem: Optional[str] = None,
        prefinalized: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> Path:
        from output.dxf_exporter import HeavyExportTimeoutError, save_dxf

        path = self._user_dir(user_id) / self._artifact_name(stem, "dxf")
        timeout = self.heavy_export_timeout_seconds if timeout_seconds is None else timeout_seconds
        export_started = time.perf_counter()
        try:
            save_dxf(
                final_plan,
                filename=str(path),
                timeout_seconds=timeout,
                finalize_metadata=not prefinalized,
            )
        except HeavyExportTimeoutError as exc:
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
            raise HeavyExportBlockedError(
                code="heavy_export_timeout",
                detail=str(exc),
                metadata={
                    "export_performance": dict((final_plan.get("meta") or {}).get("export_performance") or {}),
                    "elapsed_seconds": round(time.perf_counter() - export_started, 6),
                    "timeout_seconds": timeout,
                    "review_only": True,
                    "construction_release_allowed": False,
                    "recommended_path": "async_queue_heavy_export",
                },
            ) from exc
        self._write_export_sidecar(artifact_path=path, export_type="dxf", final_plan=final_plan)
        return path

    def export_review_pdf(
        self,
        *,
        user_id: str,
        result_data: Dict[str, Any],
        sheet_set: Dict[str, Any],
        auto_site_context_summary: Optional[Dict[str, Any]] = None,
        review_package_summary: Optional[Dict[str, Any]] = None,
        stem: Optional[str] = None,
    ) -> Path:
        from PIL import Image, ImageDraw

        final_plan = deepcopy(dict(result_data.get("final_plan") or {}))
        self._ensure_export_package_report(final_plan, export_type="pdf")
        preview_bytes: Optional[bytes]
        try:
            preview_bytes = self.build_preview_png(
                final_plan,
                render_labels=True,
                quality="high",
                preview_style="professional_plan",
                label_density="standard",
                preview_mode="production",
            )
        except Exception:
            preview_bytes = None

        sheets = [item for item in list(sheet_set.get("sheets") or []) if isinstance(item, dict)]
        if not sheets:
            sheets = [
                {
                    "name": "Review Plan",
                    "size": "11x17",
                    "titleBlock": {
                        "projectName": final_plan.get("project_name") or "Civora Project",
                        "sheetTitle": "Review Plan",
                        "sheetNumber": "C-1.0",
                        "reviewStage": "Review",
                        "preparedBy": "Civora review workflow",
                        "checkedBy": "Qualified reviewer",
                        "date": time.strftime("%Y-%m-%d"),
                    },
                    "annotations": [],
                    "viewports": [],
                }
            ]

        source_summary = dict(auto_site_context_summary or {})
        package_summary = dict(review_package_summary or {})
        page_images: list[Any] = []
        for sheet_index, sheet in enumerate(sheets, start=1):
            page = Image.new("RGB", (2040, 1320), "white")
            draw = ImageDraw.Draw(page)
            font_small = _load_pdf_font(18)
            font_tiny = _load_pdf_font(15)
            font_body = _load_pdf_font(21)
            font_label = _load_pdf_font(18, bold=True)
            font_heading = _load_pdf_font(26, bold=True)
            font_title = _load_pdf_font(34, bold=True)
            font_watermark = _load_pdf_font(68, bold=True)
            ink = (28, 37, 48)
            muted = (86, 101, 117)
            border = (63, 74, 88)
            accent = (17, 105, 151)
            light = (238, 243, 247)

            draw.rectangle((28, 28, 2012, 1292), outline=ink, width=4)
            draw.rectangle((48, 48, 1992, 1272), outline=border, width=2)

            title_block = dict(sheet.get("titleBlock") or {})
            project_name = str(title_block.get("projectName") or final_plan.get("project_name") or "Civora Project")
            sheet_title = str(title_block.get("sheetTitle") or sheet.get("name") or "Review Plan")
            sheet_number = str(title_block.get("sheetNumber") or f"C-{sheet_index}.0")
            review_stage = str(title_block.get("reviewStage") or "Review")

            draw.text((72, 62), project_name, fill=ink, font=font_title)
            draw.text((72, 103), sheet_title, fill=muted, font=font_heading)
            draw.rounded_rectangle((1655, 61, 1968, 116), radius=10, outline=accent, width=2, fill=(241, 248, 252))
            draw.text((1680, 76), "REVIEW PACKAGE", fill=accent, font=font_label)

            preview_box = (72, 150, 1545, 1084)
            draw.rectangle(preview_box, fill=(249, 251, 252), outline=ink, width=3)
            if preview_bytes:
                try:
                    preview = Image.open(BytesIO(preview_bytes)).convert("RGB")
                    target_w = preview_box[2] - preview_box[0] - 24
                    target_h = preview_box[3] - preview_box[1] - 24
                    preview.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                    offset_x = preview_box[0] + (preview_box[2] - preview_box[0] - preview.width) // 2
                    offset_y = preview_box[1] + (preview_box[3] - preview_box[1] - preview.height) // 2
                    page.paste(preview, (offset_x, offset_y))
                except Exception:
                    draw.text((preview_box[0] + 36, preview_box[1] + 36), "Plan preview could not be rendered.", fill=muted, font=font_body)
            else:
                draw.text((preview_box[0] + 36, preview_box[1] + 36), "Plan preview is not available in this package.", fill=muted, font=font_body)

            watermark = str(dict(sheet_set.get("plotStyles") or {}).get("reviewWatermark") or "REVIEW ONLY")
            watermark_width = draw.textbbox((0, 0), watermark, font=font_watermark)[2]
            watermark_x = preview_box[0] + max(12, (preview_box[2] - preview_box[0] - watermark_width) // 2)
            draw.text((watermark_x, 575), watermark, fill=(214, 221, 227), font=font_watermark)

            side_x = 1580
            side_width = 370
            draw.text((side_x, 152), "PLAN INFORMATION", fill=ink, font=font_label)
            draw.line((side_x, 181, side_x + side_width, 181), fill=border, width=2)
            info_rows = [
                ("Sheet", sheet_number),
                ("Stage", review_stage),
                ("Scale", str((list(sheet.get("viewports") or [{}]) or [{}])[0].get("scale") or "See viewport")),
                ("Date", str(title_block.get("date") or time.strftime("%Y-%m-%d"))),
            ]
            y = 194
            for label, value in info_rows:
                draw.text((side_x, y), label.upper(), fill=muted, font=font_small)
                draw.text((side_x + 112, y), value, fill=ink, font=font_body)
                y += 36

            draw.text((side_x, y + 12), "N", fill=ink, font=font_heading)
            draw.line((side_x + 16, y + 52, side_x + 16, y + 112), fill=ink, width=4)
            draw.polygon(
                [(side_x + 16, y + 36), (side_x + 5, y + 58), (side_x + 27, y + 58)],
                fill=ink,
            )
            draw.text((side_x + 56, y + 72), "NORTH", fill=muted, font=font_small)
            y += 142

            candidate_count = int(source_summary.get("candidateCount") or source_summary.get("candidate_count") or 0)
            missing_labels = list(source_summary.get("missingLabels") or source_summary.get("missing_labels") or [])
            draw.text((side_x, y), "SOURCE SUMMARY", fill=ink, font=font_label)
            draw.line((side_x, y + 29, side_x + side_width, y + 29), fill=border, width=2)
            y += 42
            source_lines = [
                f"Detected review items: {candidate_count}",
                f"Missing sources: {', '.join(str(item) for item in missing_labels[:4]) or 'none recorded'}",
            ]
            for line in source_lines:
                for wrapped in _wrap_pdf_text(draw, line, font_body, side_width, max_lines=3):
                    draw.text((side_x, y), wrapped, fill=ink, font=font_body)
                    y += 28
                y += 6

            blockers = list(sheet_set.get("blockers") or package_summary.get("missing") or [])
            draw.text((side_x, y + 8), "REVIEW NOTES", fill=ink, font=font_label)
            draw.line((side_x, y + 37, side_x + side_width, y + 37), fill=border, width=2)
            y += 52
            note_items = blockers[:5] or ["No package notes recorded."]
            for item in note_items:
                wrapped_lines = _wrap_pdf_text(draw, f"- {item}", font_small, side_width, max_lines=2)
                for wrapped in wrapped_lines:
                    draw.text((side_x, y), wrapped, fill=muted, font=font_small)
                    y += 24
                y += 3
                if y > 1035:
                    break

            draw.rectangle((72, 1112, 1968, 1252), outline=ink, width=3)
            draw.line((1500, 1112, 1500, 1252), fill=ink, width=2)
            draw.line((1740, 1112, 1740, 1252), fill=ink, width=2)
            draw.text((92, 1132), project_name, fill=ink, font=font_heading)
            draw.text((92, 1170), sheet_title, fill=muted, font=font_body)
            draw.text((92, 1204), "Generated from the current Civora project model for professional review.", fill=muted, font=font_small)
            draw.text((1518, 1132), "PREPARED BY", fill=muted, font=font_small)
            draw.text((1518, 1162), str(title_block.get("preparedBy") or "Civora"), fill=ink, font=font_body)
            draw.text((1518, 1200), "CHECKED BY", fill=muted, font=font_small)
            draw.text((1518, 1222), str(title_block.get("checkedBy") or "Qualified reviewer"), fill=ink, font=font_small)
            draw.text((1765, 1130), sheet_number, fill=ink, font=font_title)
            draw.text((1765, 1180), review_stage, fill=accent, font=font_label)
            review_lines = _wrap_pdf_text(draw, "Professional review required", font_tiny, 180, max_lines=2)
            for line_index, line in enumerate(review_lines):
                draw.text((1765, 1210 + line_index * 18), line, fill=muted, font=font_tiny)
            page_images.append(page)

        path = self._user_dir(user_id) / self._artifact_name(stem, "pdf")
        page_images[0].save(
            path,
            "PDF",
            resolution=120.0,
            save_all=True,
            append_images=page_images[1:],
            title=str(sheet_set.get("name") or "Civora Review Package"),
            author="Civora",
            subject="Professional review package",
        )
        self._write_export_sidecar(artifact_path=path, export_type="pdf", final_plan=final_plan)
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
