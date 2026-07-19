import { DisclosurePanel } from "./ui";

type LotBounds = {
  w?: number;
  h?: number;
};

type SetupSiteBoundarySectionProps = {
  lotBounds: LotBounds;
  lotWidth: string;
  lotHeight: string;
  siteScaleLocked: boolean;
  siteTooLargeForWarning: boolean;
  oversizedSiteMessage: string;
  siteAddress: string;
  onlineDiscoveryBusy: boolean;
  onLotWidthChange: (value: string) => void;
  onLotHeightChange: (value: string) => void;
  onStartSiteBoundaryDraw: () => void;
  onApplySite: () => void;
  onUnlockSite: () => void;
  onCreateCenteredSite: () => void;
};

export function SetupSiteBoundarySection({
  lotBounds,
  lotWidth,
  lotHeight,
  siteScaleLocked,
  siteTooLargeForWarning,
  oversizedSiteMessage,
  siteAddress,
  onlineDiscoveryBusy,
  onLotWidthChange,
  onLotHeightChange,
  onStartSiteBoundaryDraw,
  onApplySite,
  onUnlockSite,
  onCreateCenteredSite,
}: SetupSiteBoundarySectionProps) {
  return (
    <DisclosurePanel
      defaultOpen
      testId="setup-site-box-controls"
      title="Site Boundary"
      subtitle={lotBounds.w && lotBounds.h ? `${lotBounds.w.toFixed(0)} ft x ${lotBounds.h.toFixed(0)} ft` : "No boundary locked"}
      status={siteScaleLocked ? "Locked" : "Needs lock"}
      statusClassName={siteScaleLocked ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}
    >
      <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
        <label className="flex flex-col gap-1 font-semibold">
          Width (ft)
          <span className="sr-only">Site width in feet</span>
          <input
            type="number"
            value={lotWidth}
            disabled={siteScaleLocked}
            onChange={(event) => onLotWidthChange(event.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
          />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Depth (ft)
          <span className="sr-only">Site depth in feet</span>
          <input
            type="number"
            value={lotHeight}
            disabled={siteScaleLocked}
            onChange={(event) => onLotHeightChange(event.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
          />
        </label>
      </div>
      {siteTooLargeForWarning ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          {oversizedSiteMessage}
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => {
          onLotWidthChange("1000");
          onLotHeightChange("1000");
        }}
        disabled={siteScaleLocked}
        className="mt-3 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        data-testid="use-1000-site-size"
      >
        Use 1000 ft x 1000 ft
      </button>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onStartSiteBoundaryDraw}
          disabled={siteScaleLocked}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {siteScaleLocked ? "Boundary Locked" : "Draw Boundary"}
        </button>
        <button
          type="button"
          onClick={siteScaleLocked ? onUnlockSite : onApplySite}
          className="rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800"
        >
          {siteScaleLocked ? "Change Boundary" : "Lock Boundary"}
        </button>
      </div>
      <button
        type="button"
        onClick={onCreateCenteredSite}
        disabled={!siteAddress.trim() || onlineDiscoveryBusy}
        className="mt-2 w-full rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
      >
        Create centered site from address
      </button>
    </DisclosurePanel>
  );
}
