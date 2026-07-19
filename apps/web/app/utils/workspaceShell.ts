export type SidePanelKey =
  | "projects"
  | "trust"
  | "dashboard"
  | "model"
  | "site_existing"
  | "import_survey"
  | "objects"
  | "generate"
  | "grading"
  | "drainage"
  | "sanitary"
  | "water"
  | "utilities"
  | "roadway"
  | "landscape"
  | "details"
  | "layers"
  | "analysis"
  | "reports"
  | "quantities"
  | "deliverables"
  | "files"
  | "jobs"
  | "standards"
  | "templates"
  | "catalogs"
  | "libraries"
  | "data"
  | "settings"
  | "chat"
  | "system_grading"
  | "system_storm"
  | "system_sanitary"
  | "system_water"
  | "system_roadway"
  | "system_utilities"
  | "system_landscape";

export type WorkspaceMode =
  | "trust"
  | "dashboard"
  | "setup"
  | "canvas"
  | "layers"
  | "review"
  | "deliver"
  | "data"
  | "settings";

export type SidebarStatus = "ok" | "review" | "block" | "idle";

export type ProjectStatusState = "working" | "blocked" | "needs review" | "stale" | "ready";

export type ProjectStatusArea = "setup" | "generate" | "deliver" | "chat" | "projects" | "ai realism";

export type ProjectStatusSummary = {
  state: ProjectStatusState;
  area: ProjectStatusArea;
  title: string;
  detail: string;
  nextAction: string;
  updatedAt: number;
};

export const DEFAULT_PROJECT_STATUS: ProjectStatusSummary = {
  state: "needs review",
  area: "setup",
  title: "Workspace needs review",
  detail: "Start by applying an address or locking a site boundary.",
  nextAction: "Open Setup and define the site before generating review drafts.",
  updatedAt: 0,
};

export const projectStatusDisplayLabel: Record<ProjectStatusState, string> = {
  working: "Working",
  blocked: "Needs input",
  "needs review": "Needs review",
  stale: "Update recommended",
  ready: "Ready",
};

export const formatProjectStatusText = (summary: ProjectStatusSummary) =>
  `${projectStatusDisplayLabel[summary.state]}: ${summary.title}. ${summary.detail} Next: ${summary.nextAction}`;

