import type { MutableRefObject } from "react";

import type { BuildingPlacement, ChatMessage, SiteObjectType } from "../types";
import type { DraftBlockDefinition, DraftUndoAction, RecentChange } from "./dashboardTypes";
import {
  cloneBuildingPlacementForUndo,
  cloneBuildingPlacementWithUpdatesForUndo,
} from "./dashboardObjectManagerTrace";
import {
  formatDraftMeasure,
  getObjectEditBlocker,
  getPolygonArea,
  selectedObjectsToSemanticArea,
} from "./objectGeometry";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";
import type { EngineeringSystemKey } from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

export type ObjectManagerBlockActions = {
  appendChatMessage: AppendChatMessage;
  clearGeneratedPreview: () => void;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: RecordRecentChange;
  reportObjectActionBlocker: (message: string) => void;
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCombineObjectName: StateSetter<string>;
  setCombineObjectType: StateSetter<SiteObjectType>;
  setDraftBlockLibrary: StateSetter<DraftBlockDefinition[]>;
  setDraftBlockName: StateSetter<string>;
  setObjectManagerStatusMessage: (message: string) => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  persistDraftRefresh: (reason: string) => void;
};

export function runObjectManagerCombineSelected({
  buildingPlacements,
  buildingPlacementsRef,
  selectedObjectIds,
  combineObjectName,
  combineObjectType,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  selectedObjectIds: string[];
  combineObjectName: string;
  combineObjectType: SiteObjectType;
  actions: ObjectManagerBlockActions;
}) {
  actions.clearGeneratedPreview();
  const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  if (targets.length < 1) {
    actions.reportObjectActionBlocker("Combine needs input: select connected drawn linework or one drawn area first.");
    return;
  }
  const editable = targets.filter(
    (item) =>
      item.type !== "site" &&
      !item.locked &&
      !getObjectEditBlocker(item, "type") &&
      !getObjectEditBlocker(item, "style"),
  );
  if (editable.length < 1) {
    actions.reportObjectActionBlocker("Combine needs input: selected objects are locked or source-only.");
    return;
  }
  let effectiveEditable = editable;
  let semanticArea = selectedObjectsToSemanticArea(effectiveEditable);
  if (!semanticArea.valid && editable.length > 1) {
    const customLineworkEditable = editable.filter(
      (item) =>
        item.geometryType === "polyline" &&
        (item.type === "custom" || /^custom line/i.test(String(item.label || ""))),
    );
    const lineworkEditable = customLineworkEditable.length >= 3
      ? customLineworkEditable
      : editable.filter((item) => item.geometryType === "polyline");
    const lineworkArea = selectedObjectsToSemanticArea(lineworkEditable);
    if (lineworkArea.valid && lineworkArea.geometry.length >= 3) {
      effectiveEditable = lineworkEditable;
      semanticArea = lineworkArea;
    }
  }
  if (!semanticArea.valid || semanticArea.geometry.length < 3) {
    actions.reportObjectActionBlocker(`Combine needs input: ${semanticArea.blockers[0] || "selected geometry does not form one closed area."}`);
    return;
  }
  const validPoints = semanticArea.geometry;
  const xs = validPoints.map(([x]) => x);
  const ys = validPoints.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = Math.max(8, maxX - minX);
  const depth = Math.max(8, maxY - minY);
  const linearTypes = new Set<SiteObjectType>(["driveway", "road", "sidewalk", "utility_corridor", "entrance"]);
  const pointTypes = new Set<SiteObjectType>(["inlet", "outfall", "hydrant", "manhole"]);
  const nextType = combineObjectType || "custom";
  const existingCount = buildingPlacements.filter((item) => item.type === nextType).length + 1;
  const nextLabel = combineObjectName.trim() || `${SITE_OBJECT_CATALOG[nextType]?.label ?? "Combined Object"} ${existingCount}`;
  const nextGeometryType = pointTypes.has(nextType) ? "point" : linearTypes.has(nextType) ? "polyline" : "polygon";
  const nextGeometry = nextGeometryType === "point"
    ? ([[minX + width / 2, minY + depth / 2]] as Array<[number, number]>)
    : validPoints;
  const nextId = `${nextType}-combined-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const semanticAreaSf = getPolygonArea(validPoints);
  const combinedObject: BuildingPlacement = {
    id: nextId,
    label: nextLabel,
    type: nextType,
    use: SITE_OBJECT_CATALOG[nextType]?.use,
    x: nextGeometryType === "point" ? minX + width / 2 - 5 : minX,
    y: nextGeometryType === "point" ? minY + depth / 2 - 5 : minY,
    w: nextGeometryType === "point" ? 10 : width,
    d: nextGeometryType === "point" ? 10 : depth,
    rotation: 0,
    locked: false,
    placed: true,
    source: "manual_drawn",
    generated: false,
    geometryType: nextGeometryType,
    geometry: nextGeometry,
    capabilities: {
      movable: true,
      resizable: nextGeometryType !== "polyline",
      rotatable: nextGeometryType === "polygon",
      deletable: true,
    },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    meta: {
      category: SITE_OBJECT_CATALOG[nextType]?.category ?? "advanced",
      source: "semantic_drafting_conversion",
      review_status: "engineer_review_required",
      engineering_status: "draft_review_required",
      handoff_status: "draft_review_required",
      construction_release_allowed: false,
      semantic_geometry_state: "engineering_object_geometry",
      semantic_object_model: "cad_engineering_objects_v1",
      semantic_source_mode: semanticArea.sourceMode,
      canonical_object_type: nextType,
      footprint_area_sf: semanticAreaSf,
      combined_from_object_ids: effectiveEditable.map((item) => item.id),
      combined_from_labels: effectiveEditable.map((item) => item.label),
      combined_source_count: effectiveEditable.length,
      affected_systems: actions.systemsImpactedByPlacement({ ...effectiveEditable[0], type: nextType }),
    },
  };
  const undo: DraftUndoAction = {
    action: "combine",
    object: combinedObject,
    hiddenSources: effectiveEditable.map(cloneBuildingPlacementForUndo),
    label: "combine objects",
  };
  const editableIds = new Set(effectiveEditable.map((item) => item.id));
  const nextPlacements = [
    ...buildingPlacementsRef.current.map((item) =>
      editableIds.has(item.id)
        ? {
            ...item,
            meta: {
              ...(item.meta ?? {}),
              ui_hidden: true,
              combined_into_object_id: nextId,
              combined_into_label: nextLabel,
            },
          }
        : item,
    ),
    combinedObject,
  ];
  buildingPlacementsRef.current = nextPlacements;
  actions.setBuildingPlacements(nextPlacements);
  actions.setSelectedObjectIds([nextId]);
  actions.setActivePlacementId(nextId);
  actions.setCombineObjectName("");
  actions.setCombineObjectType("custom");
  actions.markSystemsStale(actions.systemsImpactedByPlacement(combinedObject));
  actions.recordDraftUndoAction(undo);
  actions.recordRecentChange({
    type: "object_added",
    label: "Objects combined",
    detail: `${effectiveEditable.length} drawn objects were combined into ${nextLabel}. Source pieces were hidden, not deleted.`,
    undo,
  });
  const message = semanticArea.sourceMode === "program_group_bounds"
    ? `Combined ${effectiveEditable.length} drawn objects into ${nextLabel}. Group bounds area: ${formatDraftMeasure(semanticAreaSf, "sf")}.`
    : `Combined ${effectiveEditable.length} drawn geometry piece${effectiveEditable.length === 1 ? "" : "s"} into ${nextLabel} as a semantic ${SITE_OBJECT_CATALOG[nextType]?.label ?? "object"}. Area: ${formatDraftMeasure(semanticAreaSf, "sf")}.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", `${message} Source pieces are hidden, preserved for trace, and the new object is review-required.`, "status");
  actions.persistDraftRefresh("Refreshing preview after combining drawn objects...");
}

