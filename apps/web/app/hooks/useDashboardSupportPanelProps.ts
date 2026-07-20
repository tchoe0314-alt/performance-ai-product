import { useCallback, useMemo } from "react";
import type { ComponentProps, Dispatch, MutableRefObject, SetStateAction } from "react";

import { getJson, postJson } from "../../lib/api";
import { FilesPanel } from "../components/FilesPanel";
import { JobsPanel } from "../components/JobsPanel";
import { LibrariesPanel } from "../components/LibrariesPanel";
import { StandardsPanel } from "../components/StandardsPanel";
import { TemplatesPanel, type TemplateSummary } from "../components/TemplatesPanel";
import { UtilityCatalogPanel } from "../components/UtilityCatalogPanel";
import type { SiteObjectType } from "../types";
import type { CustomerTemplateRegistryResponse, UtilityCatalogResponse } from "../utils/dashboardDataTypes";
import { panelErrorMessage } from "../utils/dashboardStatus";
import type { SidePanelKey } from "../utils/workspaceShell";

type FilesPanelProps = ComponentProps<typeof FilesPanel>;
type JobsPanelProps = ComponentProps<typeof JobsPanel>;
type TemplatesPanelProps = ComponentProps<typeof TemplatesPanel>;
type UtilityCatalogPanelProps = ComponentProps<typeof UtilityCatalogPanel>;
type StandardsPanelProps = ComponentProps<typeof StandardsPanel>;
type LibrariesPanelProps = ComponentProps<typeof LibrariesPanel>;

type RefreshJobs = (token: string, options?: { force?: boolean }) => Promise<unknown>;

type UseDashboardSupportPanelPropsInput = {
  token: string | null;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  surveyFileName: string;
  projectRecordLabel: string;
  surveyUploadMessage: string;
  planPreviewUrl: string;
  hasBackendResult: boolean;
  dxfStatus: string;
  exportBlockReason: string;
  onOpenPanel: (panel: SidePanelKey) => void;
  mapSnapshotInputRef: MutableRefObject<HTMLInputElement | null>;
  surveyInputRef: MutableRefObject<HTMLInputElement | null>;
  onExportDxf: () => void;
  onExportReport: () => void;
  activeJob: JobsPanelProps["activeJob"];
  selectedJob: JobsPanelProps["selectedJob"];
  jobHistory: JobsPanelProps["jobHistory"];
  jobStatusCounts: JobsPanelProps["jobStatusCounts"];
  artifactHistory: JobsPanelProps["artifactHistory"];
  activeJobStale: boolean;
  selectedJobStale: boolean;
  jobsPanelStatusMessage: string;
  onJobsPanelStatusMessageChange: Dispatch<SetStateAction<string>>;
  onStatusMessageChange: Dispatch<SetStateAction<string>>;
  formatTimestamp: JobsPanelProps["formatTimestamp"];
  toReadableLabel: JobsPanelProps["toReadableLabel"];
  jobDetailMessage: JobsPanelProps["jobDetailMessage"];
  refreshJobs: RefreshJobs;
  onSelectJob: JobsPanelProps["onSelectJob"];
  onCancelJobById: JobsPanelProps["onCancelJob"];
  onRetryJob: JobsPanelProps["onRetryJob"];
  onResumeJob: JobsPanelProps["onResumeJob"];
  onArtifactDownload: JobsPanelProps["onDownloadArtifact"];
  customerTemplates: CustomerTemplateRegistryResponse | null;
  customerTemplateStatus: string;
  customerTemplateSummaries: TemplateSummary[];
  activeCustomerTemplate: TemplateSummary | null;
  customerTemplateBlockerCount: number;
  onCustomerTemplatesChange: Dispatch<SetStateAction<CustomerTemplateRegistryResponse | null>>;
  onCustomerTemplateStatusChange: Dispatch<SetStateAction<string>>;
  utilityCatalog: UtilityCatalogResponse | null;
  utilityCatalogStatus: string;
  utilityCatalogNetworkFilter: string;
  onUtilityCatalogNetworkFilterChange: Dispatch<SetStateAction<string>>;
  standardsPanelCriteria: StandardsPanelProps["criteria"];
  standardsPanelRows: StandardsPanelProps["rows"];
  libraryPanelSections: LibrariesPanelProps["sections"];
  onAddObject: (type: SiteObjectType) => void;
};

