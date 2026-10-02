import { useCallback, useRef } from "react";
import type { MutableRefObject } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  PlanRequestPayload,
  ProjectRecord,
} from "../types";
import { formatCalmActionMessage } from "../utils/objectGeometry";
import { captureWorkspaceSaveGuard } from "../utils/workspaceSaveGuard";
import { guardedTransactionSave } from "../utils/guardedTransactionSave";

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type SaveProject = (options: {
  silent?: boolean;
  projectInputOverride?: PlanRequestPayload | ProjectRecord["project_input"];
}) => Promise<ProjectRecord | null>;

type UseDashboardObjectPersistenceActionsInput = {
  appendChatMessage: AppendChatMessage;
  currentProjectRef: MutableRefObject<ProjectRecord | null>;
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  projectLoadRequestRef: MutableRefObject<number>;
  ensureProjectDraftRef: MutableRefObject<() => Promise<string | null>>;
  payloadPreviewRef: MutableRefObject<PlanRequestPayload>;
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  saveProjectRef: MutableRefObject<SaveProject>;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
};

export function useDashboardObjectPersistenceActions({
  appendChatMessage,
  currentProjectRef,
  buildingPlacementsRef,
  projectLoadRequestRef,
  ensureProjectDraftRef,
  payloadPreviewRef,
  previewRefreshIntentRef,
  saveProjectRef,
  setObjectManagerStatusMessage,
  setStatusMessage,
}: UseDashboardObjectPersistenceActionsInput) {
  const latestDraftRefreshRef = useRef<{ reason: string; isCurrent: () => boolean } | null>(null);
  const draftRefreshWorkerRef = useRef<Promise<void> | null>(null);
  const detectedSaveSequenceRef = useRef(0);

  const persistDetectedPlacements = useCallback(
    (nextDetected: BuildingPlacement[]) => {
      const sequence = ++detectedSaveSequenceRef.current;
      void guardedTransactionSave({
        isCurrent: captureWorkspaceSaveGuard(projectLoadRequestRef, buildingPlacementsRef,
          () => detectedSaveSequenceRef.current === sequence),
        ensureDraft: () => ensureProjectDraftRef.current(),
        save: () => {
          const currentInput = currentProjectRef.current?.project_input ?? payloadPreviewRef.current;
          return saveProjectRef.current({
            silent: true,
            projectInputOverride: {
              ...currentInput,
              input_mode: "user",
              strict_mode: false,
              allow_ai_fill_for_blanks: false,
              meta: {
                ...(currentInput?.meta ?? {}),
                site_inputs: { ...(currentInput?.meta?.site_inputs ?? {}), detected_objects: nextDetected },
              },
            },
          });
        },
        onFailure: () => setStatusMessage("Detected-object changes remain in the working plan, but saving failed. Retry Save Project."),
      });
    },
    [currentProjectRef, buildingPlacementsRef, projectLoadRequestRef, ensureProjectDraftRef, payloadPreviewRef, saveProjectRef, setStatusMessage],
  );

  const reportObjectActionBlocker = useCallback((message: string) => {
    const calmMessage = formatCalmActionMessage(message);
    setObjectManagerStatusMessage(calmMessage);
    setStatusMessage(calmMessage);
    appendChatMessage("assistant", calmMessage, "status");
  }, [appendChatMessage, setObjectManagerStatusMessage, setStatusMessage]);

  const persistDraftRefresh = useCallback((reason: string) => {
    latestDraftRefreshRef.current = {
      reason,
      isCurrent: captureWorkspaceSaveGuard(projectLoadRequestRef, buildingPlacementsRef),
    };
    if (draftRefreshWorkerRef.current) return;

    draftRefreshWorkerRef.current = (async () => {
      try {
        while (latestDraftRefreshRef.current) {
          await new Promise<void>((resolve) => {
            if (typeof window === "undefined") {
              resolve();
              return;
            }
            window.requestAnimationFrame(() => resolve());
          });

          const request = latestDraftRefreshRef.current;
          latestDraftRefreshRef.current = null;
          if (!request) continue;
          await guardedTransactionSave({
            isCurrent: () => request.isCurrent() && !latestDraftRefreshRef.current,
            ensureDraft: () => ensureProjectDraftRef.current(),
            save: () => saveProjectRef.current({ silent: true }),
            refresh: () => { previewRefreshIntentRef.current = { reason: request.reason, track: true }; },
            onFailure: () => reportObjectActionBlocker("The draft remains in the working plan, but saving failed. Retry Save Project."),
          });
        }
      } finally {
        draftRefreshWorkerRef.current = null;
      }
    })();
  }, [projectLoadRequestRef, buildingPlacementsRef, ensureProjectDraftRef, previewRefreshIntentRef, saveProjectRef, reportObjectActionBlocker]);

  return {
    persistDetectedPlacements,
    persistDraftRefresh,
    reportObjectActionBlocker,
  };
}