export function runObjectManagerSaveBlock({
  buildingPlacements,
  selectedObjectIds,
  draftBlockName,
  combineObjectType,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  draftBlockName: string;
  combineObjectType: SiteObjectType;
  actions: ObjectManagerBlockActions;
}) {
  const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  const editable = targets.filter(
    (item) =>
      item.type !== "site" &&
      !item.locked &&
      !getObjectEditBlocker(item, "copy") &&
      !item.meta?.ui_hidden,
  );
  if (!editable.length) {
    actions.reportObjectActionBlocker("Save block blocked: select one or more visible editable draft objects first.");
    return;
  }
  const name = draftBlockName.trim() || `${editable[0].label || "Draft"} Block`;
  const type = combineObjectType || editable[0].type || "custom";
  const nextBlock: DraftBlockDefinition = {
    id: `draft-block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    type,
    objects: editable.map(cloneBuildingPlacementForUndo),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    revision: 1,
  };
  actions.setDraftBlockLibrary((prev) => [nextBlock, ...prev.filter((block) => block.name !== name)].slice(0, 12));
  actions.setDraftBlockName("");
  const message = `Saved ${name} as a reusable draft block with ${editable.length} source object${editable.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(`${message} Inserts remain review-required draft geometry.`);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_added",
    label: "Draft block saved",
    detail: `${name} saved from ${editable.length} selected draft object${editable.length === 1 ? "" : "s"}.`,
    undoBlockedReason: "Remove or replace saved draft blocks from the block library if needed.",
  });
}

