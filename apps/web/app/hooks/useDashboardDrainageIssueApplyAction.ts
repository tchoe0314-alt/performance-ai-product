import { useCallback, type Dispatch, type SetStateAction } from "react";

import type { BuildingPlacement, Issue, SiteObjectType } from "../types";

type Point = { x: number; y: number };
type LotBounds = { x: number; y: number; w: number; h: number };
type ExternalRectUndo = {
  id: string;
  snapshot: BuildingPlacement;
  action: "update" | "delete" | "add";
  ts: number;
} | null;
type ForcedInlet = { x: number; y: number; name?: string };
type RunDrainageAutofix = (input: {
  placementsOverride?: BuildingPlacement[];
  forcedInlets?: Array<Record<string, unknown>>;
  forcedBasins?: Array<Record<string, unknown>>;
  connectOrphans?: boolean;
  allowSlopeAdjust?: boolean;
}) => Promise<boolean>;

type UseDashboardDrainageIssueApplyActionInput = {
  buildingPlacements: BuildingPlacement[];
  clearGeneratedPreview: () => void;
  drainageAllowSlopeAdjust: boolean;
  drainageConnectOrphans: boolean;
  drainageForcedInlets: ForcedInlet[];
  pickBestLowPoint: () => (Point & { z?: number }) | null;
  resolveLotBounds: () => LotBounds;
  runDrainageAutofix: RunDrainageAutofix;
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setDrainageAllowSlopeAdjust: (value: boolean) => void;
  setDrainageConnectOrphans: (value: boolean) => void;
  setDrainageForcedInlets: Dispatch<SetStateAction<ForcedInlet[]>>;
  setExternalRectUndo: Dispatch<SetStateAction<ExternalRectUndo>>;
  setFocusObjectId: (id: string | null) => void;
  setStatusMessage: (message: string) => void;
};

