import { useCallback } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  SiteObjectType,
} from "../types";
import { parseDashboardObjectCommandIntent } from "../utils/dashboardChatCommandParsing";
import type { DraftUndoAction } from "../utils/dashboardTypes";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type AddObjectOptions = {
  label?: string;
  style?: Record<string, string>;
  geometryType?: "polygon" | "polyline" | "rect";
  placed?: boolean;
  width?: number;
  depth?: number;
  stallCount?: number;
  meta?: Record<string, unknown>;
};

type UseDashboardObjectCommandIntentHandlerInput = {
  addGradingDrainageReviewContext: (
    message: string,
    mode: "grading" | "drainage" | "both",
  ) => void;
  appendChatMessage: AppendChatMessage;
  buildingPlacements: BuildingPlacement[];
  ensureSiteBoundary: (reason: string) => boolean;
  formatObjectLabel: (type: SiteObjectType, count: number) => string;
  handleAddObject: (type: SiteObjectType, options?: AddObjectOptions) => void;
  parkingCount: string;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  resolveLotBounds: () => { w: number; h: number };
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setParkingCount: StateSetter<string>;
  setStatusMessage: StateSetter<string>;
};

export function useDashboardObjectCommandIntentHandler({
  addGradingDrainageReviewContext,
  appendChatMessage,
  buildingPlacements,
  ensureSiteBoundary,
  formatObjectLabel,
  handleAddObject,
  recordDraftUndoAction,
  resolveLotBounds,
  setBuildingPlacements,
  setLotHeight,
  setLotWidth,
  setParkingCount,
  setStatusMessage,
}: UseDashboardObjectCommandIntentHandlerInput) {
  return useCallback((message: string): boolean => {
    const intent = parseDashboardObjectCommandIntent(message);
    if (!intent) return false;
    const lot = resolveLotBounds();

    if (intent.kind === "grading_context") {
      appendChatMessage("user", message);
      addGradingDrainageReviewContext(
        message,
        intent.mode,
      );
      return true;
    }

    if (intent.kind === "parking_count") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the parking field can be added immediately.");
      }
      appendChatMessage("user", message);
      setParkingCount(String(Math.round(intent.stalls)));
      handleAddObject("parking", {
        label: `Parking Field - ${Math.round(intent.stalls)} stalls`,
        placed: true,
        stallCount: Math.round(intent.stalls),
        meta: { command_created: true, requested_stalls: Math.round(intent.stalls) },
      });
      appendChatMessage(
        "assistant",
        `Added and placed a ${Math.round(intent.stalls)} stall parking field as draft layout geometry. It still needs review.`,
        "status",
      );
      setStatusMessage(`Added and placed ${Math.round(intent.stalls)} parking stalls as draft review geometry.`);
      return true;
    }

    if (intent.kind === "office_area") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the office building can be added immediately.");
      }
      appendChatMessage("user", message);
      const depth = Math.round(Math.sqrt(intent.areaSf / 1.8));
      const width = Math.round(intent.areaSf / Math.max(depth, 1));
      handleAddObject("office_building", {
        label: `Office Building - ${Math.round(intent.areaSf).toLocaleString()} sf`,
        placed: true,
        width,
        depth,
        meta: {
          command_created: true,
          requested_area_sf: Math.round(intent.areaSf),
          sizing_method: "command_area_to_review_footprint",
        },
      });
      appendChatMessage(
        "assistant",
        `Added and placed a ${Math.round(intent.areaSf).toLocaleString()} sf office building as a draft ${width} ft by ${depth} ft footprint.`,
        "status",
      );
      setStatusMessage("Office building added and placed as draft review geometry.");
      return true;
    }

    if (intent.kind === "building_dims") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the building can be added immediately.");
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        w: intent.width,
        d: intent.depth,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      appendChatMessage(
        "assistant",
        `Added a ${intent.width} ft by ${intent.depth} ft building to the placement tray. Use placement mode to drop it on the site or auto-place it.`,
        "status",
      );
      return true;
    }
    if (intent.kind === "object") {
      const typeKey = intent.type;
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the object can be added immediately.");
      }
      appendChatMessage("user", message);
      const catalog = SITE_OBJECT_CATALOG[typeKey];
      const nextLabel = formatObjectLabel(
        typeKey,
        buildingPlacements.filter((item) => item.type === typeKey).length + 1,
      );
      handleAddObject(typeKey, {
        label: formatObjectLabel(
          typeKey,
          buildingPlacements.filter((item) => item.type === typeKey).length + 1,
        ),
        placed: true,
        width: intent.width ?? catalog?.defaultW,
        depth: intent.depth ?? catalog?.defaultD,
        meta: { command_created: true },
      });
      appendChatMessage(
        "assistant",
        `Added and placed ${nextLabel} as draft review geometry.`,
        "status",
      );
      return true;
    }
    if (intent.kind === "basin") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the basin can be added immediately.");
      }
      appendChatMessage("user", message);
      handleAddObject("basin", {
        width: intent.width,
        depth: intent.depth,
        placed: true,
        meta: { command_created: true },
      });
      appendChatMessage(
        "assistant",
        "Added and placed a basin object as draft review geometry.",
        "status",
      );
      return true;
    }
    if (intent.kind === "entrance") {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add an entrance anchor.",
          "status",
        );
        return true;
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `entrance-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Entrance ${buildingPlacements.length + 1}`,
        type: "entrance",
        w: 20,
        d: 20,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      appendChatMessage(
        "assistant",
        "Added an entrance object to the placement tray. Place it on the canvas when ready.",
        "status",
      );
      return true;
    }
    if (intent.kind === "plot_dims") {
      appendChatMessage("user", message);
      setLotWidth(String(intent.width));
      setLotHeight(String(intent.height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to ${intent.width} ft by ${intent.height} ft.`,
        "status",
      );
      return true;
    }

    if (intent.kind === "plot_acres") {
      appendChatMessage("user", message);
      const area = intent.acres * 43560;
      const side = Math.sqrt(area);
      const width = Math.round(side);
      const height = Math.round(side);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to about ${width} ft by ${height} ft to match ${intent.acres} acres.`,
        "status",
      );
      return true;
    }

    return false;
  }, [
    addGradingDrainageReviewContext,
    appendChatMessage,
    buildingPlacements,
    ensureSiteBoundary,
    formatObjectLabel,
    handleAddObject,
    recordDraftUndoAction,
    resolveLotBounds,
    setBuildingPlacements,
    setLotHeight,
    setLotWidth,
    setParkingCount,
    setStatusMessage,
  ]);
}
