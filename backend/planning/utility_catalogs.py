from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ACCEPTED_REVIEW_STATUSES = {"accepted_for_workspace", "company_reviewed", "jurisdiction_reviewed"}
SUPPORTED_NETWORKS = {"storm", "sanitary", "water"}
SUPPORTED_PART_TYPES = {"structure", "inlet", "manhole", "hydrant", "valve", "fitting"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return float(default)
    return result


@dataclass
class CatalogSource:
    source_name: str
    source_type: str
    source_reference: str
    jurisdiction: str = ""
    company: str = ""
    effective_date: str = ""
    reviewed_by: str = ""
    review_date: str = ""
    notes: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CatalogSource":
        return cls(
            source_name=_safe_str(payload.get("source_name")),
            source_type=_safe_str(payload.get("source_type")),
            source_reference=_safe_str(payload.get("source_reference")),
            jurisdiction=_safe_str(payload.get("jurisdiction")),
            company=_safe_str(payload.get("company")),
            effective_date=_safe_str(payload.get("effective_date")),
            reviewed_by=_safe_str(payload.get("reviewed_by")),
            review_date=_safe_str(payload.get("review_date")),
            notes=_safe_str(payload.get("notes")),
        )

    def missing_fields(self) -> List[str]:
        missing = []
        for field_name in ("source_name", "source_type", "source_reference", "reviewed_by", "review_date"):
            if not getattr(self, field_name):
                missing.append(field_name)
        if not (self.jurisdiction or self.company):
            missing.append("jurisdiction_or_company")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "jurisdiction": self.jurisdiction,
            "company": self.company,
            "effective_date": self.effective_date,
            "reviewed_by": self.reviewed_by,
            "review_date": self.review_date,
            "notes": self.notes,
        }


@dataclass
class PipeCatalogItem:
    item_id: str
    network: str
    material: str
    sizes_in: List[float]
    pressure_class: str = ""
    roughness_n: Optional[float] = None
    source: CatalogSource = field(default_factory=lambda: CatalogSource("", "", ""))
    review_status: str = "needs_review"
    limitations: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PipeCatalogItem":
        return cls(
            item_id=_safe_str(payload.get("item_id")),
            network=_safe_str(payload.get("network")).lower(),
            material=_safe_str(payload.get("material")).upper(),
            sizes_in=sorted({_safe_float(value) for value in _safe_list(payload.get("sizes_in")) if _safe_float(value) > 0}),
            pressure_class=_safe_str(payload.get("pressure_class")),
            roughness_n=payload.get("roughness_n") if isinstance(payload.get("roughness_n"), (int, float)) else None,
            source=CatalogSource.from_payload(_safe_dict(payload.get("source"))),
            review_status=_safe_str(payload.get("review_status"), "needs_review"),
            limitations=[_safe_str(item) for item in _safe_list(payload.get("limitations")) if _safe_str(item)],
        )

    def validate(self) -> List[str]:
        issues = []
        if not self.item_id:
            issues.append("item_id is required")
        if self.network not in SUPPORTED_NETWORKS:
            issues.append("network must be storm, sanitary, or water")
        if not self.material:
            issues.append("material is required")
        if not self.sizes_in:
            issues.append("at least one positive size is required")
        issues.extend([f"source.{field_name} is required" for field_name in self.source.missing_fields()])
        if self.review_status not in ACCEPTED_REVIEW_STATUSES and self.review_status != "needs_review":
            issues.append("review_status must be needs_review or an accepted workspace review status")
        return issues

    def accepted(self) -> bool:
        return self.review_status in ACCEPTED_REVIEW_STATUSES and not self.source.missing_fields()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "network": self.network,
            "material": self.material,
            "sizes_in": self.sizes_in,
            "pressure_class": self.pressure_class,
            "roughness_n": self.roughness_n,
            "source": self.source.to_dict(),
            "review_status": self.review_status,
            "accepted_for_workspace": self.accepted(),
            "limitations": list(self.limitations),
        }


