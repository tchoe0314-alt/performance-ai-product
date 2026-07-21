import { useCallback } from "react";

import type { ChatMessage } from "../types";
import type {
  PlanSheetScale,
  PlanSheetSet,
  PlanSheetTitleBlock,
} from "../components/PlanSheetEditor";
import { formatCalmActionMessage } from "../utils/objectGeometry";
import type { SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type UseDashboardSheetIntentHandlerInput = {
  appendChatMessage: AppendChatMessage;
  getPlanSheetBlockers: () => string[];
  handleCreateReviewSheet: () => void;
  handleOpenSidePanel: (panel: SidePanelKey) => void;
  handlePlanSheetAddNote: (text?: string) => void;
  handlePlanSheetAddRevision: (note?: string) => void;
  handlePlanSheetExportPdf: () => void;
  handlePlanSheetScaleChange: (viewportId: string, scale: PlanSheetScale) => void;
  handlePlanSheetTitleBlockUpdate: (updates: Partial<PlanSheetTitleBlock>) => void;
  planSheetSet: PlanSheetSet;
  setActiveWorkspaceMode: (mode: WorkspaceMode) => void;
};

export function useDashboardSheetIntentHandler({
  appendChatMessage,
  getPlanSheetBlockers,
  handleCreateReviewSheet,
  handleOpenSidePanel,
  handlePlanSheetAddNote,
  handlePlanSheetAddRevision,
  handlePlanSheetExportPdf,
  handlePlanSheetScaleChange,
  handlePlanSheetTitleBlockUpdate,
  planSheetSet,
  setActiveWorkspaceMode,
}: UseDashboardSheetIntentHandlerInput) {
  return useCallback(
    (message: string): boolean => {
      const normalized = message.toLowerCase();
      const activeSheet =
        planSheetSet.sheets.find((sheet) => sheet.id === planSheetSet.activeSheetId) ??
        planSheetSet.sheets[0];

      if (/(make|create|build).*((review\s+)?sheet|sheet set)|review sheet package|plan sheet/i.test(normalized)) {
        handleCreateReviewSheet();
        return true;
      }

      if (/edit title block|title block/i.test(normalized)) {
        const titleMatch = message.match(/title(?: block)?(?: to|:)\s*([^.;\n]+)/i);
        const sheetNoMatch = message.match(/(?:sheet number|sheet no\.?|number)(?: to|:)\s*([A-Za-z0-9.-]+)/i);
        const stageMatch = message.match(/(?:stage|review stage)(?: to|:)\s*([^.;\n]+)/i);
        const updates: Partial<PlanSheetTitleBlock> = {};
        if (titleMatch?.[1]) updates.sheetTitle = titleMatch[1].trim();
        if (sheetNoMatch?.[1]) updates.sheetNumber = sheetNoMatch[1].trim();
        if (stageMatch?.[1]) updates.reviewStage = stageMatch[1].trim();
        if (Object.keys(updates).length) {
          handlePlanSheetTitleBlockUpdate(updates);
          appendChatMessage("assistant", "Updated the active sheet title block.", "status");
        } else {
          setActiveWorkspaceMode("deliver");
          handleOpenSidePanel("deliverables");
          appendChatMessage("assistant", "Opened the sheet editor title block fields.", "status");
        }
        return true;
      }

      if (/add revision note|revision note/i.test(normalized)) {
        const noteText =
          message.match(/revision note(?: that says| saying|:)?\s*["“]?([^"”]+)["”]?/i)?.[1]?.trim() ||
          "Review revision note added; verify before package handoff.";
        handlePlanSheetAddRevision(noteText);
        appendChatMessage("assistant", `Added revision note: ${noteText}`, "status");
        return true;
      }

      if (/add note|new note|sheet note/i.test(normalized)) {
        const noteText =
          message.match(/(?:add|new)\s+(?:a\s+)?note(?: that says| saying|:)?\s*["“]?([^"”]+)["”]?/i)?.[1]?.trim() ||
          "Review note: confirm source before package handoff.";
        handlePlanSheetAddNote(noteText);
        appendChatMessage("assistant", `Added note: ${noteText}`, "status");
        return true;
      }

      if (/change scale|set scale|viewport scale|scale/i.test(normalized)) {
        const scaleMatch =
          message.match(/1\s*:\s*(10|20|30|40|50|100)/i) ||
          message.match(/1\s*(?:inch|in|")?\s*(?:equals|=)\s*(10|20|30|40|50|100)\s*(?:feet|foot|ft|')?/i);
        const scale = scaleMatch ? (`1:${scaleMatch[1]}` as PlanSheetScale) : null;
        const viewportId = activeSheet?.viewports[0]?.id;
        if (scale && viewportId) {
          handlePlanSheetScaleChange(viewportId, scale);
          appendChatMessage("assistant", `Changed the active viewport scale to ${scale}.`, "status");
        } else {
          appendChatMessage("assistant", "Tell me a supported scale like 1:20, 1:40, or 1:100.", "status");
        }
        return true;
      }

      if (/plot this review set|plot.*review set|review pdf|print package/i.test(normalized)) {
        handlePlanSheetExportPdf();
        appendChatMessage("assistant", "Opened the review PDF print package with review-only watermark and plotting standards.", "status");
        return true;
      }

      if (/why is this not for construction|not for construction/i.test(normalized)) {
        appendChatMessage(
          "assistant",
          "This is not for construction because sheets and plots are review-only production aids. Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
          "status",
        );
        return true;
      }

      if (/show sheet blockers|sheet blockers|sheet blocked|show sheet needs|sheet needs/i.test(normalized)) {
        const blockers = getPlanSheetBlockers();
        appendChatMessage(
          "assistant",
          blockers.length
            ? `Sheet needs:\n${blockers.map((blocker) => `- ${formatCalmActionMessage(blocker)}`).join("\n")}`
            : "No sheet needs are recorded.",
          "status",
        );
        setActiveWorkspaceMode("deliver");
        handleOpenSidePanel("deliverables");
        return true;
      }

      return false;
    },
    [
      appendChatMessage,
      getPlanSheetBlockers,
      handleCreateReviewSheet,
      handleOpenSidePanel,
      handlePlanSheetAddNote,
      handlePlanSheetAddRevision,
      handlePlanSheetExportPdf,
      handlePlanSheetScaleChange,
      handlePlanSheetTitleBlockUpdate,
      planSheetSet,
      setActiveWorkspaceMode,
    ],
  );
}