export function runObjectManagerInsertBlock({
  definition,
  buildingPlacements,
  actions,
}: {
  definition: DraftBlockDefinition;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBlockActions;
}) {
  actions.clearGeneratedPreview();
  if (!definition.objects.length) {
    actions.reportObjectActionBlocker(`Insert block blocked: ${definition.name} has no saved source objects.`);
    return;
  }
  const stamp = Date.now();
  const insertIndex = buildingPlacements.filter((item) => item.meta?.draft_block_definition_id === definition.id).length + 1;
  const dx = 32 + insertIndex * 18;
  const dy = 32 + insertIndex * 18;
  const copiedSources = definition.objects.map((source, sourceIndex): BuildingPlacement => ({
    ...source,
    id: `${definition.id}-source-${stamp}-${sourceIndex}-${Math.random().toString(36).slice(2, 8)}`,
    label: `${source.label} Block Source`,
    x: (source.x ?? 0) + dx,
    y: (source.y ?? 0) + dy,
    source: "manual_drawn",
    generated: false,
    locked: false,
    placed: true,
    geometry: source.geometry?.map(([x, y]) => [x + dx, y + dy]),
    capabilities: {
      movable: true,
      resizable: source.capabilities?.resizable ?? true,
      rotatable: source.capabilities?.rotatable ?? true,
      deletable: true,
    },
    meta: {
      ...(source.meta ?? {}),
      ui_hidden: true,
      source: "manual_drawn_block_source",
      draft_block_definition_id: definition.id,
      draft_block_definition_name: definition.name,
      review_status: "engineer_review_required",
      engineering_status: "draft_review_required",
      handoff_status: "draft_review_required",
      construction_release_allowed: false,
    },
  }));
  const sourcePoints = copiedSources.flatMap((item) => {
    if (Array.isArray(item.geometry) && item.geometry.length) return item.geometry;
    const x = item.x ?? 0;
    const y = item.y ?? 0;
    return [
      [x, y],
      [x + item.w, y],
      [x + item.w, y + item.d],
      [x, y + item.d],
    ] as Array<[number, number]>;
  });
  const xs = sourcePoints.map(([x]) => x).filter(Number.isFinite);
  const ys = sourcePoints.map(([, y]) => y).filter(Number.isFinite);
  if (!xs.length || !ys.length) {
    actions.reportObjectActionBlocker(`Insert block blocked: ${definition.name} source geometry is invalid.`);
    return;
  }
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = Math.max(8, maxX - minX);
  const depth = Math.max(8, maxY - minY);
  const linearTypes = new Set<SiteObjectType>(["driveway", "road", "sidewalk", "utility_corridor", "entrance"]);
  const pointTypes = new Set<SiteObjectType>(["inlet", "outfall", "hydrant", "manhole"]);
  const geometryType = pointTypes.has(definition.type)
    ? "point"
    : linearTypes.has(definition.type)
      ? "polyline"
      : "polygon";
  const blockId = `${definition.type}-block-${stamp}-${Math.random().toString(36).slice(2, 8)}`;
  const blockLabel = `${definition.name} Insert ${insertIndex}`;
  const blockObject: BuildingPlacement = {
    id: blockId,
    label: blockLabel,
    type: definition.type,
    use: SITE_OBJECT_CATALOG[definition.type]?.use,
    x: geometryType === "point" ? minX + width / 2 - 5 : minX,
    y: geometryType === "point" ? minY + depth / 2 - 5 : minY,
    w: geometryType === "point" ? 10 : width,
    d: geometryType === "point" ? 10 : depth,
    rotation: 0,
    locked: false,
    placed: true,
    source: "manual_drawn",
    generated: false,
    geometryType,
    geometry:
      geometryType === "point"
        ? ([[minX + width / 2, minY + depth / 2]] as Array<[number, number]>)
        : geometryType === "polyline"
          ? sourcePoints
          : ([
              [minX, minY],
              [maxX, minY],
              [maxX, maxY],
              [minX, maxY],
            ] as Array<[number, number]>),
    capabilities: {
      movable: true,
      resizable: geometryType !== "polyline",
      rotatable: geometryType === "polygon",
      deletable: true,
    },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    meta: {
      category: SITE_OBJECT_CATALOG[definition.type]?.category ?? "advanced",
      source: "manual_drawn_block_insert",
      draft_block_definition_id: definition.id,
      draft_block_definition_name: definition.name,
      review_status: "engineer_review_required",
      engineering_status: "draft_review_required",
      handoff_status: "draft_review_required",
      construction_release_allowed: false,
      combined_from_object_ids: copiedSources.map((item) => item.id),
      combined_from_labels: copiedSources.map((item) => item.label),
      combined_source_count: copiedSources.length,
    },
  };
  const linkedSources = copiedSources.map((source) => ({
    ...source,
    meta: {
      ...(source.meta ?? {}),
      combined_into_object_id: blockId,
      combined_into_label: blockLabel,
    },
  }));
  const createdObjects = [...linkedSources, blockObject];
  actions.setBuildingPlacements((prev) => [...prev, ...createdObjects]);
  actions.setSelectedObjectIds([blockId]);
  actions.setActivePlacementId(blockId);
  createdObjects.forEach((item) => actions.markSystemsStale(actions.systemsImpactedByPlacement(item)));
  const undo: DraftUndoAction = { action: "add_many", objects: createdObjects, label: "block insert" };
  actions.recordDraftUndoAction(undo);
  actions.recordRecentChange({
    type: "object_added",
    label: "Draft block inserted",
    detail: `${definition.name} inserted as ${blockLabel} with ${linkedSources.length} hidden source trace piece${linkedSources.length === 1 ? "" : "s"}.`,
    undo,
  });
  const message = `Inserted ${definition.name} as ${blockLabel} with ${linkedSources.length} hidden source trace piece${linkedSources.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(`${message} It remains review-required draft geometry.`);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", `${message} Use Explode combined if you need to edit the source pieces.`, "status");
  actions.persistDraftRefresh("Refreshing preview after block insert...");
}

export function runObjectManagerUpdateBlock({
  definition,
  buildingPlacements,
  selectedObjectIds,
  activePlacementId,
  combineObjectType,
  actions,
}: {
  definition: DraftBlockDefinition;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  activePlacementId: string | null;
  combineObjectType: SiteObjectType;
  actions: ObjectManagerBlockActions;
}) {
  const selectedRegularObjects = buildingPlacements.filter(
    (item) =>
      selectedObjectIds.includes(item.id) &&
      item.type !== "site" &&
      !item.locked &&
      !getObjectEditBlocker(item, "copy") &&
      !item.meta?.ui_hidden,
  );
  const activeObject = activePlacementId
    ? buildingPlacements.find((item) => item.id === activePlacementId)
    : null;
  const selectedBlockSourceIds =
    activeObject?.meta?.draft_block_definition_id === definition.id &&
    Array.isArray(activeObject.meta?.combined_from_object_ids)
      ? activeObject.meta.combined_from_object_ids.map((id) => String(id)).filter(Boolean)
      : [];
  const selectedBlockSources = selectedBlockSourceIds.length
    ? buildingPlacements
        .filter((item) => selectedBlockSourceIds.includes(item.id))
        .map((item) => ({
          ...item,
          meta: {
            ...(item.meta ?? {}),
            ui_hidden: false,
            combined_into_object_id: undefined,
            combined_into_label: undefined,
          },
        }))
    : [];
  const sourceObjects = selectedRegularObjects.length ? selectedRegularObjects : selectedBlockSources;
  if (!sourceObjects.length) {
    actions.reportObjectActionBlocker(`Update block blocked: select editable draft objects or a placed ${definition.name} block insert first.`);
    return;
  }
  const nextType = selectedRegularObjects.length
    ? combineObjectType || selectedRegularObjects[0].type || definition.type
    : activeObject?.type || definition.type;
  const nextDefinition: DraftBlockDefinition = {
    ...definition,
    type: nextType,
    objects: sourceObjects.map((item) => ({
      ...cloneBuildingPlacementForUndo(item),
      locked: false,
      source: "manual_drawn",
      generated: false,
      placed: true,
      meta: {
        ...(item.meta ?? {}),
        ui_hidden: false,
        source: "manual_drawn_block_definition",
        draft_block_definition_id: definition.id,
        draft_block_definition_name: definition.name,
        review_status: "engineer_review_required",
        engineering_status: "draft_review_required",
        handoff_status: "draft_review_required",
        construction_release_allowed: false,
        combined_into_object_id: undefined,
        combined_into_label: undefined,
      },
    })),
    createdAt: definition.createdAt,
    updatedAt: Date.now(),
    revision: (definition.revision ?? 1) + 1,
  };
  actions.setDraftBlockLibrary((prev) =>
    prev.map((block) => (block.id === definition.id ? nextDefinition : block)),
  );
  const message = `Updated ${definition.name} block definition from ${sourceObjects.length} draft source object${sourceObjects.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(`${message} Future inserts use the updated review geometry.`);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_style_changed",
    label: "Draft block updated",
    detail: `${definition.name} block definition updated from ${sourceObjects.length} source object${sourceObjects.length === 1 ? "" : "s"}.`,
    undoBlockedReason: "Saved block library updates are local drafting setup; save a replacement block if you need a previous version.",
  });
}

