import { useCallback } from "react";
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
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason,
          track: true,
        };
      });
  }, [ensureProjectDraftRef, previewRefreshIntentRef, saveProjectRef]);

  return {
    persistDetectedPlacements,
    persistDraftRefresh,
    reportObjectActionBlocker,
  };
}
