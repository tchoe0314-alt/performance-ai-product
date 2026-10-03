import { useCallback } from "react";
import type { BuildingPlacement, SiteObjectType } from "../types";
import type { CadDimensionMode, CadSymbolKind } from "../utils/cadToolTypes";
import { clampValue } from "../utils/previewCadObjectHelpers";
import { parseCadNumber } from "../utils/previewCadCommandParsing";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import type { buildSelectedCadMetrics } from "../utils/previewCadDerivedObjects";
import type { CadCommandHistoryEntry, PreviewPanelProps } from "./previewPanelTypes";

export type CadPropertyDraft = {
  id: string; name: string; type: SiteObjectType; layer: string; elevation: string;
  material: string; size: string; source: string; sourceNote: string; reviewNote: string;
};

type Options = {
  buildingPlacements: BuildingPlacement[];
  selectedCadIds: string[];
  selectedCadObject: BuildingPlacement | null;
  selectedCadMetrics: ReturnType<typeof buildSelectedCadMetrics>;
  cadLayerDraft: string;
  cadDimensionMode: CadDimensionMode;
  cadDimensionLabelDraft: string;
  cadPropertyDraft: CadPropertyDraft;
  cadCoordinateDraft: { x: string; y: string };
  cadSymbolDraft: CadSymbolKind;
  lotWidth: number; lotHeight: number;
  onCreateCustomGeometry: PreviewPanelProps["onCreateCustomGeometry"];
  pushCadCommandFeedback: (command: string, status: CadCommandHistoryEntry["status"], message: string) => void;
  updateCadObject: (target: BuildingPlacement, updates: Partial<BuildingPlacement>, label: string) => void;
};