export function runObjectManagerRenameBlock({
  definition,
  rawName,
  draftBlockLibrary,
  actions,
}: {
  definition: DraftBlockDefinition;
  rawName: string;
  draftBlockLibrary: DraftBlockDefinition[];
  actions: ObjectManagerBlockActions;
}) {
  const nextName = rawName.trim();
  if (!nextName) {
    actions.reportObjectActionBlocker("Rename block blocked: provide a block name.");
    return;
  }
  if (nextName === definition.name) {
    return;
  }
  const duplicate = draftBlockLibrary.some(
    (block) => block.id !== definition.id && block.name.toLowerCase() === nextName.toLowerCase(),
  );
  if (duplicate) {
    actions.reportObjectActionBlocker(`Rename block blocked: a saved block named ${nextName} already exists.`);
    return;
  }
  const previousName = definition.name;
  actions.setDraftBlockLibrary((prev) =>
    prev.map((block) =>
      block.id === definition.id
        ? {
            ...block,
            name: nextName,
            updatedAt: Date.now(),
            revision: (block.revision ?? 1) + 1,
          }
        : block,
    ),
  );
  const message = `Renamed saved block ${previousName} to ${nextName}.`;
  actions.setObjectManagerStatusMessage(`${message} Existing placed inserts keep their current labels; future inserts use the new block name.`);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_renamed",
    label: "Draft block renamed",
    detail: `${previousName} saved block renamed to ${nextName}. Existing placed inserts were not changed.`,
    undoBlockedReason: "Saved block library names can be changed again from Object Manager.",
  });
}

