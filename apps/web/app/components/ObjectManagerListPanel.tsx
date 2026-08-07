import type { BuildingPlacement, SiteObjectType, SourceConfidenceEntry } from "../types";
import {
  buildDraftObjectResizeUpdates,
  CustomGeometryHandoffDetails,
  getObjectDimensionsLabel,
  getObjectDisplayType,
  getObjectEditBlocker,
  getObjectLayerLabel,
  getObjectReviewLabel,
  getObjectSourceLabel,
} from "../utils/objectGeometry";
import { parsePositiveNumber } from "../utils/formatting";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import { ObjectManagerRow } from "./ObjectManagerRow";

type ObjectTransform = "rotate" | "flip_horizontal" | "flip_vertical";

export function ObjectManagerListPanel({
  objects,
  units,
  activeObjectId,
  selectedObjectSet,
  sourceConfidenceByObjectId,
  objectOutlineColor,
  onSetPlacementModeEnabled,
  onSelect,
  onToggleMultiSelect,
  onDelete,
  onUpdate,
  onReportBlocker,
  onToggleLock,
  onFocus,
  onInspect,
  onCopy,
  onTransform,
  onExplodeCombined,
}: {
  objects: BuildingPlacement[];
  units: string;
  activeObjectId: string | null;
  selectedObjectSet: Set<string>;
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>;
  objectOutlineColor: string;
  onSetPlacementModeEnabled: (enabled: boolean) => void;
  onSelect: (objectId: string) => void;
  onToggleMultiSelect: (objectId: string, checked: boolean) => void;
  onDelete: (item: BuildingPlacement) => void;
  onUpdate: (objectId: string, updates: Partial<BuildingPlacement>) => void;
  onReportBlocker: (blocker: string) => void;
  onToggleLock: (objectId: string) => void;
  onFocus: (objectId: string) => void;
  onInspect: () => void;
  onCopy: (item: BuildingPlacement) => void;
  onTransform: (item: BuildingPlacement, transform: ObjectTransform) => void;
  onExplodeCombined: (item: BuildingPlacement) => void;
}) {
  const objectTypeOptions = Object.entries(SITE_OBJECT_CATALOG)
    .filter(([type]) => type !== "site")
    .map(([type, catalog]) => ({ type: type as SiteObjectType, label: catalog.label }));

  return (
    <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1" data-testid="object-manager-list">
      {objects.length ? (
        objects.map((item) => {
          const confidenceEntry = sourceConfidenceByObjectId.get(item.id);
          const isSelected = activeObjectId === item.id || selectedObjectSet.has(item.id);
          return (
            <ObjectManagerRow
              key={item.id}
              item={item}
              isSelected={isSelected}
              isMultiSelected={selectedObjectSet.has(item.id)}
              confidenceEntry={confidenceEntry}
              displayType={getObjectDisplayType(item)}
              dimensionsLabel={getObjectDimensionsLabel(item)}
              sourceLabel={getObjectSourceLabel(item)}
              reviewLabel={getObjectReviewLabel(item)}
              layerLabel={getObjectLayerLabel(item)}
              objectTypeOptions={objectTypeOptions}
              objectOutlineColor={objectOutlineColor || "#64748b"}
              hasDefaultHeight={SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined}
              customGeometryDetails={item.type === "custom" ? <CustomGeometryHandoffDetails item={item} units={units} /> : null}
              onDragStart={(event) => {
                if (item.locked) return;
                event.dataTransfer?.setData("civora-object-id", item.id);
                onSetPlacementModeEnabled(true);
              }}
              onToggleMultiSelect={(checked) => onToggleMultiSelect(item.id, checked)}
              onDelete={() => onDelete(item)}
              onRename={(value) => {
                const blocker = getObjectEditBlocker(item, "rename");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(item.id, { label: value });
              }}
              onColor={(value) => {
                const blocker = getObjectEditBlocker(item, "style");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(item.id, {
                  meta: {
                    ...(item.meta ?? {}),
                    ui_color: value,
                  },
                });
              }}
              onType={(nextType) => {
                const blocker = getObjectEditBlocker(item, "type");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(item.id, {
                  type: nextType,
                  use: SITE_OBJECT_CATALOG[nextType]?.use ?? item.use,
                  meta: {
                    ...(item.meta ?? {}),
                    category: SITE_OBJECT_CATALOG[nextType]?.category ?? "advanced",
                  },
                });
              }}
              onLength={(value) => {
                const blocker = getObjectEditBlocker(item, "resize");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(
                  item.id,
                  buildDraftObjectResizeUpdates(
                    item,
                    parsePositiveNumber(value) ?? item.w,
                    item.d,
                  ),
                );
              }}
              onWidth={(value) => {
                const blocker = getObjectEditBlocker(item, "resize");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(
                  item.id,
                  buildDraftObjectResizeUpdates(
                    item,
                    item.w,
                    parsePositiveNumber(value) ?? item.d,
                  ),
                );
              }}
              onHeight={(value) => {
                const blocker = getObjectEditBlocker(item, "resize");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(item.id, {
                  h: parsePositiveNumber(value) ?? item.h,
                });
              }}
              onToggleLock={() => onToggleLock(item.id)}
              onMove={() => {
                onSelect(item.id);
                onSetPlacementModeEnabled(true);
              }}
              onSelect={() => onSelect(item.id)}
              onFocus={() => {
                onSelect(item.id);
                onFocus(item.id);
              }}
              onToggleVisibility={() => {
                const blocker = getObjectEditBlocker(item, "hide");
                if (blocker) {
                  onReportBlocker(blocker);
                  return;
                }
                onUpdate(item.id, {
                  meta: {
                    ...(item.meta ?? {}),
                    ui_hidden: !Boolean(item.meta?.ui_hidden),
                  },
                });
              }}
              onInspect={() => {
                onSelect(item.id);
                onInspect();
              }}
              onCopy={() => onCopy(item)}
              onRotate={() => onTransform(item, "rotate")}
              onFlipHorizontal={() => onTransform(item, "flip_horizontal")}
              onFlipVertical={() => onTransform(item, "flip_vertical")}
              onExplodeCombined={() => onExplodeCombined(item)}
            />
          );
        })
      ) : (
        <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500" data-testid="object-manager-empty-state">
          No objects yet. Draw, add, or ask Civora to create one.
        </p>
      )}
    </div>
  );
}