export function useDashboardSupportPanelProps({
  token,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  surveyFileName,
  projectRecordLabel,
  surveyUploadMessage,
  planPreviewUrl,
  hasBackendResult,
  dxfStatus,
  exportBlockReason,
  onOpenPanel,
  mapSnapshotInputRef,
  surveyInputRef,
  onExportDxf,
  onExportReport,
  activeJob,
  selectedJob,
  jobHistory,
  jobStatusCounts,
  artifactHistory,
  activeJobStale,
  selectedJobStale,
  jobsPanelStatusMessage,
  onJobsPanelStatusMessageChange,
  onStatusMessageChange,
  formatTimestamp,
  toReadableLabel,
  jobDetailMessage,
  refreshJobs,
  onSelectJob,
  onCancelJobById,
  onRetryJob,
  onResumeJob,
  onArtifactDownload,
  customerTemplates,
  customerTemplateStatus,
  customerTemplateSummaries,
  activeCustomerTemplate,
  customerTemplateBlockerCount,
  onCustomerTemplatesChange,
  onCustomerTemplateStatusChange,
  utilityCatalog,
  utilityCatalogStatus,
  utilityCatalogNetworkFilter,
  onUtilityCatalogNetworkFilterChange,
  standardsPanelCriteria,
  standardsPanelRows,
  libraryPanelSections,
  onAddObject,
}: UseDashboardSupportPanelPropsInput) {
  const handleRefreshJobs = useCallback(() => {
    if (!token) {
      onJobsPanelStatusMessageChange("Sign in/connect backend to refresh jobs.");
      return;
    }
    void refreshJobs(token, { force: true })
      .then(() => onJobsPanelStatusMessageChange("Jobs refreshed."))
      .catch((error) => {
        const message = `Job refresh failed: ${panelErrorMessage(error, "Could not refresh job history.")}`;
        onJobsPanelStatusMessageChange(message);
        onStatusMessageChange(message);
      });
  }, [onJobsPanelStatusMessageChange, onStatusMessageChange, refreshJobs, token]);

  const handleUseCompanyTemplate = useCallback(() => {
    if (!token) return;
    void postJson<Record<string, unknown>>("/api/customer-templates/activate", { template_id: "" }, { token })
      .then((result) => {
        const registry = result.registry as CustomerTemplateRegistryResponse | undefined;
        if (registry) onCustomerTemplatesChange(registry);
        onCustomerTemplateStatusChange("Company template activated");
      })
      .catch((error) =>
        onCustomerTemplateStatusChange(error instanceof Error ? error.message : "Template activation failed"),
      );
  }, [onCustomerTemplateStatusChange, onCustomerTemplatesChange, token]);

  const handleExportTemplateJson = useCallback(() => {
    if (!token) return;
    void getJson<Record<string, unknown>>("/api/customer-templates/export", { token })
      .then(() => onCustomerTemplateStatusChange("Template JSON export prepared"))
      .catch((error) =>
        onCustomerTemplateStatusChange(error instanceof Error ? error.message : "Template export failed"),
      );
  }, [onCustomerTemplateStatusChange, token]);

  const handleActivateTemplate = useCallback<TemplatesPanelProps["onActivateTemplate"]>((item) => {
    if (!token || !item.template_id) return;
    void postJson<Record<string, unknown>>("/api/customer-templates/activate", { template_id: item.template_id }, { token })
      .then((result) => {
        const registry = result.registry as CustomerTemplateRegistryResponse | undefined;
        if (registry) onCustomerTemplatesChange(registry);
        onCustomerTemplateStatusChange(`${item.name || "Template"} activated`);
      })
      .catch((error) =>
        onCustomerTemplateStatusChange(error instanceof Error ? error.message : "Template activation failed"),
      );
  }, [onCustomerTemplateStatusChange, onCustomerTemplatesChange, token]);

  const filesPanelProps = useMemo<FilesPanelProps>(() => ({
    mapSnapshotReady: Boolean(uploadedImageApiUrl || uploadedImagePreviewUrl),
    surveyFileName,
    projectRecordLabel,
    surveyUploadMessage,
    previewReady: Boolean(planPreviewUrl),
    reportReady: hasBackendResult,
    dxfStatus,
    onOpenImportFiles: () => onOpenPanel("import_survey"),
    onSelectMapImage: () => mapSnapshotInputRef.current?.click(),
    onSelectSurveyFile: () => surveyInputRef.current?.click(),
    onOpenPlanPdf: () => onOpenPanel("data"),
    onExportDxf,
    onExportReport,
    exportBlockReason,
  }), [
    dxfStatus,
    exportBlockReason,
    hasBackendResult,
    mapSnapshotInputRef,
    onExportDxf,
    onExportReport,
    onOpenPanel,
    planPreviewUrl,
    projectRecordLabel,
    surveyFileName,
    surveyInputRef,
    surveyUploadMessage,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);

  const jobsPanelProps = useMemo<JobsPanelProps>(() => ({
    activeJob,
    selectedJob,
    jobHistory,
    jobStatusCounts,
    artifactHistory,
    activeJobStale,
    selectedJobStale,
    statusMessage: jobsPanelStatusMessage,
    formatTimestamp,
    toReadableLabel,
    jobDetailMessage,
    onRefresh: handleRefreshJobs,
    onSelectJob,
    onCancelJob: onCancelJobById,
    onRetryJob,
    onResumeJob,
    onDownloadArtifact: onArtifactDownload,
  }), [
    activeJob,
    activeJobStale,
    artifactHistory,
    formatTimestamp,
    handleRefreshJobs,
    jobDetailMessage,
    jobHistory,
    jobStatusCounts,
    jobsPanelStatusMessage,
    onArtifactDownload,
    onCancelJobById,
    onRetryJob,
    onResumeJob,
    onSelectJob,
    selectedJob,
    selectedJobStale,
    toReadableLabel,
  ]);

  const templatesPanelProps = useMemo<TemplatesPanelProps>(() => ({
    registry: customerTemplates,
    status: customerTemplateStatus,
    summaries: customerTemplateSummaries,
    activeTemplate: activeCustomerTemplate,
    blockerCount: customerTemplateBlockerCount,
    toReadableLabel,
    onUseCompanyTemplate: handleUseCompanyTemplate,
    onExportJson: handleExportTemplateJson,
    onActivateTemplate: handleActivateTemplate,
  }), [
    activeCustomerTemplate,
    customerTemplateBlockerCount,
    customerTemplateStatus,
    customerTemplateSummaries,
    customerTemplates,
    handleActivateTemplate,
    handleExportTemplateJson,
    handleUseCompanyTemplate,
    toReadableLabel,
  ]);

  const utilityCatalogPanelProps = useMemo<UtilityCatalogPanelProps>(() => ({
    catalog: utilityCatalog,
    status: utilityCatalogStatus,
    networkFilter: utilityCatalogNetworkFilter,
    onNetworkFilterChange: onUtilityCatalogNetworkFilterChange,
  }), [onUtilityCatalogNetworkFilterChange, utilityCatalog, utilityCatalogNetworkFilter, utilityCatalogStatus]);

  const standardsPanelProps = useMemo<StandardsPanelProps>(() => ({
    criteria: standardsPanelCriteria,
    rows: standardsPanelRows,
    onOpenSourceData: () => onOpenPanel("data"),
    onOpenReviewGates: () => onOpenPanel("reports"),
  }), [onOpenPanel, standardsPanelCriteria, standardsPanelRows]);

  const librariesPanelProps = useMemo<LibrariesPanelProps>(() => ({
    sections: libraryPanelSections,
    onAddObject: (type) => onAddObject(type as SiteObjectType),
  }), [libraryPanelSections, onAddObject]);

  return {
    filesPanelProps,
    jobsPanelProps,
    librariesPanelProps,
    standardsPanelProps,
    templatesPanelProps,
    utilityCatalogPanelProps,
  };
}
