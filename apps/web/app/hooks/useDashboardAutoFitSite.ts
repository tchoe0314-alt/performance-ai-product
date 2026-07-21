import { useCallback, type Dispatch, type SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import { SQFT_PER_ACRE } from "../utils/workflowConstants";

type UseDashboardAutoFitSiteInput = {
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setFitToSiteRequest: Dispatch<SetStateAction<number>>;
  setLotHeight: Dispatch<SetStateAction<string>>;
  setLotWidth: Dispatch<SetStateAction<string>>;
  setSiteScaleLocked: Dispatch<SetStateAction<boolean>>;
};

export function useDashboardAutoFitSite({
  setBuildingPlacements,
  setFitToSiteRequest,
  setLotHeight,
  setLotWidth,
  setSiteScaleLocked,
}: UseDashboardAutoFitSiteInput) {
  return useCallback(
    (
      width: number,
      height: number,
      label?: string,
      siteIdOverride?: string | null,
      fitMap: boolean = true,
      lockSite: boolean = true,
      preserveExistingObjects: boolean = true,
    ) => {
      const clampedW = Math.max(width, 1);
      const clampedH = Math.max(height, 1);
      setLotWidth(clampedW.toFixed(0));
      setLotHeight(clampedH.toFixed(0));
      setSiteScaleLocked(lockSite);
      setBuildingPlacements((prev) => {
        const filtered = preserveExistingObjects ? prev.filter((item) => item.type !== "site") : [];
        const existingSite = prev.find((item) => item.type === "site");
        const siteId =
          siteIdOverride ||
          existingSite?.id ||
          `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const siteLabel = label || existingSite?.label || "Site Boundary";
        return [
          {
            id: siteId,
            label: siteLabel,
            type: "site",
            w: clampedW,
            d: clampedH,
            x: 0,
            y: 0,
            rotation: 0,
            locked: lockSite,
            placed: true,
            source: "user",
            generated: false,
            capabilities: {
              movable: !lockSite,
              resizable: !lockSite,
              rotatable: !lockSite,
              deletable: false,
            },
            systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
            meta: {
              category: "site",
              site_boundary_state: lockSite ? "locked_canonical" : "draft_editable",
              source_ui_mode: "site_setup",
              engineering_status: "review_required",
              construction_release_allowed: false,
              acres: Number(((clampedW * clampedH) / SQFT_PER_ACRE).toFixed(3)),
            },
          },
          ...filtered,
        ];
      });
      if (fitMap) {
        setFitToSiteRequest((value) => value + 1);
      }
    },
    [setBuildingPlacements, setFitToSiteRequest, setLotHeight, setLotWidth, setSiteScaleLocked],
  );
}
