import { useCallback, useRef } from "react";
import type { MutableRefObject } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  PlanRequestPayload,
  ProjectRecord,
} from "../types";
import { formatCalmActionMessage } from "../utils/objectGeometry";

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
  currentProject: ProjectRecord | null;
  ensureProjectDraftRef: MutableRefObject<() => Promise<string | null>>;
  payloadPreview: PlanRequestPayload;
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  saveProjectRef: MutableRefObject<SaveProject>;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
};

export function useDashboardObjectPersistenceActions({
  appendChatMessage,
  currentProject,
  ensureProjectDraftRef,
  payloadPreview,
  previewRefreshIntentRef,
  saveProjectRef,
  setObjectManagerStatusMessage,
  setStatusMessage,
}: UseDashboardObjectPersistenceActionsInput) {
  const latestDraftRefreshRef = useRef<{ reason: string } | null>(null);
  const draftRefreshWorkerRef = useRef<Promise<void> | null>(null);

  const persistDetectedPlacements = useCallback(
    (nextDetected: BuildingPlacement[]) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: nextDetected,
      };
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({
          silent: true,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: nextSiteInputs,
            },
          },
        }));
    },
    [currentProject, ensureProjectDraftRef, payloadPreview, saveProjectRef],
  );

  const reportObjectActionBlocker = useCallback((message: string) => {
    const calmMessage = formatCalmActionMessage(message);
    setObjectManagerStatusMessage(calmMessage);
    setStatusMessage(calmMessage);
    appendChatMessage("assistant", calmMessage, "status");
  }, [appendChatMessage, setObjectManagerStatusMessage, setStatusMessage]);

  const persistDraftRefresh = useCallback((reason: string) => {
    latestDraftRefreshRef.current = { reason };
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
          await ensureProjectDraftRef.current();

          // A newer object edit landed while the project was being prepared. Skip
          // the stale payload and let the next loop persist the latest workspace.
          if (latestDraftRefreshRef.current) continue;

          await saveProjectRef.current({ silent: true });
          if (!latestDraftRefreshRef.current && request) {
            previewRefreshIntentRef.current = {
              reason: request.reason,
              track: true,
            };
          }
        }
      } finally {
        draftRefreshWorkerRef.current = null;
      }
    })();
  }, [ensureProjectDraftRef, previewRefreshIntentRef, saveProjectRef]);

  return {
    persistDetectedPlacements,
    persistDraftRefresh,
    reportObjectActionBlocker,
  };
}