export function runObjectManagerDeleteBlock({
  definition,
  draftBlockLibrary,
  actions,
}: {
  definition: DraftBlockDefinition;
  draftBlockLibrary: DraftBlockDefinition[];
  actions: ObjectManagerBlockActions;
}) {
  const exists = draftBlockLibrary.some((block) => block.id === definition.id);
  if (!exists) {
    actions.reportObjectActionBlocker(`Delete block blocked: ${definition.name} is no longer saved in the block library.`);
    return;
  }
  actions.setDraftBlockLibrary((prev) => prev.filter((block) => block.id !== definition.id));
  const message = `Deleted saved block ${definition.name}.`;
  actions.setObjectManagerStatusMessage(`${message} Existing placed inserts remain on the canvas as draft review geometry.`);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_deleted",
    label: "Draft block deleted",
    detail: `${definition.name} was removed from the reusable block library; placed inserts were preserved.`,
    undoBlockedReason: "Re-save selected draft objects if you need this block definition again.",
  });
}

export function runObjectManagerExplodeCombined({
  item,
  buildingPlacements,
  actions,
}: {
  item: BuildingPlacement;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBlockActions;
}) {
  actions.clearGeneratedPreview();
  const sourceIds = Array.isArray(item.meta?.combined_from_object_ids)
    ? item.meta.combined_from_object_ids.map((id) => String(id)).filter(Boolean)
    : [];
  if (!sourceIds.length) {
    actions.reportObjectActionBlocker("Explode blocked: select a combined object with preserved source pieces first.");
    return;
  }
  const restoredSources = buildingPlacements.filter((candidate) => sourceIds.includes(candidate.id));
  if (!restoredSources.length) {
    actions.reportObjectActionBlocker("Explode blocked: the original source pieces are missing from this workspace.");
    return;
  }
  const afterSources = restoredSources.map((source) => cloneBuildingPlacementWithUpdatesForUndo(source, {
    meta: {
      ui_hidden: false,
      exploded_from_object_id: item.id,
      exploded_from_label: item.label,
    },
  }));
  const undo: DraftUndoAction = {
    action: "explode",
    object: cloneBuildingPlacementForUndo(item),
    beforeSources: restoredSources.map(cloneBuildingPlacementForUndo),
    afterSources,
    label: "explode combined object",
  };
  const afterSourceById = new Map(afterSources.map((source) => [source.id, source]));
  actions.setBuildingPlacements((prev) =>
    prev
      .filter((candidate) => candidate.id !== item.id)
      .map((candidate) =>
        afterSourceById.has(candidate.id)
          ? { ...afterSourceById.get(candidate.id)! }
          : candidate,
      ),
  );
  const restoredIds = restoredSources.map((source) => source.id);
  actions.setSelectedObjectIds(restoredIds);
  actions.setActivePlacementId(restoredIds[0] ?? null);
  actions.markSystemsStale(actions.systemsImpactedByPlacement(item));
  actions.recordDraftUndoAction(undo);
  actions.recordRecentChange({
    type: "object_deleted",
    label: "Combined object exploded",
    detail: `${item.label} was exploded back into ${restoredIds.length} preserved source piece${restoredIds.length === 1 ? "" : "s"}.`,
    undo,
  });
  const message = `Exploded ${item.label} back into ${restoredIds.length} preserved source piece${restoredIds.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", `${message} Restored pieces remain draft review geometry and still need qualified review.`, "status");
  actions.persistDraftRefresh("Refreshing preview after exploding combined object...");
}
