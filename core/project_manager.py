from __future__ import annotations

"""
core/project_manager.py

Managed engineering-state layer for the AI civil / CAD / infrastructure design
platform.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
import copy
import uuid

from core.geometry_core import (
    EngineeringObject,
    ProjectModel,
    ReviewIssue,
    RoutingGraph,
    Zone,
    ZoneType,
    _snapshot_serialize,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class DependencyState(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    INVALID = "invalid"
    COMPLETE = "complete"
    FAILED = "failed"


class ConflictSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class VariantStatus(str, Enum):
    ACTIVE = "active"
    SAVED = "saved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass
class DependencyRecord:
    source: str
    target: str
    reason: str = ""
    state: DependencyState = DependencyState.FRESH
    id: str = field(default_factory=lambda: _new_id("dep"))
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictRecord:
    code: str
    message: str
    severity: ConflictSeverity = ConflictSeverity.WARNING
    related_ids: List[str] = field(default_factory=list)
    category: str = "general"
    id: str = field(default_factory=lambda: _new_id("conflict"))
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


@dataclass
class MetricRecord:
    name: str
    value: Any
    units: Optional[str] = None
    category: str = "general"
    id: str = field(default_factory=lambda: _new_id("metric"))
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LinearSystemRecord:
    name: str
    system_type: str
    graph_id: Optional[str] = None
    zone_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    related_system_ids: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: _new_id("system"))
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignSnapshot:
    name: str
    project_state: Dict[str, Any]
    description: str = ""
    id: str = field(default_factory=lambda: _new_id("snapshot"))
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignVariant:
    name: str
    payload: Dict[str, Any]
    status: VariantStatus = VariantStatus.SAVED
    score: Optional[float] = None
    summary: str = ""
    id: str = field(default_factory=lambda: _new_id("variant"))
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    title: str
    description: str = ""
    id: str = field(default_factory=lambda: _new_id("audit"))
    category: str = "general"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateBundle:
    dependencies: Dict[str, DependencyRecord] = field(default_factory=dict)
    conflicts: Dict[str, ConflictRecord] = field(default_factory=dict)
    systems: Dict[str, LinearSystemRecord] = field(default_factory=dict)
    metrics: Dict[str, MetricRecord] = field(default_factory=dict)
    snapshots: Dict[str, DesignSnapshot] = field(default_factory=dict)
    variants: Dict[str, DesignVariant] = field(default_factory=dict)
    audit_log: List[AuditEvent] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


class ProjectManager:
    def __init__(self, project: Optional[ProjectModel] = None) -> None:
        self.project = project or ProjectModel()
        self.state = StateBundle()
        self._transaction_snapshots: Dict[str, str] = {}

    @property
    def name(self) -> str:
        return self.project.name

    @property
    def units(self) -> Any:
        return self.project.units

    def add_zone(self, zone: Zone) -> str:
        return self.project.add_zone(zone)

    def add_object(self, obj: EngineeringObject) -> str:
        return self.project.add_object(obj)

    def add_graph(self, graph: RoutingGraph) -> str:
        return self.project.add_graph(graph)

    def add_issue(self, issue: ReviewIssue) -> str:
        return self.project.add_issue(issue)

    def add_review_issue(self, severity: str, message: str, **meta: Any) -> str:
        issue_id = self.project.add_review_issue(severity, message, **meta)
        self.record_event("review_issue", message, category="qa", severity=severity, **meta)
        return issue_id

    @property
    def dependencies(self) -> List[DependencyRecord]:
        return list(self.state.dependencies.values())

    @property
    def conflicts(self) -> List[ConflictRecord]:
        return list(self.state.conflicts.values())

    @property
    def metrics(self) -> Dict[str, MetricRecord]:
        return {metric.name: metric for metric in self.state.metrics.values()}

    @property
    def engine_state(self) -> Dict[str, Any]:
        return self.state.meta.setdefault("engine_state", {})

    @property
    def system_dirty_state(self) -> Dict[str, Any]:
        return self.state.meta.setdefault("system_dirty_state", {})

    @property
    def latest_outputs(self) -> Dict[str, Any]:
        return self.state.meta.setdefault("latest_outputs", {})

    def objects_by_kind(self, kind: str) -> List[EngineeringObject]:
        return self.project.objects_by_kind(kind)

    def zones_by_type(self, zone_type: ZoneType) -> List[Zone]:
        return self.project.zones_by_type(zone_type)

    def graphs_by_kind(self, kind: str) -> List[RoutingGraph]:
        return self.project.graphs_by_kind(kind)

    def find_object(self, object_id_or_name: str) -> Optional[EngineeringObject]:
        return self.project.find_object(object_id_or_name)

    def find_zone(self, zone_id_or_name: str) -> Optional[Zone]:
        return self.project.find_zone(zone_id_or_name)

    def find_graph(self, graph_id_or_name: str) -> Optional[RoutingGraph]:
        return self.project.find_graph(graph_id_or_name)

    def add_dependency(
        self,
        dependency: DependencyRecord | str,
        target: Optional[str] = None,
        state: DependencyState = DependencyState.FRESH,
        *,
        reason: str = "",
        **context: Any,
    ) -> str:
        if isinstance(dependency, DependencyRecord):
            self.state.dependencies[dependency.id] = dependency
            return dependency.id

        if target is None:
            raise ValueError("target is required when add_dependency is called with source/target strings.")

        dep = DependencyRecord(
            source=dependency,
            target=target,
            reason=reason,
            state=state,
            context=dict(context),
        )
        self.state.dependencies[dep.id] = dep
        return dep.id

    def ensure_dependency(
        self,
        source: str,
        target: str,
        *,
        reason: str = "",
        state: DependencyState = DependencyState.FRESH,
        **context: Any,
    ) -> str:
        for dep in self.state.dependencies.values():
            if dep.source == source and dep.target == target:
                dep.reason = reason or dep.reason
                dep.state = state
                dep.context.update(context)
                return dep.id
        dep = DependencyRecord(source=source, target=target, reason=reason, state=state, context=dict(context))
        self.state.dependencies[dep.id] = dep
        return dep.id

    def invalidate_targets_from_source(self, source: str, reason: Optional[str] = None) -> List[str]:
        affected: List[str] = []
        for dep in self.state.dependencies.values():
            if dep.source == source:
                dep.state = DependencyState.INVALID
                if reason:
                    dep.context["invalidated_reason"] = reason
                affected.append(dep.target)
                self.mark_system_dirty(dep.target, reason=reason or f"Dependency invalidated by '{source}'.", source=source)
        if affected:
            self.record_event(
                "invalidate_targets",
                f"Invalidated {len(affected)} dependent targets from source '{source}'.",
                category="dependency",
                source=source,
                affected=affected,
                reason=reason,
            )
        return affected

    def mark_dependency_state(
        self,
        source: str,
        target: str,
        state: DependencyState,
        *,
        reason: Optional[str] = None,
        **context: Any,
    ) -> None:
        dep_id = self.ensure_dependency(source, target, reason=reason or "", state=state, **context)
        dep = self.state.dependencies[dep_id]
        dep.state = state
        if reason:
            dep.context["reason"] = reason

    def dependencies_for_target(self, target: str) -> List[DependencyRecord]:
        return [dep for dep in self.state.dependencies.values() if dep.target == target]

    def dependencies_from_source(self, source: str) -> List[DependencyRecord]:
        return [dep for dep in self.state.dependencies.values() if dep.source == source]

    def add_conflict(self, conflict: ConflictRecord) -> str:
        self.state.conflicts[conflict.id] = conflict
        self.record_event(
            conflict.code,
            conflict.message,
            category="conflict",
            severity=conflict.severity.value,
            related_ids=list(conflict.related_ids),
        )
        return conflict.id

    def report_conflict(
        self,
        code: str,
        message: str,
        *,
        severity: ConflictSeverity = ConflictSeverity.WARNING,
        related_ids: Optional[Sequence[str]] = None,
        category: str = "general",
        **context: Any,
    ) -> str:
        conflict = ConflictRecord(
            code=code,
            message=message,
            severity=severity,
            related_ids=list(related_ids or []),
            category=category,
            context=dict(context),
        )
        return self.add_conflict(conflict)

    def resolve_conflict(self, conflict_id: str, *, resolution_note: str = "") -> bool:
        conflict = self.state.conflicts.get(conflict_id)
        if conflict is None:
            return False
        conflict.resolved = True
        if resolution_note:
            conflict.context["resolution_note"] = resolution_note
        self.record_event("conflict_resolved", f"Resolved conflict '{conflict.code}'.", category="conflict", conflict_id=conflict_id)
        return True

    def unresolved_conflicts(self) -> List[ConflictRecord]:
        return [c for c in self.state.conflicts.values() if not c.resolved]

    def unresolved_conflicts_by_category(self, category: str) -> List[ConflictRecord]:
        target = str(category or "").strip().lower()
        return [c for c in self.unresolved_conflicts() if str(c.category).lower() == target]

    def add_system(self, system: LinearSystemRecord) -> str:
        self.state.systems[system.id] = system
        return system.id

    def upsert_system(
        self,
        name: str,
        system_type: str,
        *,
        graph_id: Optional[str] = None,
        zone_ids: Optional[Sequence[str]] = None,
        object_ids: Optional[Sequence[str]] = None,
        related_system_ids: Optional[Sequence[str]] = None,
        **meta: Any,
    ) -> str:
        for existing in self.state.systems.values():
            if existing.name == name and existing.system_type == system_type:
                existing.graph_id = graph_id or existing.graph_id
                if zone_ids:
                    existing.zone_ids = list(dict.fromkeys(existing.zone_ids + list(zone_ids)))
                if object_ids:
                    existing.object_ids = list(dict.fromkeys(existing.object_ids + list(object_ids)))
                if related_system_ids:
                    existing.related_system_ids = list(dict.fromkeys(existing.related_system_ids + list(related_system_ids)))
                existing.meta.update(meta)
                return existing.id
        record = LinearSystemRecord(
            name=name,
            system_type=system_type,
            graph_id=graph_id,
            zone_ids=list(zone_ids or []),
            object_ids=list(object_ids or []),
            related_system_ids=list(related_system_ids or []),
            meta=dict(meta),
        )
        self.state.systems[record.id] = record
        return record.id

    def systems_by_type(self, system_type: str) -> List[LinearSystemRecord]:
        target = str(system_type or "").strip().lower()
        return [sys for sys in self.state.systems.values() if sys.system_type.lower() == target]

    def add_metric(self, metric: MetricRecord) -> str:
        self.state.metrics[metric.id] = metric
        return metric.id

    def set_metric(self, name: str, value: Any, *, units: Optional[str] = None, category: str = "general", **meta: Any) -> str:
        existing = next((m for m in self.state.metrics.values() if m.name == name), None)
        if existing is not None:
            existing.value = value
            existing.units = units
            existing.category = category
            existing.meta.update(meta)
            return existing.id
        metric = MetricRecord(name=name, value=value, units=units, category=category, meta=dict(meta))
        self.state.metrics[metric.id] = metric
        return metric.id

    def get_metric(self, name: str, default: Any = None) -> Any:
        for metric in self.state.metrics.values():
            if metric.name == name:
                return metric.value
        return default

    def snapshot(self, name: str, description: str = "", **meta: Any) -> str:
        snap = DesignSnapshot(
            name=name,
            description=description,
            project_state=self._export_state_bundle(
                include_snapshots=False,
                include_variants=False,
                include_audit_log=False,
            ),
            meta=dict(meta),
        )
        self.state.snapshots[snap.id] = snap
        self.record_event("snapshot", f"Created snapshot '{name}'.", category="snapshot", snapshot_id=snap.id)
        return snap.id

    def restore_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        snap = self.state.snapshots.get(snapshot_id)
        if snap is None:
            raise KeyError(f"Snapshot '{snapshot_id}' not found.")

        restored_state = copy.deepcopy(snap.project_state)
        if isinstance(restored_state, dict) and "project" in restored_state and "state" in restored_state:
            preserved_snapshots = copy.deepcopy(self.state.snapshots)
            preserved_variants = copy.deepcopy(self.state.variants)
            preserved_audit_log = copy.deepcopy(self.state.audit_log)
            restored_manager = self.from_dict(restored_state, assume_isolated=True)
            if not restored_manager.state.snapshots:
                restored_manager.state.snapshots = preserved_snapshots
            if not restored_manager.state.variants:
                restored_manager.state.variants = preserved_variants
            if not restored_manager.state.audit_log:
                restored_manager.state.audit_log = preserved_audit_log
            self.project = restored_manager.project
            self.state = restored_manager.state
        elif hasattr(ProjectModel, "from_dict") and callable(getattr(ProjectModel, "from_dict")):
            self.project = ProjectModel.from_dict(restored_state)
        else:
            self.project = ProjectModel(**restored_state)

        self.record_event("snapshot_restore", f"Restored snapshot '{snap.name}'.", category="snapshot", snapshot_id=snapshot_id)
        if isinstance(restored_state, dict) and "project" in restored_state and "state" in restored_state:
            return restored_state
        return self.project.to_dict() if hasattr(self.project, "to_dict") else restored_state

    def save_variant(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        score: Optional[float] = None,
        summary: str = "",
        status: VariantStatus = VariantStatus.SAVED,
        **meta: Any,
    ) -> str:
        variant = DesignVariant(name=name, payload=copy.deepcopy(payload), score=score, summary=summary, status=status, meta=dict(meta))
        self.state.variants[variant.id] = variant
        self.record_event("variant_save", f"Saved variant '{name}'.", category="variant", variant_id=variant.id, score=score)
        return variant.id

    def set_variant_status(self, variant_id: str, status: VariantStatus) -> bool:
        variant = self.state.variants.get(variant_id)
        if variant is None:
            return False
        variant.status = status
        self.record_event("variant_status", f"Variant '{variant.name}' status set to '{status.value}'.", category="variant", variant_id=variant_id)
        return True

    def list_variants(self, *, status: Optional[VariantStatus] = None) -> List[DesignVariant]:
        variants = list(self.state.variants.values())
        if status is not None:
            variants = [v for v in variants if v.status == status]
        return variants

    def record_event(self, title: str, description: str = "", *, category: str = "general", **meta: Any) -> str:
        event = AuditEvent(title=title, description=description, category=category, meta=dict(meta))
        self.state.audit_log.append(event)
        return event.id

    def log(self, title: str, description: str = "", *, category: str = "general", **meta: Any) -> str:
        return self.record_event(title, description, category=category, **meta)

    def begin_transaction(self, name: str = "transaction") -> str:
        snapshot_id = self.snapshot(f"{name}_snapshot", description=f"Auto snapshot for {name}")
        transaction_id = _new_id("txn")
        self._transaction_snapshots[transaction_id] = snapshot_id
        return transaction_id

    def commit_transaction(self, transaction_id: str) -> None:
        self._transaction_snapshots.pop(transaction_id, None)

    def rollback_transaction(self, transaction_id: str) -> None:
        snapshot_id = self._transaction_snapshots.pop(transaction_id, None)
        if snapshot_id is not None:
            self.restore_snapshot(snapshot_id)

    def invalidate_from(self, source: str, include_source: bool = False, reason: Optional[str] = None) -> List[str]:
        affected = self.invalidate_targets_from_source(source, reason=reason)
        if include_source and source not in affected:
            affected.append(source)
            self.mark_system_dirty(source, reason=reason or f"System '{source}' was explicitly invalidated.", source=source)
        return affected

    def get_invalidated_targets(self) -> List[str]:
        targets: List[str] = []
        for dep in self.state.dependencies.values():
            if dep.state in {DependencyState.INVALID, DependencyState.STALE, DependencyState.FAILED}:
                targets.append(dep.target)
        return list(dict.fromkeys(targets))

    def list_rerun_queue(self) -> List[str]:
        return self.get_invalidated_targets()

    def _ensure_engine_record(self, name: str) -> Dict[str, Any]:
        return self.engine_state.setdefault(
            name,
            {"status": "idle", "message": "", "warnings": [], "errors": [], "dirty_state": "dirty", "dirty_reasons": []},
        )

    def mark_system_dirty(self, name: str, message: str = "", *, reason: Optional[str] = None, source: Optional[str] = None) -> None:
        record = self._ensure_engine_record(name)
        dirty_reason = reason or message or f"System '{name}' marked dirty."
        reasons = list(record.get("dirty_reasons", []) or [])
        if dirty_reason not in reasons:
            reasons.append(dirty_reason)
        record["dirty_state"] = "dirty"
        record["dirty_reasons"] = reasons
        if message:
            record["message"] = message
        state_row = self.system_dirty_state.setdefault(name, {"state": "dirty", "reasons": []})
        if dirty_reason not in state_row["reasons"]:
            state_row["reasons"].append(dirty_reason)
        state_row["state"] = "dirty"
        if source:
            state_row["source"] = source
        if isinstance(getattr(self.project, "meta", None), dict):
            self.project.meta["system_dirty_state"] = _snapshot_serialize(self.system_dirty_state)

    def mark_system_clean(self, name: str, message: str = "") -> None:
        record = self._ensure_engine_record(name)
        record["dirty_state"] = "clean"
        record["dirty_reasons"] = []
        if message:
            record["message"] = message
        self.system_dirty_state[name] = {"state": "clean", "reasons": []}
        if isinstance(getattr(self.project, "meta", None), dict):
            self.project.meta["system_dirty_state"] = _snapshot_serialize(self.system_dirty_state)

    def is_system_dirty(self, name: str) -> bool:
        state_row = self.system_dirty_state.get(name)
        if isinstance(state_row, dict) and str(state_row.get("state", "")).lower() == "dirty":
            return True
        record = self._ensure_engine_record(name)
        return str(record.get("dirty_state", "dirty")).lower() != "clean"

    def mark_system_running(self, name: str, message: str = "") -> None:
        record = self._ensure_engine_record(name)
        record.update({"status": "running", "message": message})

    def mark_system_complete(self, name: str, message: str = "", warnings: Optional[Sequence[str]] = None) -> None:
        record = self._ensure_engine_record(name)
        record.update({"status": "complete", "message": message, "warnings": list(warnings or [])})
        self.mark_system_clean(name, message)

    def mark_system_failed(self, name: str, message: str = "", errors: Optional[Sequence[str]] = None) -> None:
        record = self._ensure_engine_record(name)
        record.update({"status": "failed", "message": message, "errors": list(errors or [])})
        self.mark_system_dirty(name, message=message, reason=message)

    def mark_system_skipped(self, name: str, message: str = "") -> None:
        record = self._ensure_engine_record(name)
        record.update({"status": "skipped", "message": message})
        self.mark_system_clean(name, message)

    def export_metrics(self, *, summary_only: bool = False) -> Dict[str, Any]:
        metrics = {
            metric.name: {
                "value": metric.value,
                "units": metric.units,
                "category": metric.category,
                "meta": dict(metric.meta),
            }
            for metric in self.state.metrics.values()
        }

        conflict_counts = {"info": 0, "warning": 0, "error": 0, "resolved": 0, "active": 0, "total": len(self.state.conflicts)}
        for conflict in self.state.conflicts.values():
            severity_value = getattr(conflict, "severity", ConflictSeverity.WARNING.value)
            severity = getattr(severity_value, "value", severity_value)
            severity = str(severity).lower()
            if severity in conflict_counts:
                conflict_counts[severity] += 1
            if conflict.resolved:
                conflict_counts["resolved"] += 1
            else:
                conflict_counts["active"] += 1

        dependency_counts = {state.value: 0 for state in DependencyState}
        dependency_counts["total"] = len(self.state.dependencies)
        for dep in self.state.dependencies.values():
            state_value = getattr(dep, "state", DependencyState.FRESH.value)
            state = getattr(state_value, "value", state_value)
            state = str(state).lower()
            dependency_counts[state] = dependency_counts.get(state, 0) + 1

        engine_state = _snapshot_serialize(self.engine_state)
        dirty_state = _snapshot_serialize(self.system_dirty_state)
        system_counts = {
            "declared": len(self.state.systems),
            "running": 0,
            "complete": 0,
            "failed": 0,
            "skipped": 0,
            "idle": 0,
            "total": len(self.state.systems),
        }
        for record in engine_state.values():
            status = str((record or {}).get("status", "idle")).lower()
            if status in system_counts:
                system_counts[status] += 1
            else:
                system_counts["idle"] += 1
        system_counts["total"] = max(system_counts["total"], len(engine_state))

        project_counts = {
            "levels": len(getattr(self.project, "levels", {}) or {}),
            "zones": len(getattr(self.project, "zones", {}) or {}),
            "obstacles": len(getattr(self.project, "obstacles", {}) or {}),
            "alignments": len(getattr(self.project, "alignments", {}) or {}),
            "corridors": len(getattr(self.project, "corridors", {}) or {}),
            "objects": len(getattr(self.project, "objects", {}) or {}),
            "graphs": len(getattr(self.project, "graphs", {}) or {}),
            "drawing_entities": len(getattr(self.project, "drawing_entities", []) or []),
            "review_issues": len(getattr(self.project, "review_issues", []) or []),
        }

        manager_meta = _snapshot_serialize(self.state.meta)
        manager_meta.pop("engine_state", None)
        manager_meta.pop("latest_outputs", None)
        result = {
            "metrics": metrics,
            "conflict_counts": conflict_counts,
            "dependency_counts": dependency_counts,
            "system_counts": system_counts,
            "project_counts": project_counts,
            "dirty_state": dirty_state,
        }
        if not summary_only:
            result["engine_state"] = engine_state
            result["latest_outputs"] = _snapshot_serialize(self.latest_outputs)
            result["manager_meta"] = manager_meta
        return result

    def register_graph_as_system(
        self,
        graph_id: str,
        *,
        name: Optional[str] = None,
        system_type: str = "generic_linear",
        related_zone_ids: Optional[Sequence[str]] = None,
        related_object_ids: Optional[Sequence[str]] = None,
        **meta: Any,
    ) -> str:
        graph = self.project.graphs.get(graph_id)
        if graph is None:
            raise KeyError(f"Graph '{graph_id}' not found.")
        return self.upsert_system(
            name=name or graph.name or graph.id,
            system_type=system_type,
            graph_id=graph_id,
            zone_ids=list(related_zone_ids or []),
            object_ids=list(related_object_ids or []),
            **meta,
        )

    def assert_references_valid(self) -> List[str]:
        errors: List[str] = []
        zone_ids = set(self.project.zones.keys())
        object_ids = set(self.project.objects.keys())
        graph_ids = set(self.project.graphs.keys())

        for dep in self.state.dependencies.values():
            if not dep.source:
                errors.append(f"Dependency {dep.id} missing source.")
            if not dep.target:
                errors.append(f"Dependency {dep.id} missing target.")

        for conflict in self.state.conflicts.values():
            for rel in conflict.related_ids:
                if rel not in zone_ids and rel not in object_ids and rel not in graph_ids:
                    errors.append(f"Conflict {conflict.id} references unknown id '{rel}'.")

        for system in self.state.systems.values():
            if system.graph_id and system.graph_id not in graph_ids:
                errors.append(f"System {system.id} references unknown graph '{system.graph_id}'.")
            for zid in system.zone_ids:
                if zid not in zone_ids:
                    errors.append(f"System {system.id} references unknown zone '{zid}'.")
            for oid in system.object_ids:
                if oid not in object_ids:
                    errors.append(f"System {system.id} references unknown object '{oid}'.")
        return errors

    def _export_state_bundle(
        self,
        *,
        include_snapshots: bool = True,
        include_variants: bool = True,
        include_audit_log: bool = True,
    ) -> Dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "state": {
                "dependencies": {did: _dependency_to_dict(dep) for did, dep in self.state.dependencies.items()},
                "conflicts": {cid: _conflict_to_dict(conflict) for cid, conflict in self.state.conflicts.items()},
                "systems": {sid: _system_to_dict(system) for sid, system in self.state.systems.items()},
                "metrics": {mid: _metric_to_dict(metric) for mid, metric in self.state.metrics.items()},
                "snapshots": (
                    {sid: _snapshot_to_dict(snapshot) for sid, snapshot in self.state.snapshots.items()}
                    if include_snapshots
                    else {}
                ),
                "variants": (
                    {vid: _variant_to_dict(variant) for vid, variant in self.state.variants.items()}
                    if include_variants
                    else {}
                ),
                "audit_log": (
                    [_audit_event_to_dict(event) for event in self.state.audit_log]
                    if include_audit_log
                    else []
                ),
                "meta": _snapshot_serialize(self.state.meta),
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._export_state_bundle()

    @classmethod
    def from_project(cls, project: ProjectModel) -> "ProjectManager":
        return cls(project=project)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, assume_isolated: bool = False) -> "ProjectManager":
        if not isinstance(data, dict):
            raise TypeError("ProjectManager.from_dict expects a dict payload.")

        project_payload = data.get("project", {}) if assume_isolated else copy.deepcopy(data.get("project", {}))
        state_payload = data.get("state", {}) if assume_isolated else copy.deepcopy(data.get("state", {}))
        manager = cls(
            project=ProjectModel.from_dict(project_payload, assume_isolated=assume_isolated)
            if project_payload
            else ProjectModel()
        )

        for dep_id, dep in (state_payload.get("dependencies") or {}).items():
            manager.state.dependencies[dep_id] = DependencyRecord(
                id=dep.get("id", dep_id),
                source=dep.get("source", ""),
                target=dep.get("target", ""),
                reason=dep.get("reason", ""),
                state=DependencyState(dep.get("state", DependencyState.STALE.value)),
                context=dep.get("context", {}) if assume_isolated else copy.deepcopy(dep.get("context", {})),
            )

        for conflict_id, conflict in (state_payload.get("conflicts") or {}).items():
            manager.state.conflicts[conflict_id] = ConflictRecord(
                id=conflict.get("id", conflict_id),
                code=conflict.get("code", "CONFLICT"),
                message=conflict.get("message", ""),
                severity=ConflictSeverity(conflict.get("severity", ConflictSeverity.WARNING.value)),
                related_ids=list(conflict.get("related_ids", [])),
                category=conflict.get("category", "general"),
                context=conflict.get("context", {}) if assume_isolated else copy.deepcopy(conflict.get("context", {})),
                resolved=bool(conflict.get("resolved", False)),
            )

        for sys_id, system in (state_payload.get("systems") or {}).items():
            manager.state.systems[sys_id] = LinearSystemRecord(
                id=system.get("id", sys_id),
                name=system.get("name", ""),
                system_type=system.get("system_type", "generic"),
                graph_id=system.get("graph_id"),
                zone_ids=list(system.get("zone_ids", [])),
                object_ids=list(system.get("object_ids", [])),
                related_system_ids=list(system.get("related_system_ids", [])),
                meta=system.get("meta", {}) if assume_isolated else copy.deepcopy(system.get("meta", {})),
            )

        for metric_id, metric in (state_payload.get("metrics") or {}).items():
            manager.state.metrics[metric_id] = MetricRecord(
                id=metric.get("id", metric_id),
                name=metric.get("name", ""),
                value=metric.get("value") if assume_isolated else copy.deepcopy(metric.get("value")),
                units=metric.get("units"),
                category=metric.get("category", "general"),
                meta=metric.get("meta", {}) if assume_isolated else copy.deepcopy(metric.get("meta", {})),
            )

        for snap_id, snap in (state_payload.get("snapshots") or {}).items():
            manager.state.snapshots[snap_id] = DesignSnapshot(
                id=snap.get("id", snap_id),
                name=snap.get("name", snap_id),
                description=snap.get("description", ""),
                project_state=snap.get("project_state", {}) if assume_isolated else copy.deepcopy(snap.get("project_state", {})),
                meta=snap.get("meta", {}) if assume_isolated else copy.deepcopy(snap.get("meta", {})),
            )

        for var_id, variant in (state_payload.get("variants") or {}).items():
            manager.state.variants[var_id] = DesignVariant(
                id=variant.get("id", var_id),
                name=variant.get("name", var_id),
                payload=variant.get("payload", {}) if assume_isolated else copy.deepcopy(variant.get("payload", {})),
                status=VariantStatus(variant.get("status", VariantStatus.SAVED.value)),
                score=variant.get("score"),
                summary=variant.get("summary", ""),
                meta=variant.get("meta", {}) if assume_isolated else copy.deepcopy(variant.get("meta", {})),
            )

        manager.state.audit_log = [
            AuditEvent(
                id=event.get("id", _new_id("audit")),
                title=event.get("title", "event"),
                description=event.get("description", ""),
                category=event.get("category", "general"),
                meta=event.get("meta", {}) if assume_isolated else copy.deepcopy(event.get("meta", {})),
            )
            for event in (state_payload.get("audit_log") or [])
            if isinstance(event, dict)
        ]
        manager.state.meta = state_payload.get("meta", {}) if assume_isolated else copy.deepcopy(state_payload.get("meta", {}))
        return manager

    @classmethod
    def from_command(cls, parsed: Dict[str, Any]) -> "ProjectManager":
        manager = cls(project=ProjectModel.from_command(parsed))
        manager.record_event("from_command", "Initialized project manager from parsed command payload.", category="bootstrap")
        manager.snapshot("initial_from_command", source="command")
        return manager


def _dependency_to_dict(dep: DependencyRecord) -> Dict[str, Any]:
    return {
        "id": dep.id,
        "source": dep.source,
        "target": dep.target,
        "reason": dep.reason,
        "state": dep.state.value,
        "context": _snapshot_serialize(dep.context),
    }


def _conflict_to_dict(conflict: ConflictRecord) -> Dict[str, Any]:
    return {
        "id": conflict.id,
        "code": conflict.code,
        "message": conflict.message,
        "severity": conflict.severity.value,
        "related_ids": list(conflict.related_ids),
        "category": conflict.category,
        "context": _snapshot_serialize(conflict.context),
        "resolved": conflict.resolved,
    }


def _metric_to_dict(metric: MetricRecord) -> Dict[str, Any]:
    return {
        "id": metric.id,
        "name": metric.name,
        "value": _snapshot_serialize(metric.value),
        "units": metric.units,
        "category": metric.category,
        "meta": _snapshot_serialize(metric.meta),
    }


def _system_to_dict(system: LinearSystemRecord) -> Dict[str, Any]:
    return {
        "id": system.id,
        "name": system.name,
        "system_type": system.system_type,
        "graph_id": system.graph_id,
        "zone_ids": list(system.zone_ids),
        "object_ids": list(system.object_ids),
        "related_system_ids": list(system.related_system_ids),
        "meta": _snapshot_serialize(system.meta),
    }


def _snapshot_to_dict(snapshot: DesignSnapshot) -> Dict[str, Any]:
    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "description": snapshot.description,
        "project_state": _snapshot_serialize(snapshot.project_state),
        "meta": _snapshot_serialize(snapshot.meta),
    }


def _variant_to_dict(variant: DesignVariant) -> Dict[str, Any]:
    return {
        "id": variant.id,
        "name": variant.name,
        "payload": _snapshot_serialize(variant.payload),
        "status": variant.status.value,
        "score": variant.score,
        "summary": variant.summary,
        "meta": _snapshot_serialize(variant.meta),
    }


def _audit_event_to_dict(event: AuditEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "meta": _snapshot_serialize(event.meta),
    }