/** Draft annotation/property commands use the existing guarded edit/create adapters. */
export function usePreviewCadPropertyCommands({
  buildingPlacements, selectedCadIds, selectedCadObject, selectedCadMetrics, cadLayerDraft, cadDimensionMode, cadDimensionLabelDraft, cadPropertyDraft, cadCoordinateDraft, cadSymbolDraft, lotWidth, lotHeight, onCreateCustomGeometry, pushCadCommandFeedback, updateCadObject
}: Options) {
  const applySelectedCadLayer = useCallback(() => {
    if (!selectedCadIds.length) {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: select one or more editable draft objects first.");
      return;
    }
    let appliedCount = 0;
    selectedCadIds.forEach((id) => {
      const target = buildingPlacements.find((item) => item.id === id);
      if (!target || target.locked || target.type === "site") return;
      updateCadObject(target, { meta: { ...(target.meta ?? {}), cad_layer: cadLayerDraft || "C-DRAFT" } }, "Layer");
      appliedCount += 1;
    });
    if (appliedCount) {
      pushCadCommandFeedback("LAYER", "applied", `LAYER applied to ${appliedCount} draft object${appliedCount === 1 ? "" : "s"}.`);
    } else {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: selected objects are locked or not editable draft objects.");
    }
  }, [buildingPlacements, cadLayerDraft, pushCadCommandFeedback, selectedCadIds, updateCadObject]);
  const applySelectedCadDimension = useCallback(() => {
    if (!selectedCadObject || selectedCadMetrics === null) {
      pushCadCommandFeedback("DIM", "blocked", "DIM blocked: select one editable line/polyline draft object first.");
      return;
    }
    const defaultLabel =
      cadDimensionMode === "linear"
        ? `${selectedCadMetrics.firstLength.toFixed(1)} ft`
        : `${selectedCadMetrics.firstLength.toFixed(1)} ft @ ${selectedCadMetrics.firstAngle.toFixed(1)} deg`;
    updateCadObject(
      selectedCadObject,
      {
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_dimension_mode: cadDimensionMode,
          cad_dimension_label: cadDimensionLabelDraft.trim() || defaultLabel,
        },
      },
      "Dimension",
    );
    pushCadCommandFeedback("DIM", "applied", "DIM label stored on selected draft geometry for review.");
  }, [cadDimensionLabelDraft, cadDimensionMode, pushCadCommandFeedback, selectedCadMetrics, selectedCadObject, updateCadObject]);

  const applyCadProperties = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("PROPERTIES", "blocked", "PROPERTIES blocked: select one editable draft object first.");
      return;
    }
    const safeName = cadPropertyDraft.name.trim() || selectedCadObject.label || "Draft object";
    const safeLayer = cadPropertyDraft.layer.trim().toUpperCase() || "C-DRAFT";
    const safeType = cadPropertyDraft.type || selectedCadObject.type || "custom";
    const classification = SITE_OBJECT_CATALOG[safeType];
    updateCadObject(
      selectedCadObject,
      {
        label: safeName,
        type: safeType,
        use: classification?.use ?? selectedCadObject.use,
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_layer: safeLayer,
          source_note: cadPropertyDraft.sourceNote.trim(),
          review_note: cadPropertyDraft.reviewNote.trim(),
          source: cadPropertyDraft.source.trim() || "manual_drawn",
          symbol_id: cadPropertyDraft.id.trim() || selectedCadObject.id,
          symbol_attributes: {
            id: cadPropertyDraft.id.trim() || selectedCadObject.id,
            label: safeName,
            elevation: cadPropertyDraft.elevation.trim(),
            material: cadPropertyDraft.material.trim(),
            size: cadPropertyDraft.size.trim(),
            source: cadPropertyDraft.source.trim() || "manual_drawn",
            review_note: cadPropertyDraft.reviewNote.trim(),
          },
          category: classification?.category ?? selectedCadObject.meta?.category ?? "advanced",
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
        },
      },
      "Properties",
    );
    pushCadCommandFeedback("PROPERTIES", "applied", "PROPERTIES applied to selected draft object.");
  }, [cadPropertyDraft, pushCadCommandFeedback, selectedCadObject, updateCadObject]);

  const insertCadSymbol = useCallback(() => {
    const x = clampValue(parseCadNumber(cadCoordinateDraft.x, lotWidth / 2), 0, lotWidth);
    const y = clampValue(parseCadNumber(cadCoordinateDraft.y, lotHeight / 2), 0, lotHeight);
    const symbolInstanceId = `${cadSymbolDraft}-${Date.now()}`;
    const labels: Record<CadSymbolKind, string> = {
      hydrant: "Hydrant",
      inlet: "Inlet",
      manhole: "Manhole",
      valve: "Valve",
      tree: "Tree",
      light: "Light",
      sign: "Sign",
      utility_marker: "Utility Marker",
      benchmark: "Benchmark",
      note_callout: "Note / Callout",
    };
    const created = onCreateCustomGeometry({
      mode: "point",
      points: [[x, y]],
      label: labels[cadSymbolDraft],
      meta: {
        cad_symbol: cadSymbolDraft,
        symbol_id: symbolInstanceId,
        cad_layer: cadSymbolDraft === "tree" || cadSymbolDraft === "note_callout" ? "C-ANNO" : "C-SYMB",
        symbol_attributes: {
          id: symbolInstanceId,
          label: labels[cadSymbolDraft],
          elevation: "",
          material: "",
          size: "",
          source: "manual_drawn",
          review_note: "Inserted symbol remains draft/review-required.",
        },
        symbol_review_required: true,
        engineering_status: "draft_review_required",
        review_status: "engineer_review_required",
        source: "manual_drawn",
      },
    });
    if (!created) {
      pushCadCommandFeedback("SYMBOL", "blocked", "SYMBOL was not inserted. Confirm and lock the site boundary, then try again.");
      return;
    }
    pushCadCommandFeedback("SYMBOL", "applied", `SYMBOL inserted: ${labels[cadSymbolDraft]} remains draft/review-required.`);
  }, [cadCoordinateDraft.x, cadCoordinateDraft.y, cadSymbolDraft, lotHeight, lotWidth, onCreateCustomGeometry, pushCadCommandFeedback]);

  return { applySelectedCadLayer, applySelectedCadDimension, applyCadProperties, insertCadSymbol };
}
