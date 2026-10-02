import { useCallback } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  SiteObjectType,
} from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import {
  sidePanelCopy,
  type SidePanelKey,
} from "../utils/workspaceShell";
import type { SystemGenerationTarget } from "../utils/workflowConstants";

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type UseDashboardActionIntentHandlerInput = {
  activePlacementId: string | null;
  appendChatMessage: AppendChatMessage;
  buildingPlacements: BuildingPlacement[];
  formatObjectLabel: (type: SiteObjectType, count: number) => string;
  handleGenerateSystem: (target: SystemGenerationTarget) => void | Promise<void>;
  handleOpenSidePanel: (panel: SidePanelKey) => void;
  handleRemoveBuilding: (id: string) => void;
  handleSelectPlacementTarget: (id: string) => void;
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void | "applied" | "proposed" | "blocked";
  setActivePlacementId: (id: string | null) => void;
  setStatusMessage: (message: string) => void;
  workflowActionHints: string[];
};

export function useDashboardActionIntentHandler({
  activePlacementId,
  appendChatMessage,
  buildingPlacements,
  formatObjectLabel,
  handleGenerateSystem,
  handleOpenSidePanel,
  handleRemoveBuilding,
  handleSelectPlacementTarget,
  handleUpdateBuilding,
  setActivePlacementId,
  setStatusMessage,
  workflowActionHints,
}: UseDashboardActionIntentHandlerInput) {
  return useCallback((message: string): boolean => {
    const normalized = message.toLowerCase();
    const tokens = normalized.split(/\s+/);
    const allObjects = buildingPlacements;

    const findByLabel = (label: string) =>
      allObjects.find((item) => item.label.toLowerCase() === label.toLowerCase());
    const matchByKeyword = (keyword: string) =>
      allObjects.filter((item) =>
        item.label.toLowerCase().includes(keyword) ||
        (item.type ?? "").toLowerCase() === keyword,
      );

    const numberMatch = normalized.match(/(?:building|basin|entrance)\s*(\d+)/i);
    const keywordMatch = tokens.find((token) =>
      ["building", "basin", "entrance", "site", "road", "parking"].includes(token),
    );
    const selected = activePlacementId
      ? allObjects.find((item) => item.id === activePlacementId)
      : null;

    const targetFromNumber = numberMatch
      ? findByLabel(`${numberMatch[0].charAt(0).toUpperCase()}${numberMatch[0].slice(1)}`)
      : null;
    const targetFromKeyword = keywordMatch
      ? matchByKeyword(keywordMatch).filter((item) => item.placed)
      : [];

    const resolveTarget = () => {
      if (targetFromNumber) return targetFromNumber;
      if (selected) return selected;
      if (targetFromKeyword.length === 1) return targetFromKeyword[0];
      return null;
    };

    if (normalized.startsWith("select ")) {
      const label = message.replace(/^select\s+/i, "").replace(/^(the|a|an)\s+/i, "").trim();
      const target =
        findByLabel(label) ||
        allObjects.find((item) => item.label.toLowerCase().includes(label.toLowerCase())) ||
        (matchByKeyword(label).length === 1 ? matchByKeyword(label)[0] : null);
      if (target) {
        setActivePlacementId(target.id);
        setStatusMessage(`Selected ${target.label}.`);
        appendChatMessage("assistant", `Selected ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "I couldn't find that object. Try 'select Building 1' or 'select basin 1'.", "status");
      return true;
    }

    if (/(delete|remove)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleRemoveBuilding(target.id);
        appendChatMessage("assistant", `Removed ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I remove? You can say 'remove Building 1'.", "status");
      return true;
    }

    if (/(make|classify|change|convert).*\b(building|road|parking|basin|detention|pond|line|area|rectangle)\b/.test(normalized)) {
      const target = resolveTarget();
      const requestedType: SiteObjectType | null = /basin|detention|pond/.test(normalized)
        ? "basin"
        : /parking/.test(normalized)
          ? "parking"
          : /road|line/.test(normalized)
            ? "road"
            : /building|rectangle/.test(normalized)
              ? "building"
              : null;
      if (!requestedType) return false;
      if (!target) {
        appendChatMessage(
          "assistant",
          `Select a drawn object first, then say "make this a ${SITE_OBJECT_CATALOG[requestedType].label.toLowerCase()}."`,
          "status",
        );
        return true;
      }
      if (target.type === "site") {
        appendChatMessage("assistant", "The site boundary cannot be reclassified. Draw or select a separate object first.", "status");
        return true;
      }
      const nextLabel = formatObjectLabel(
        requestedType,
        buildingPlacements.filter((item) => item.id !== target.id && item.type === requestedType).length + 1,
      );
      handleUpdateBuilding(target.id, {
        type: requestedType,
        label: nextLabel,
        use: SITE_OBJECT_CATALOG[requestedType].use,
        source: target.source ?? "user",
        meta: {
          ...(target.meta ?? {}),
          category: SITE_OBJECT_CATALOG[requestedType].category,
          classification_status: "draft_review_required",
          canonical_edit_source: "chat",
        },
      });
      appendChatMessage(
        "assistant",
        `Reclassified ${target.label} as ${SITE_OBJECT_CATALOG[requestedType].label}. This is draft geometry and still requires engineer review.`,
        "status",
      );
      return true;
    }

    const moveByDistanceMatch = normalized.match(
      /\bmove\b.*?\b(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(north|south|east|west|up|down|left|right)\b/,
    );
    if (moveByDistanceMatch) {
      const target = resolveTarget();
      if (!target) {
        appendChatMessage("assistant", "Select an object first, then tell me how far and which direction to move it.", "status");
        return true;
      }
      const distance = Number(moveByDistanceMatch[1]);
      const direction = moveByDistanceMatch[2];
      const dx = direction === "east" || direction === "right" ? distance : direction === "west" || direction === "left" ? -distance : 0;
      const dy = direction === "south" || direction === "down" ? distance : direction === "north" || direction === "up" ? -distance : 0;
      const outcome = handleUpdateBuilding(target.id, {
        x: (target.x ?? 0) + dx,
        y: (target.y ?? 0) + dy,
        placed: true,
        meta: { ...(target.meta ?? {}), canonical_edit_source: "chat" },
      });
      appendChatMessage("assistant", outcome === "proposed" ? `Move proposed for ${target.label}; review the complete transaction before applying. The working plan is unchanged.` : outcome === "blocked" ? `The move to ${target.label} was blocked. Review the object status; the working plan is unchanged.` : `Moved ${target.label} ${distance} ft ${direction}. The canonical edit uses the same command path as a CAD move.`, "status");
      return true;
    }

    const exactResizeMatch = normalized.match(
      /\b(?:set|make|resize|change)\b.*?\b(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')?/,
    );
    if (exactResizeMatch) {
      const target = resolveTarget();
      if (!target) {
        appendChatMessage("assistant", "Select an object first, then give me its width and depth.", "status");
        return true;
      }
      const width = Number(exactResizeMatch[1]);
      const depth = Number(exactResizeMatch[2]);
      const outcome = handleUpdateBuilding(target.id, {
        w: width,
        d: depth,
        meta: { ...(target.meta ?? {}), canonical_edit_source: "chat" },
      });
      appendChatMessage("assistant", outcome === "proposed" ? `Resize proposed for ${target.label}; review the complete transaction before applying. The working plan is unchanged.` : outcome === "blocked" ? `The resize to ${target.label} was blocked. Review the object status; the working plan is unchanged.` : `Resized ${target.label} to ${width} ft by ${depth} ft through the canonical edit system.`, "status");
      return true;
    }

    if (/(place|re-?place|move)\b/.test(normalized) && !/\b(pdf|plan|label|sheet)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleSelectPlacementTarget(target.id);
        return true;
      }
      if (allObjects.length === 0) {
        appendChatMessage("assistant", "There are no objects to place yet. Add a building first.", "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I place? For example, 'place Building 1'.", "status");
      return true;
    }

    if (/(bigger|smaller|resize|scale|shrink|grow)\b/.test(normalized)) {
      const target = resolveTarget();
      if (!target) {
        appendChatMessage("assistant", "Which object should I resize? For example, 'make Building 1 bigger'.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `How should I resize ${target.label}? Give me a size like "set to 120 ft by 60 ft".`,
        "status",
      );
      return true;
    }

    if (/(generate|run)\b/.test(normalized)) {
      if (/roads|circulation/.test(normalized)) {
        void handleGenerateSystem("roads");
        return true;
      }
      if (/parking/.test(normalized)) {
        void handleGenerateSystem("parking");
        return true;
      }
      if (/grading|contours/.test(normalized)) {
        void handleGenerateSystem("grading");
        return true;
      }
      if (/drainage|storm/.test(normalized)) {
        void handleGenerateSystem("drainage");
        return true;
      }
      if (/utilities|utility/.test(normalized)) {
        void handleGenerateSystem("utilities");
        return true;
      }
      if (/full|all|everything/.test(normalized)) {
        void handleGenerateSystem("full");
        return true;
      }
    }

    if (/(fix|improve)\b/.test(normalized)) {
      const nextHint = workflowActionHints[0];
      if (nextHint) {
        const targetPanel: SidePanelKey =
          nextHint.startsWith("Setup panel")
            ? "site_existing"
            : nextHint.startsWith("Data panel")
              ? "data"
              : nextHint.startsWith("Objects panel")
                ? "objects"
                : nextHint.startsWith("Generate Systems panel")
                  ? "generate"
                  : nextHint.startsWith("Deliver panel")
                    ? "deliverables"
                    : "reports";
        handleOpenSidePanel(targetPanel);
        appendChatMessage(
          "assistant",
          `Next fix: ${nextHint} I opened the ${sidePanelCopy[targetPanel].title} panel. Civora can prepare review evidence only; independent professional review remains required.`,
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        "I do not see a single automatic fix to apply. Open Review for needs, or ask for a specific action like 'fix drainage' or 'improve parking'.",
        "status",
      );
      return true;
    }

    return false;
  }, [
    activePlacementId,
    appendChatMessage,
    buildingPlacements,
    formatObjectLabel,
    handleGenerateSystem,
    handleOpenSidePanel,
    handleRemoveBuilding,
    handleSelectPlacementTarget,
    handleUpdateBuilding,
    setActivePlacementId,
    setStatusMessage,
    workflowActionHints,
  ]);
}
