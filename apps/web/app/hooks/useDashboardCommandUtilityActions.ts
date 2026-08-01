import { useCallback, useRef } from "react";
import type { RefObject } from "react";

import type { ChatMessage } from "../types";
import type { CadToolRequestForPreview } from "../utils/dashboardTypes";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type UseDashboardCommandUtilityActionsInput = {
  appendChatMessage: AppendChatMessage;
  commandInputRef: RefObject<HTMLTextAreaElement | null>;
  setActivePlacementId: StateSetter<string | null>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setCommandBarExpanded: StateSetter<boolean>;
  setPendingClarification: StateSetter<{
    action: string;
    payload?: Record<string, unknown>;
    question: string;
  } | null>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setShortcutsOverlayOpen: StateSetter<boolean>;
  setStatusMessage: StateSetter<string>;
  setWorkspaceChromeMinimized: StateSetter<boolean>;
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
};

export function shouldRouteDashboardMessageToOrchestrator(message: string): boolean {
  const normalized = message.toLowerCase();
  if (normalized.length < 140) return false;
  const asksForDesign =
    /\b(design|create|generate|produce|engineer|layout|site plan|development)\b/.test(normalized);
  const describesScope =
    /\b(include|with|building|road|parking|grading|drainage|utilities|detention|basin|sanitary|water)\b/.test(
      normalized,
    );
  return asksForDesign && describesScope;
}

export function useDashboardCommandUtilityActions({
  appendChatMessage,
  commandInputRef,
  setActivePlacementId,
  setCadToolRequest,
  setCommandBarExpanded,
  setPendingClarification,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setShortcutsOverlayOpen,
  setStatusMessage,
  setWorkspaceChromeMinimized,
  updateProjectStatus,
}: UseDashboardCommandUtilityActionsInput) {
  const commandFocusRequestRef = useRef(0);

  const focusCommandInput = useCallback(() => {
    const focusRequestId = commandFocusRequestRef.current + 1;
    commandFocusRequestRef.current = focusRequestId;
    setShortcutsOverlayOpen(false);
    setCommandBarExpanded(true);
    setWorkspaceChromeMinimized(true);
    setPlacementModeEnabled(false);
    setPreviewInteraction("static");
    setCadToolRequest({ id: Date.now() + Math.random(), tool: "select" });
    let focusCancelled = false;
    let selectedOnFocus = false;
    let stableFocusFrames = 0;
    const cleanupFocusListeners = () => {
      window.removeEventListener("keydown", cancelFocusOnEscape, true);
      window.removeEventListener("pointerdown", cancelFocusOnOutsidePointer, true);
    };
    const cancelFocusOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      focusCancelled = true;
      cleanupFocusListeners();
    };
    const cancelFocusOnOutsidePointer = (event: PointerEvent) => {
      const input = commandInputRef.current;
      if (input && event.target === input) return;
      focusCancelled = true;
      cleanupFocusListeners();
    };
    window.addEventListener("keydown", cancelFocusOnEscape, true);
    window.addEventListener("pointerdown", cancelFocusOnOutsidePointer, true);
    const focusMountedInput = (attempt = 0) => {
      if (focusCancelled || commandFocusRequestRef.current !== focusRequestId) {
        cleanupFocusListeners();
        return;
      }
      const referencedInput = commandInputRef.current;
      const input =
        (referencedInput?.isConnected ? referencedInput : null) ??
        (document.querySelector(
          '[data-testid="civora-command-input"]',
        ) as HTMLTextAreaElement | null);
      if (input) {
        if (document.activeElement !== input) {
          input.focus({ preventScroll: true });
          stableFocusFrames = 0;
        } else {
          stableFocusFrames += 1;
        }
        if (!selectedOnFocus) {
          input.select();
          selectedOnFocus = true;
        }
        if (stableFocusFrames >= 3) {
          cleanupFocusListeners();
          return;
        }
      }
      if (attempt < 24) {
        window.requestAnimationFrame(() => focusMountedInput(attempt + 1));
        return;
      }
      if (!input || document.activeElement !== input) {
        updateProjectStatus({
          state: "blocked",
          area: "chat",
          title: "Command focus needs attention",
          detail: "Command input is not mounted.",
          nextAction: "Open the chat panel or return to the canvas, then try / again.",
        });
      }
      cleanupFocusListeners();
    };
    focusMountedInput();
  }, [
    commandInputRef,
    setCadToolRequest,
    setCommandBarExpanded,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setShortcutsOverlayOpen,
    setWorkspaceChromeMinimized,
    updateProjectStatus,
  ]);

  const refuseUnsafeConstructionCommand = useCallback((message: string) => {
    appendChatMessage("user", message);
    appendChatMessage(
      "assistant",
      "I can't stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record. I can help prepare review-only draft materials and call out needs for a qualified professional to review.",
      "status",
    );
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Command refused",
      detail: "Construction authorization refused. Civora stays review-only.",
      nextAction: "Ask for review-only draft materials, blocker review, or a review package instead.",
    });
    return true;
  }, [appendChatMessage, updateProjectStatus]);

  const cancelActiveCommandState = useCallback(() => {
    commandFocusRequestRef.current += 1;
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLElement &&
      (activeElement.tagName === "INPUT" ||
        activeElement.tagName === "TEXTAREA" ||
        activeElement.isContentEditable)
    ) {
      activeElement.blur();
    }
    setShortcutsOverlayOpen(false);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setPendingClarification(null);
    setPreviewInteraction("static");
    setCadToolRequest({ id: Date.now() + Math.random(), tool: "select" });
    setStatusMessage("Active drawing/tool state cancelled.");
  }, [
    setActivePlacementId,
    setCadToolRequest,
    setPendingClarification,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setShortcutsOverlayOpen,
    setStatusMessage,
  ]);

  return {
    cancelActiveCommandState,
    focusCommandInput,
    refuseUnsafeConstructionCommand,
    shouldRouteToOrchestrator: shouldRouteDashboardMessageToOrchestrator,
  };
}
