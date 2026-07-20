import type { ComponentProps } from "react";

import { SetupAddressSection } from "./SetupAddressSection";
import { SetupAutoSiteContextSection } from "./SetupAutoSiteContextSection";
import { SetupSiteBoundarySection } from "./SetupSiteBoundarySection";
import { SetupSurveyTerrainSection } from "./SetupSurveyTerrainSection";

type SiteSetupPanelProps = {
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
}: SiteSetupPanelProps) {
  return (
    <div className="space-y-3" data-testid="clean-setup-panel">
      <SetupAddressSection {...address} />
      <SetupSiteBoundarySection {...boundary} />
      <SetupSurveyTerrainSection {...surveyTerrain} />
      <SetupAutoSiteContextSection {...autoSiteContext} />
    </div>
  );
}
