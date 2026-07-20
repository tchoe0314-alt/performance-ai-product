import type { ComponentType } from "react";
import { Hand, MapPin, MousePointer2, Pentagon, PencilLine, Square } from "lucide-react";

import type { DrawMode } from "./cadToolTypes";

export type PreviewDrawModeButton = {
  mode: DrawMode;
  label: string;
  icon: ComponentType<{ className?: string }>;
  disabled?: boolean;
  disabledLabel?: string;
};

export function buildPreviewDrawModeButtons({
  siteLocked,
  canDrawObjects,
  drawObjectsDisabledLabel,
}: {
  siteLocked: boolean;
  canDrawObjects: boolean;
  drawObjectsDisabledLabel: string;
}): PreviewDrawModeButton[] {
  return [
    { mode: "select", label: "Select", icon: MousePointer2 },
    { mode: "pan", label: "Pan", icon: Hand },
    {
      mode: "site",
      label: "Draw Site Boundary",
      icon: Pentagon,
      disabled: siteLocked,
      disabledLabel: "Change site boundary before drawing a new boundary",
    },
    {
      mode: "polyline",
      label: "Add Line",
      icon: PencilLine,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "polygon",
      label: "Add Area",
      icon: Pentagon,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "rect",
      label: "Add Box",
      icon: Square,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "point",
      label: "Add Point",
      icon: MapPin,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
  ];
}
