import type { ComponentProps, ReactNode } from "react";
import type { SidePanelKey } from "../utils/workspaceShell";
import { DashboardHomePanel } from "./DashboardHomePanel";
import { SiteSetupPanel } from "./SiteSetupPanel";
import { ImportSurveyPanel } from "./ImportSurveyPanel";
import { DataSourcesPanel } from "./DataSourcesPanel";
import { ModelReviewPanel } from "./ModelReviewPanel";
import { GeneratePanel } from "./GeneratePanel";
import { GradingWorkbenchPanel } from "./GradingWorkbenchPanel";
import { DrainageWorkbenchPanel } from "./DrainageWorkbenchPanel";
import { UtilitiesWorkbenchPanel } from "./UtilitiesWorkbenchPanel";
import { SanitaryWorkbenchPanel } from "./SanitaryWorkbenchPanel";
import { WaterFireFlowWorkbenchPanel } from "./WaterFireFlowWorkbenchPanel";
import { SystemReadinessPanel } from "./SystemReadinessPanel";
import { RoadwayWorkbenchPanel } from "./RoadwayWorkbenchPanel";
import { LandscapeWorkbenchPanel } from "./LandscapeWorkbenchPanel";
import { DashboardDetailsPanel } from "./DashboardDetailsPanel";
import { LayersPanel } from "./LayersPanel";
import { AnalysisPanel } from "./AnalysisPanel";
import { FilesPanel } from "./FilesPanel";
import { JobsPanel } from "./JobsPanel";
import { TemplatesPanel } from "./TemplatesPanel";
import { UtilityCatalogPanel } from "./UtilityCatalogPanel";
import { StandardsPanel } from "./StandardsPanel";
import { LibrariesPanel } from "./LibrariesPanel";
import { WorkspaceSettingsPanel } from "./WorkspaceSettingsPanel";
import { DeliverPanel } from "./DeliverPanel";
import { DashboardReportsQuantitiesPanel } from "./DashboardReportsQuantitiesPanel";
import ChatPanel from "./ChatPanel";

type PanelProps = {
  dashboard: ComponentProps<typeof DashboardHomePanel>;
  site_existing: ComponentProps<typeof SiteSetupPanel>;
  import_survey: ComponentProps<typeof ImportSurveyPanel>;
  data: ComponentProps<typeof DataSourcesPanel>;
  model: ComponentProps<typeof ModelReviewPanel>;
  generate: ComponentProps<typeof GeneratePanel>;
  grading: ComponentProps<typeof GradingWorkbenchPanel>;
  drainage: ComponentProps<typeof DrainageWorkbenchPanel>;
  utilities: ComponentProps<typeof UtilitiesWorkbenchPanel>;
  sanitary: ComponentProps<typeof SanitaryWorkbenchPanel>;
  water: ComponentProps<typeof WaterFireFlowWorkbenchPanel>;
  system: ComponentProps<typeof SystemReadinessPanel>;
  roadway: ComponentProps<typeof RoadwayWorkbenchPanel>;
  landscape: ComponentProps<typeof LandscapeWorkbenchPanel>;
  details: ComponentProps<typeof DashboardDetailsPanel>;
  layers: ComponentProps<typeof LayersPanel>;
  analysis: ComponentProps<typeof AnalysisPanel>;
  files: ComponentProps<typeof FilesPanel>;
  jobs: ComponentProps<typeof JobsPanel>;
  templates: ComponentProps<typeof TemplatesPanel>;
  catalogs: ComponentProps<typeof UtilityCatalogPanel>;
  standards: ComponentProps<typeof StandardsPanel>;
  libraries: ComponentProps<typeof LibrariesPanel>;
  settings: ComponentProps<typeof WorkspaceSettingsPanel>;
  deliverables: ComponentProps<typeof DeliverPanel>;
  reports: ComponentProps<typeof DashboardReportsQuantitiesPanel>;
  chat: ComponentProps<typeof ChatPanel>;
  trust: ReactNode;
  projects: ReactNode;
  objects: ReactNode;
};

/** Presentation-only routing. Project state and write operations stay with their owners. */
export function DashboardPanelContent({ activePanel, panels }: { activePanel: SidePanelKey; panels: PanelProps }) {
  switch (activePanel) {
    case "system_grading":
    case "system_storm":
    case "system_sanitary":
    case "system_water":
    case "system_roadway":
    case "system_utilities":
    case "system_landscape": return <SystemReadinessPanel {...panels.system} />;
    case "dashboard": return <DashboardHomePanel {...panels.dashboard} />;
    case "site_existing": return <SiteSetupPanel {...panels.site_existing} />;
    case "import_survey": return <ImportSurveyPanel {...panels.import_survey} />;
    case "data": return <DataSourcesPanel {...panels.data} />;
    case "model": return <ModelReviewPanel {...panels.model} />;
    case "generate": return <GeneratePanel {...panels.generate} />;
    case "grading": return <GradingWorkbenchPanel {...panels.grading} />;
    case "drainage": return <DrainageWorkbenchPanel {...panels.drainage} />;
    case "utilities": return <UtilitiesWorkbenchPanel {...panels.utilities} />;
    case "sanitary": return <SanitaryWorkbenchPanel {...panels.sanitary} />;
    case "water": return <WaterFireFlowWorkbenchPanel {...panels.water} />;
    case "roadway": return <RoadwayWorkbenchPanel {...panels.roadway} />;
    case "landscape": return <LandscapeWorkbenchPanel {...panels.landscape} />;
    case "details": return <DashboardDetailsPanel {...panels.details} />;
    case "layers": return <LayersPanel {...panels.layers} />;
    case "analysis": return <AnalysisPanel {...panels.analysis} />;
    case "files": return <FilesPanel {...panels.files} />;
    case "jobs": return <JobsPanel {...panels.jobs} />;
    case "templates": return <TemplatesPanel {...panels.templates} />;
    case "catalogs": return <UtilityCatalogPanel {...panels.catalogs} />;
    case "standards": return <StandardsPanel {...panels.standards} />;
    case "libraries": return <LibrariesPanel {...panels.libraries} />;
    case "settings": return <WorkspaceSettingsPanel {...panels.settings} />;
    case "deliverables": return <DeliverPanel {...panels.deliverables} />;
    case "quantities":
    case "reports": return <DashboardReportsQuantitiesPanel {...panels.reports} />;
    case "chat": return <ChatPanel {...panels.chat} historyOnly />;
    case "trust": return panels.trust;
    case "projects": return panels.projects;
    case "objects": return panels.objects;
    default: {
      const unsupportedPanel: never = activePanel;
      throw new Error(`Unsupported dashboard panel: ${unsupportedPanel}`);
    }
  }
}
