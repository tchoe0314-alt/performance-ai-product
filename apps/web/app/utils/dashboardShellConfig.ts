import type { SiteObjectType } from "../types";
import type { WorkspaceShortcutRow } from "../components/WorkspaceShortcutsOverlay";
import type { SidePanelKey } from "./workspaceShell";

export const DASHBOARD_SOURCE_HUB_LINKS: Array<[SidePanelKey, string]> = [
  ["site_existing", "Existing Conditions"],
  ["import_survey", "Survey / Terrain"],
  ["files", "Files"],
  ["standards", "Standards Sources"],
  ["templates", "Templates"],
  ["catalogs", "Utility Catalogs"],
  ["libraries", "Libraries"],
];

export const DASHBOARD_SUPPORTED_SHORTCUTS: WorkspaceShortcutRow[] = [
  ["Esc", "Cancel active tool or close help"],
  ["Delete", "Delete selected draft object"],
  ["Cmd/Ctrl C", "Copy selected draft object"],
  ["Cmd/Ctrl V", "Paste copied draft object"],
  ["Cmd/Ctrl Z", "Undo supported draft action"],
  ["Cmd/Ctrl Y", "Redo supported draft action"],
  ["Cmd/Ctrl S", "Save project"],
  ["/ or Cmd/Ctrl K", "Focus command"],
  ["G", "Open Generate"],
  ["D", "Open Draw Canvas"],
  ["P", "Open Projects"],
  ["?", "Show shortcuts"],
];

export function buildDashboardLibraryPanelSections({
  addMenuSections,
  siteObjectCatalog,
}: {
  addMenuSections: Array<{ key: string; title: string; items: SiteObjectType[] }>;
  siteObjectCatalog: Record<SiteObjectType, { label: string }>;
}) {
  return addMenuSections.map((group) => ({
    key: group.key,
    title: group.title,
    items: group.items.map((type) => ({
      type,
      label: siteObjectCatalog[type].label,
    })),
  }));
}

export function buildDashboardStandardsPanelCriteria({
  minSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  maxAdaCrossSlopePct,
  pipeMinSlopePct,
  parkingAngle,
}: {
  minSlopePct: string;
  maxParkingSlopePct: string;
  maxRoadGradePct: string;
  maxAdaCrossSlopePct: string;
  pipeMinSlopePct: string;
  parkingAngle: string;
}) {
  return [
    { label: "Min slope", value: minSlopePct || "Auto" },
    { label: "Parking max", value: maxParkingSlopePct || "Auto" },
    { label: "Road max", value: maxRoadGradePct || "Auto" },
    { label: "ADA cross", value: maxAdaCrossSlopePct || "Auto" },
    { label: "Pipe slope", value: pipeMinSlopePct || "Auto" },
    { label: "Parking angle", value: `${parkingAngle} deg` },
  ];
}
