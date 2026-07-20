import { useEffect, useRef, useState } from "react";

import type { SidePanelKey } from "../utils/workspaceShell";
import { measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";

type PanelProbe = {
  label: string;
  panel: SidePanelKey;
  startedAt: number;
};

type PanelCloseProbe = {
  label: string;
  panel: SidePanelKey | null;
  startedAt: number;
};

export function useDashboardSidePanelState() {
  const [activeSidePanel, setActiveSidePanel] = useState<SidePanelKey | null>(null);
  const [renderedSidePanel, setRenderedSidePanel] = useState<SidePanelKey | null>(null);
  const [sidePanelVisible, setSidePanelVisible] = useState(false);
  const [rightRailCollapsed, setRightRailCollapsed] = useState(true);
  const panelOpenProbeRef = useRef<PanelProbe | null>(null);
  const panelCloseProbeRef = useRef<PanelCloseProbe | null>(null);
  const sidePanelCloseTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let timeout: number | undefined;
    const frames: number[] = [];

    if (!rightRailCollapsed) {
      frames.push(window.requestAnimationFrame(() => {
        setRenderedSidePanel(activeSidePanel ?? "dashboard");
      }));
      frames.push(window.requestAnimationFrame(() => {
        setSidePanelVisible(true);
        const probe = panelOpenProbeRef.current;
        if (probe && probe.panel === (activeSidePanel ?? "dashboard")) {
          measureCivoraInteractionAfterPaint(probe.label, probe.startedAt, { panel: probe.panel });
          panelOpenProbeRef.current = null;
        }
      }));
    } else {
      frames.push(window.requestAnimationFrame(() => setSidePanelVisible(false)));
      timeout = window.setTimeout(() => {
        setRenderedSidePanel(null);
        const probe = panelCloseProbeRef.current;
        if (probe) {
          measureCivoraInteractionAfterPaint(probe.label, probe.startedAt, { panel: probe.panel ?? "none" });
          panelCloseProbeRef.current = null;
        }
      }, 180);
    }

    return () => {
      frames.forEach((frame) => window.cancelAnimationFrame(frame));
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [activeSidePanel, rightRailCollapsed]);

  return {
    activeSidePanel,
    setActiveSidePanel,
    renderedSidePanel,
    setRenderedSidePanel,
    sidePanelVisible,
    setSidePanelVisible,
    rightRailCollapsed,
    setRightRailCollapsed,
    panelOpenProbeRef,
    panelCloseProbeRef,
    sidePanelCloseTimeoutRef,
  };
}
