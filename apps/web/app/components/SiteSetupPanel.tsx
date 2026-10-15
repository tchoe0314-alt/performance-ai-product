import type { ComponentProps } from "react";
import type { ProjectInput } from "../types";
import { ActiveBriefSummary } from "./ActiveBriefSummary";
import { BriefSourceRegister } from "./BriefSourceRegister";

import { SetupAddressSection } from "./SetupAddressSection";
import { SetupAutoSiteContextSection } from "./SetupAutoSiteContextSection";
import { SetupSiteBoundarySection } from "./SetupSiteBoundarySection";
import { SetupSurveyTerrainSection } from "./SetupSurveyTerrainSection";

type SiteSetupPanelProps = {
  briefInput?: ProjectInput;
  savedBriefInput?: ProjectInput;
  onClassifyBrief?: ComponentProps<typeof ActiveBriefSummary>["onClassify"];
  onEditBrief?: ComponentProps<typeof ActiveBriefSummary>["onEdit"];
  onSaveBriefSource?: ComponentProps<typeof BriefSourceRegister>["onSave"];
  onSetDrawingUnits?: (units: "ft" | "m") => void;
  address: ComponentProps<typeof SetupAddressSection>;
  boundary: ComponentProps<typeof SetupSiteBoundarySection>;
  surveyTerrain: ComponentProps<typeof SetupSurveyTerrainSection>;
  autoSiteContext: ComponentProps<typeof SetupAutoSiteContextSection>;
};

export function SiteSetupPanel({
  address,
  boundary,
  surveyTerrain,
  autoSiteContext,
  briefInput,
  savedBriefInput,
  onClassifyBrief,
  onEditBrief,
  onSaveBriefSource,
  onSetDrawingUnits,
}: SiteSetupPanelProps) {
  return (
    <div className="space-y-3" data-testid="clean-setup-panel">
      {briefInput && !briefInput.manual_fields?.units?.trim() && <section data-testid="unknown-drawing-units" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs"><p>Drawing units not set. Calculations and current-drawing exports are blocked.</p>{onSetDrawingUnits ? <label className="mt-2 block">Interpret coordinates as<select aria-label="Set drawing units" value="" onChange={event => { if (event.target.value === "ft" || event.target.value === "m") onSetDrawingUnits(event.target.value); }} className="mt-1 w-full rounded border p-1"><option value="">Choose units…</option><option value="ft">Feet</option><option value="m">Metres</option></select></label> : <p className="mt-1">Ask the project editor to set units.</p>}</section>}
      {briefInput && <ActiveBriefSummary input={briefInput} savedInput={savedBriefInput} onClassify={onClassifyBrief} onEdit={onEditBrief} />}
      {briefInput && <BriefSourceRegister stored={briefInput.meta?.site_inputs?.brief_sources_v1} onSave={onSaveBriefSource} />}
      <SetupAddressSection {...address} />
      <SetupSiteBoundarySection {...boundary} />
      <SetupSurveyTerrainSection {...surveyTerrain} />
      <SetupAutoSiteContextSection {...autoSiteContext} />
    </div>
  );
}