@dataclass
class PartCatalogItem:
    item_id: str
    network: str
    part_type: str
    name: str
    compatible_materials: List[str] = field(default_factory=list)
    compatible_sizes_in: List[float] = field(default_factory=list)
    source: CatalogSource = field(default_factory=lambda: CatalogSource("", "", ""))
    review_status: str = "needs_review"
    limitations: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PartCatalogItem":
        return cls(
            item_id=_safe_str(payload.get("item_id")),
            network=_safe_str(payload.get("network")).lower(),
            part_type=_safe_str(payload.get("part_type")).lower(),
            name=_safe_str(payload.get("name")),
            compatible_materials=[_safe_str(item).upper() for item in _safe_list(payload.get("compatible_materials")) if _safe_str(item)],
            compatible_sizes_in=sorted({_safe_float(value) for value in _safe_list(payload.get("compatible_sizes_in")) if _safe_float(value) > 0}),
            source=CatalogSource.from_payload(_safe_dict(payload.get("source"))),
            review_status=_safe_str(payload.get("review_status"), "needs_review"),
            limitations=[_safe_str(item) for item in _safe_list(payload.get("limitations")) if _safe_str(item)],
        )

    def validate(self) -> List[str]:
        issues = []
        if not self.item_id:
            issues.append("item_id is required")
        if self.network not in SUPPORTED_NETWORKS:
            issues.append("network must be storm, sanitary, or water")
        if self.part_type not in SUPPORTED_PART_TYPES:
            issues.append("part_type is not supported")
        if not self.name:
            issues.append("name is required")
        issues.extend([f"source.{field_name} is required" for field_name in self.source.missing_fields()])
        if self.review_status not in ACCEPTED_REVIEW_STATUSES and self.review_status != "needs_review":
            issues.append("review_status must be needs_review or an accepted workspace review status")
        return issues

    def accepted(self) -> bool:
        return self.review_status in ACCEPTED_REVIEW_STATUSES and not self.source.missing_fields()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "network": self.network,
            "part_type": self.part_type,
            "name": self.name,
            "compatible_materials": list(self.compatible_materials),
            "compatible_sizes_in": list(self.compatible_sizes_in),
            "source": self.source.to_dict(),
            "review_status": self.review_status,
            "accepted_for_workspace": self.accepted(),
            "limitations": list(self.limitations),
        }


def sample_catalog() -> Dict[str, Any]:
    source = CatalogSource(
        source_name="Civora sample utility catalog",
        source_type="sample",
        source_reference="local fixture for workspace review",
        company="Civora demo workspace",
        reviewed_by="Civora fixture",
        review_date="2026-06-07",
        notes="Sample data for workflow testing; replace with jurisdiction or company source before relying on it.",
    )
    return {
        "version": "utility_catalog_v1",
        "pipes": [
            PipeCatalogItem("storm-rcp-sample", "storm", "RCP", [12, 15, 18, 24, 30, 36], source=source, review_status="needs_review").to_dict(),
            PipeCatalogItem("san-pvc-sample", "sanitary", "PVC", [6, 8, 10, 12], source=source, review_status="needs_review").to_dict(),
            PipeCatalogItem("water-dip-sample", "water", "DIP", [6, 8, 10, 12], pressure_class="workspace_review_required", source=source, review_status="needs_review").to_dict(),
        ],
        "parts": [
            PartCatalogItem("storm-inlet-sample", "storm", "inlet", "Curb inlet", ["RCP"], [12, 15, 18, 24], source=source, review_status="needs_review").to_dict(),
            PartCatalogItem("san-manhole-sample", "sanitary", "manhole", "Sanitary manhole", ["PVC"], [6, 8, 10, 12], source=source, review_status="needs_review").to_dict(),
            PartCatalogItem("water-hydrant-sample", "water", "hydrant", "Fire hydrant assembly", ["DIP"], [6, 8, 10, 12], source=source, review_status="needs_review").to_dict(),
            PartCatalogItem("water-valve-sample", "water", "valve", "Gate valve", ["DIP"], [6, 8, 10, 12], source=source, review_status="needs_review").to_dict(),
            PartCatalogItem("water-fitting-sample", "water", "fitting", "Bend fitting", ["DIP"], [6, 8, 10, 12], source=source, review_status="needs_review").to_dict(),
        ],
        "policy": {
            "requires_explicit_source": True,
            "requires_review_status": True,
            "standards_claim": "No standards compliance is inferred from catalog presence.",
        },
    }


