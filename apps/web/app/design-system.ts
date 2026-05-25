export const civoraTheme = {
  color: {
    background: "var(--civora-bg)",
    backgroundSoft: "var(--civora-bg-soft)",
    surface: "var(--civora-surface)",
    surfaceSolid: "var(--civora-surface-solid)",
    surfaceMuted: "var(--civora-surface-muted)",
    border: "var(--civora-border)",
    borderStrong: "var(--civora-border-strong)",
    text: "var(--civora-text)",
    textMuted: "var(--civora-text-muted)",
    textSoft: "var(--civora-text-soft)",
    accent: "var(--civora-accent)",
    accentSoft: "var(--civora-accent-soft)",
    success: "var(--civora-success)",
    warning: "var(--civora-warning)",
    danger: "var(--civora-danger)",
  },
  radius: {
    xs: "var(--civora-radius-xs)",
    sm: "var(--civora-radius-sm)",
    md: "var(--civora-radius-md)",
    lg: "var(--civora-radius-lg)",
    xl: "var(--civora-radius-xl)",
    pill: "var(--civora-radius-pill)",
  },
  shadow: {
    soft: "var(--civora-shadow-soft)",
    panel: "var(--civora-shadow-panel)",
    canvas: "var(--civora-shadow-canvas)",
  },
} as const;

export const workflowSteps = [
  "Concept",
  "Grading",
  "Drainage",
  "Utilities",
  "Review",
  "Deliverables",
] as const;

export const workspaceNavItems = [
  "Model",
  "Layers",
  "Sections",
  "3D",
  "Reports",
  "Quantities",
  "Sheets",
  "Data",
  "Settings",
] as const;

export type CivoraWorkflowStep = (typeof workflowSteps)[number];
export type CivoraWorkspaceNavItem = (typeof workspaceNavItems)[number];
