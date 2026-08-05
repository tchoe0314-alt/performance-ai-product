import type { PlanSheet, PlanSheetSet } from "../components/PlanSheetEditor";

export const createDefaultPlanSheet = (index = 0, projectName = "Untitled Project"): PlanSheet => {
  const sheetNumber = `R-${String(index + 1).padStart(2, "0")}`;
  return {
    id: `sheet-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
    name: `${sheetNumber} Review Plan`,
    size: "ARCH D",
    titleBlock: {
      projectName,
      sheetTitle: index === 0 ? "Review Site Plan" : `Review Sheet ${index + 1}`,
      sheetNumber,
      reviewStage: "Internal review",
      preparedBy: "Civora",
      checkedBy: "Reviewer",
      date: new Date().toISOString().slice(0, 10),
    },
    viewports: [
      {
        id: `viewport-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: "Site plan viewport",
        source: "Current model preview",
        target: "Overall site plan",
        scale: "1:40",
        scaleLocked: true,
        layerVisibility: {
          "C-ANNO": true,
          "C-ROAD": true,
          "C-PIPE-STORM": true,
          "C-UTIL": true,
          "X-REFERENCE": true,
        },
        northArrow: true,
        scaleBar: true,
        x: 7,
        y: 15,
        w: 56,
        h: 58,
      },
    ],
    annotations: [
      { id: "note-review-only", type: "note", text: "Review package only", x: 10, y: 78 },
      { id: "label-north", type: "label", text: "N", x: 58, y: 20 },
      { id: "dimension-site", type: "dimension", text: "Site dimensions pending source check", x: 15, y: 68 },
    ],
    legends: [
      {
        id: "legend-layers",
        title: "Layer Legend",
        rows: [
          ["CIV-SITE", "Site geometry"],
          ["CIV-STORM", "Storm review"],
          ["CIV-UTIL", "Utility review"],
        ],
      },
    ],
    detailBlocks: [
      {
        id: "detail-review-notes",
        title: "General Review Notes",
        rows: [
          ["1", "Verify source geometry before reliance."],
          ["2", "Resolve listed needs before package handoff."],
        ],
      },
    ],
    references: [
      { id: "profile-main", kind: "profile", label: "Profile reference", target: "Roadway / utility profile pending" },
      { id: "section-a", kind: "section", label: "Section reference", target: "Typical section pending" },
    ],
  };
};

export const createDefaultPlanSheetSet = (projectName = "Untitled Project"): PlanSheetSet => {
  const firstSheet = createDefaultPlanSheet(0, projectName);
  return {
    id: `sheet-set-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: `${projectName} Review Sheet Package`,
    status: "draft",
    mode: "sheet_layout",
    sheets: [firstSheet],
    activeSheetId: firstSheet.id,
    sheetIndex: [{ sheetNumber: firstSheet.titleBlock.sheetNumber, title: firstSheet.titleBlock.sheetTitle }],
    plotStyles: {
      mappings: [
        { layer: "C-ROAD", color: "black", lineweight: "0.35mm", linetype: "CONTINUOUS" },
        { layer: "C-PIPE-STORM", color: "green", lineweight: "0.25mm", linetype: "DASHED" },
        { layer: "C-UTIL", color: "blue", lineweight: "0.25mm", linetype: "DASHED" },
        { layer: "C-ANNO", color: "black", lineweight: "0.18mm", linetype: "CONTINUOUS" },
      ],
      grayscale: false,
      reviewWatermark: "REVIEW ONLY",
    },
    revisions: [
      {
        id: "revision-initial-review",
        revision: "REV-REVIEW",
        note: "Initial review sheet package. Verify before package handoff.",
        date: new Date().toISOString().slice(0, 10),
        reviewer: "Reviewer",
      },
    ],
    blockers: ["Model preview has not been linked to a reviewed source package."],
    updatedAt: new Date().toISOString(),
  };
};