export const sidePanelCopy: Record<SidePanelKey, { title: string; desc: string }> = {
  projects: { title: "Projects", desc: "Open, create, and manage project records." },
  trust: { title: "What Civora does", desc: "Clear product boundaries for planning, drafting, source context, review packages, and AI visualization." },
  dashboard: { title: "Project Health", desc: "See what needs attention, what changed, and what is ready to review." },
  model: { title: "Draw Canvas", desc: "Use the canvas, map, 2D/3D view, and visible drawing controls." },
  site_existing: { title: "Project Setup", desc: "Start from address, blank site, site size, boundary drawing, and first objects." },
  import_survey: { title: "Import & Survey", desc: "Bring in survey, map snapshots, and terrain sources." },
  objects: { title: "Draw & Objects", desc: "Draw on the canvas, select objects, then edit names, colors, layers, transforms, and visibility from one place." },
  generate: { title: "Generate Systems", desc: "Run focused engines from one control panel." },
  grading: { title: "Grading Controls", desc: "Control grading rules, terrain inputs, and slope limits." },
  drainage: { title: "Drainage Controls", desc: "Control drainage rules, sources, and repair behavior." },
  sanitary: { title: "Sanitary Controls", desc: "Configure sanitary coverage, slopes, and service assumptions." },
  water: { title: "Water Controls", desc: "Configure water, hydrant, loop, and pressure assumptions." },
  utilities: { title: "Utility Controls", desc: "Control utility generation and coordination assumptions." },
  roadway: { title: "Roadway Controls", desc: "Control roads, parking, and corridor behavior." },
  landscape: { title: "Landscape Controls", desc: "Place open space and landscape-related site objects." },
  details: { title: "Object Manager", desc: "Review profiles, cross sections, selected objects, locks, and object metadata." },
  layers: { title: "Layers", desc: "Choose visible model layers and labels." },
  analysis: { title: "Project health", desc: "Open only when you want blockers, evidence, and QA detail." },
  reports: { title: "Review package status", desc: "Review package gates, assumptions, standards, conflicts, and system readiness." },
  quantities: { title: "Quantities", desc: "Review takeoff totals, stale labels, source confidence, and cost inputs." },
  deliverables: { title: "Deliver", desc: "Review sheets, reports, quantities, profiles, sections, exports, and package gates." },
  files: { title: "Files", desc: "Manage imported inputs and generated outputs." },
  jobs: { title: "Async Jobs", desc: "Inspect background runs, retries, review holds, exports, and artifact history." },
  standards: { title: "Standards", desc: "Review rule packs, assumptions, and project criteria." },
  templates: { title: "Template Manager", desc: "Manage firm templates for layers, title blocks, labels, symbols, reports, cost links, pipes, and roadway hooks." },
  catalogs: { title: "Utility Catalogs", desc: "Manage source-traced pipe and parts catalogs for storm, sanitary, and water networks." },
  libraries: { title: "Libraries", desc: "Use reusable objects, templates, and project presets." },
  data: { title: "Data", desc: "Configure survey, terrain, GIS, parcels, standards sources, imported utilities, and confidence labels." },
  settings: { title: "Settings", desc: "Set project rules, defaults, and run preferences." },
  chat: { title: "Chat", desc: "Conversation and assisted workflow control." },
  system_grading: { title: "Grading Health", desc: "Review what grading needs before it can be trusted." },
  system_storm: { title: "Storm Drainage Health", desc: "Review what storm drainage needs before it can be trusted." },
  system_sanitary: { title: "Sanitary Sewer Health", desc: "Review what sanitary needs before it can be trusted." },
  system_water: { title: "Water Health", desc: "Review what water needs before it can be trusted." },
  system_roadway: { title: "Roadway Health", desc: "Review what roadway needs before it can be trusted." },
  system_utilities: { title: "Utilities Health", desc: "Review what utility coordination needs before it can be trusted." },
  system_landscape: { title: "Landscape Health", desc: "Review what landscape needs before it can be trusted." },
};

export const disciplinePanelLinks: Array<{ panel: SidePanelKey; label: string }> = [
  { panel: "grading", label: "Grading" },
  { panel: "drainage", label: "Drainage" },
  { panel: "utilities", label: "Utilities" },
  { panel: "roadway", label: "Roadway" },
  { panel: "landscape", label: "Landscape" },
];

export const engineeringHealthPanelLinks: Array<{ panel: SidePanelKey; label: string }> = [
  { panel: "system_grading", label: "Grading" },
  { panel: "system_storm", label: "Storm" },
  { panel: "system_sanitary", label: "Sanitary" },
  { panel: "system_water", label: "Water" },
  { panel: "system_roadway", label: "Roadway" },
  { panel: "system_utilities", label: "Utilities" },
  { panel: "system_landscape", label: "Landscape" },
  { panel: "analysis", label: "Review & QA" },
];

export const workspaceModeByPanel: Record<SidePanelKey, WorkspaceMode> = {
  projects: "dashboard",
  trust: "trust",
  dashboard: "dashboard",
  model: "canvas",
  site_existing: "setup",
  import_survey: "setup",
  objects: "canvas",
  generate: "canvas",
  grading: "canvas",
  drainage: "canvas",
  sanitary: "canvas",
  water: "canvas",
  utilities: "canvas",
  roadway: "canvas",
  landscape: "canvas",
  details: "review",
  layers: "layers",
  analysis: "review",
  reports: "review",
  quantities: "deliver",
  deliverables: "deliver",
  files: "data",
  jobs: "review",
  standards: "data",
  templates: "data",
  catalogs: "data",
  libraries: "data",
  data: "data",
  settings: "settings",
  chat: "canvas",
  system_grading: "review",
  system_storm: "review",
  system_sanitary: "review",
  system_water: "review",
  system_roadway: "review",
  system_utilities: "review",
  system_landscape: "review",
};

export const workspacePanelByMode: Record<WorkspaceMode, SidePanelKey> = {
  trust: "trust",
  dashboard: "dashboard",
  setup: "site_existing",
  canvas: "model",
  layers: "layers",
  review: "reports",
  deliver: "deliverables",
  data: "data",
  settings: "settings",
};