class UtilityCatalogManager:
    def __init__(self, initial_catalog: Optional[Dict[str, Any]] = None) -> None:
        self.catalog = deepcopy(initial_catalog or sample_catalog())

    def snapshot(self) -> Dict[str, Any]:
        catalog = deepcopy(self.catalog)
        catalog["summary"] = self.summary()
        return catalog

    def summary(self) -> Dict[str, Any]:
        pipes = [_safe_dict(item) for item in _safe_list(self.catalog.get("pipes"))]
        parts = [_safe_dict(item) for item in _safe_list(self.catalog.get("parts"))]
        accepted_pipe_count = sum(1 for item in pipes if PipeCatalogItem.from_payload(item).accepted())
        accepted_part_count = sum(1 for item in parts if PartCatalogItem.from_payload(item).accepted())
        return {
            "pipe_catalog_count": len(pipes),
            "part_catalog_count": len(parts),
            "accepted_pipe_catalog_count": accepted_pipe_count,
            "accepted_part_catalog_count": accepted_part_count,
            "review_required_count": len(pipes) + len(parts) - accepted_pipe_count - accepted_part_count,
        }

    def add_pipe_catalog(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        item = PipeCatalogItem.from_payload(payload)
        issues = item.validate()
        if issues:
            return {"success": False, "status": "rejected", "issues": issues, "catalog": item.to_dict()}
        self.catalog.setdefault("pipes", [])
        self.catalog["pipes"] = [record for record in _safe_list(self.catalog.get("pipes")) if _safe_dict(record).get("item_id") != item.item_id]
        self.catalog["pipes"].append(item.to_dict())
        return {"success": True, "status": "stored", "issues": [], "catalog": item.to_dict(), "summary": self.summary()}

    def add_part_catalog(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        item = PartCatalogItem.from_payload(payload)
        issues = item.validate()
        if issues:
            return {"success": False, "status": "rejected", "issues": issues, "catalog": item.to_dict()}
        self.catalog.setdefault("parts", [])
        self.catalog["parts"] = [record for record in _safe_list(self.catalog.get("parts")) if _safe_dict(record).get("item_id") != item.item_id]
        self.catalog["parts"].append(item.to_dict())
        return {"success": True, "status": "stored", "issues": [], "catalog": item.to_dict(), "summary": self.summary()}

    def available_pipe_sizes(self, network: str = "", material: str = "", accepted_only: bool = False) -> Dict[str, Any]:
        network = _safe_str(network).lower()
        material = _safe_str(material).upper()
        sizes: Dict[str, List[float]] = {}
        review_required: List[str] = []
        for record in _safe_list(self.catalog.get("pipes")):
            item = PipeCatalogItem.from_payload(_safe_dict(record))
            if network and item.network != network:
                continue
            if material and item.material != material:
                continue
            if accepted_only and not item.accepted():
                continue
            key = f"{item.network}:{item.material}"
            sizes.setdefault(key, [])
            sizes[key] = sorted(set([*sizes[key], *item.sizes_in]))
            if not item.accepted():
                review_required.append(item.item_id)
        return {
            "success": True,
            "accepted_only": accepted_only,
            "sizes_by_network_material": sizes,
            "review_required_catalog_ids": review_required,
            "message": "Catalog entries with review_required_catalog_ids need source/review acceptance before they can be used for validation.",
        }

    def validate_network(self, network_payload: Dict[str, Any]) -> Dict[str, Any]:
        features = _safe_list(network_payload.get("features") or network_payload.get("segments") or network_payload.get("pipes"))
        issues: List[Dict[str, Any]] = []
        for index, feature_value in enumerate(features, start=1):
            feature = _safe_dict(feature_value)
            feature_id = _safe_str(feature.get("id") or feature.get("name"), f"feature-{index}")
            network = _safe_str(feature.get("network") or network_payload.get("network")).lower()
            material = _safe_str(feature.get("material")).upper()
            size = _safe_float(feature.get("size_in") or feature.get("diameter_in"))
            matched = [
                PipeCatalogItem.from_payload(_safe_dict(item))
                for item in _safe_list(self.catalog.get("pipes"))
                if PipeCatalogItem.from_payload(_safe_dict(item)).network == network
                and PipeCatalogItem.from_payload(_safe_dict(item)).material == material
            ]
            if not matched:
                issues.append({"feature_id": feature_id, "severity": "error", "reason": f"No pipe catalog found for {network or 'unknown'} {material or 'unknown material'}."})
                continue
            size_matches = [item for item in matched if size in item.sizes_in]
            if not size_matches:
                valid_sizes = sorted({valid_size for item in matched for valid_size in item.sizes_in})
                issues.append({"feature_id": feature_id, "severity": "error", "reason": f"{size:g} in is not listed for {network} {material}.", "available_sizes_in": valid_sizes})
                continue
            if not any(item.accepted() for item in size_matches):
                issues.append({"feature_id": feature_id, "severity": "warning", "reason": "Matching pipe catalog exists but is not accepted for this workspace.", "matching_catalog_ids": [item.item_id for item in size_matches]})
        return {
            "success": not any(issue.get("severity") == "error" for issue in issues),
            "status": "valid" if not issues else "review_required",
            "issue_count": len(issues),
            "issues": issues,
            "catalog_policy": self.catalog.get("policy"),
        }

    def explain_invalid_pipe(self, pipe_payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self.validate_network({"features": [pipe_payload], "network": pipe_payload.get("network")})
        if not result["issues"]:
            return {"success": True, "message": "This pipe matches the catalog entries currently available. Accepted workspace status still depends on source/review metadata."}
        first = result["issues"][0]
        return {"success": False, "message": first.get("reason", "Pipe did not match the catalog."), "issue": first}


GLOBAL_UTILITY_CATALOG_MANAGER = UtilityCatalogManager()