export function useDashboardDrainageIssueApplyAction({
  buildingPlacements,
  clearGeneratedPreview,
  drainageAllowSlopeAdjust,
  drainageConnectOrphans,
  drainageForcedInlets,
  pickBestLowPoint,
  resolveLotBounds,
  runDrainageAutofix,
  setBuildingPlacements,
  setDrainageAllowSlopeAdjust,
  setDrainageConnectOrphans,
  setDrainageForcedInlets,
  setExternalRectUndo,
  setFocusObjectId,
  setStatusMessage,
}: UseDashboardDrainageIssueApplyActionInput) {
  return useCallback(
    async (issue: Issue) => {
      const issueCode = (issue.code ?? "").toUpperCase();
      const lot = resolveLotBounds();
      const lowPoint = pickBestLowPoint();
      const issueX = typeof issue.context?.x === "number" ? issue.context.x : Number(issue.context?.x);
      const issueY = typeof issue.context?.y === "number" ? issue.context.y : Number(issue.context?.y);
      const issueLocation =
        Number.isFinite(issueX) && Number.isFinite(issueY) ? { x: issueX, y: issueY } : null;
      const distanceFt = (a: Point, b: Point) =>
        Math.hypot(a.x - b.x, a.y - b.y);
      const findNearbyPlacement = (
        type: SiteObjectType,
        point: Point,
        threshold: number,
      ) =>
        buildingPlacements.find(
          (item) =>
            item.type === type &&
            item.placed &&
            Number.isFinite(item.x) &&
            Number.isFinite(item.y) &&
            distanceFt({ x: item.x as number, y: item.y as number }, point) <= threshold,
        );

      if (issueCode === "UNDER_COLLECTION" || issueCode === "UNDER_COLLECTION_REDUCED") {
        if (!lowPoint) {
          setStatusMessage("No low points available to place an inlet.");
          return;
        }
        if (issueLocation && distanceFt(lowPoint, issueLocation) > 200) {
          setStatusMessage("Closest low point is too far from the flagged area to place an inlet.");
          return;
        }
        if (findNearbyPlacement("inlet", lowPoint, 10)) {
          setStatusMessage("An inlet already exists near the suggested location.");
          return;
        }
        if (
          drainageForcedInlets.some(
            (item) =>
              typeof item.x === "number" &&
              typeof item.y === "number" &&
              distanceFt({ x: item.x, y: item.y }, lowPoint) <= 8,
          )
        ) {
          setStatusMessage("An inlet is already queued near that location.");
          return;
        }
        const forcedInlet = {
          x: lowPoint.x,
          y: lowPoint.y,
          label: "Autofix inlet",
          source: "autofix",
        };
        const nextForced = [...drainageForcedInlets, forcedInlet];
        setDrainageForcedInlets(nextForced);
        const inletPlacement: BuildingPlacement = {
          id: `inlet-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix inlet",
          type: "inlet",
          w: 8,
          d: 8,
          x: lowPoint.x - 4,
          y: lowPoint.y - 4,
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        setBuildingPlacements((prev) => [...prev, inletPlacement]);
        setExternalRectUndo({
          id: inletPlacement.id,
          snapshot: inletPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(inletPlacement.id);
        const queued = await runDrainageAutofix({
          placementsOverride: [...buildingPlacements, inletPlacement],
          forcedInlets: nextForced,
        });
        if (queued) {
          setStatusMessage("Applied inlet placement. Drainage regenerated.");
        }
        return;
      }

      if (issueCode === "ORPHAN_INLETS") {
        if (drainageConnectOrphans) {
          setStatusMessage("Orphan inlet connection already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageConnectOrphans(true);
        const queued = await runDrainageAutofix({ connectOrphans: true });
        if (queued) {
          setStatusMessage("Applied orphan inlet connection. Drainage regenerated.");
        }
        return;
      }

      if (issueCode === "POOR_SLOPE") {
        if (drainageAllowSlopeAdjust) {
          setStatusMessage("Slope adjustment already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageAllowSlopeAdjust(true);
        const queued = await runDrainageAutofix({ allowSlopeAdjust: true });
        if (queued) {
          setStatusMessage("Applied slope adjustment attempt. Drainage regenerated.");
        }
        return;
      }

      if (
        issueCode === "BASIN_UNREACHABLE" ||
        issueCode === "DRAINAGE_NO_BASIN" ||
        issueCode === "NO_VALID_OUTFALL" ||
        issueCode === "NO_PONDS_DEFINED"
      ) {
        if (!lowPoint) {
          setStatusMessage("No low points available to place a basin.");
          return;
        }
        if (issueCode === "BASIN_UNREACHABLE" && issueLocation && distanceFt(lowPoint, issueLocation) > 300) {
          setStatusMessage("Closest low point is too far from the flagged area to place a basin.");
          return;
        }
        if (findNearbyPlacement("basin", lowPoint, 40)) {
          setStatusMessage("A basin already exists near the suggested location.");
          return;
        }
        const basinPlacement: BuildingPlacement = {
          id: `basin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix basin",
          type: "basin",
          w: 60,
          d: 40,
          x: Math.min(Math.max(lowPoint.x - 30, lot.x), lot.x + lot.w - 60),
          y: Math.min(Math.max(lowPoint.y - 20, lot.y), lot.y + lot.h - 40),
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        const nextPlacements = [...buildingPlacements, basinPlacement];
        setBuildingPlacements(nextPlacements);
        setExternalRectUndo({
          id: basinPlacement.id,
          snapshot: basinPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(basinPlacement.id);
        const forcedBasins = nextPlacements
          .filter((placement) => placement.type === "basin")
          .map((placement) => ({
            id: placement.id,
            name: placement.label,
            x: placement.x,
            y: placement.y,
            w: placement.w,
            d: placement.d,
            rotation: placement.rotation ?? 0,
            locked: placement.locked,
            source: "autofix",
            generated: placement.generated,
            systemDependencies: placement.systemDependencies,
          }));
        const queued = await runDrainageAutofix({
          placementsOverride: nextPlacements,
          forcedBasins,
        });
        if (queued) {
          setStatusMessage("Applied basin placement. Drainage regenerated.");
        }
      }
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      drainageAllowSlopeAdjust,
      drainageConnectOrphans,
      drainageForcedInlets,
      pickBestLowPoint,
      resolveLotBounds,
      runDrainageAutofix,
      setBuildingPlacements,
      setDrainageAllowSlopeAdjust,
      setDrainageConnectOrphans,
      setDrainageForcedInlets,
      setExternalRectUndo,
      setFocusObjectId,
      setStatusMessage,
    ],
  );
}
