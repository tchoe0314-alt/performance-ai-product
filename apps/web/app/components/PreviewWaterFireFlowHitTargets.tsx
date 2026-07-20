import type { Dispatch, SetStateAction } from "react";

import { formatFlowValue } from "../utils/previewGeometryTruth";
import type { buildWaterFireFlowViewModel } from "../utils/previewWaterFireFlow";

type WaterFireFlowViewModel = ReturnType<typeof buildWaterFireFlowViewModel>;

type PreviewWaterFireFlowHitTargetsProps = {
  waterFireFlow: WaterFireFlowViewModel;
  passiveOverlayPointerEvents: string;
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
  setSelectedFireScenarioId: Dispatch<SetStateAction<string | null>>;
};

export function PreviewWaterFireFlowHitTargets({
  waterFireFlow,
  passiveOverlayPointerEvents,
  sitePointToPreviewPercent,
  setSelectedFireScenarioId,
}: PreviewWaterFireFlowHitTargetsProps) {
  return (
    <>
      {waterFireFlow.hydrants.map((hydrant) => {
        const [left, top] = sitePointToPreviewPercent([hydrant.x, hydrant.y]);
        const scenario = waterFireFlow.scenarios.find((item) => item.hydrantId === hydrant.id);
        const selected = waterFireFlow.selectedHydrant?.id === hydrant.id;
        return (
          <button
            key={`hydrant-hit-${hydrant.id}`}
            type="button"
            data-object-overlay
            aria-label={`Select ${hydrant.label} fire-flow scenario`}
            title={`${hydrant.label}: ${formatFlowValue(hydrant.availableFlowGpm, "gpm")}`}
            onClick={(event) => {
              event.stopPropagation();
              if (scenario) setSelectedFireScenarioId(scenario.id);
            }}
            className={`${passiveOverlayPointerEvents} absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-white/20 transition ${
              selected
                ? "border-slate-950 shadow-[0_0_0_4px_rgba(14,165,233,0.18)]"
                : "border-white/80 hover:border-slate-950"
            }`}
            style={{ left: `${left}%`, top: `${top}%` }}
          />
        );
      })}
    </>
  );
}
