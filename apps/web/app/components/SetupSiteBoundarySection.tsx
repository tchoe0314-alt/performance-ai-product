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
  onLotWidthChange,
  onLotHeightChange,
  onStartSiteBoundaryDraw,
  onApplySite,
  onUnlockSite,
  onCreateCenteredSite,
}: SetupSiteBoundarySectionProps) {
  const hasSiteDimensions = Boolean(lotBounds.w && lotBounds.h);
  const hasTypedSiteSize = Number(lotWidth) > 0 && Number(lotHeight) > 0;
  const canLockBoundary = hasSiteDimensions || hasTypedSiteSize;
  return (
    <DisclosurePanel
      testId="setup-site-box-controls"
      title="Site Boundary"
      subtitle={hasSiteDimensions ? `${lotBounds.w!.toFixed(0)} ft x ${lotBounds.h!.toFixed(0)} ft` : "No site boundary yet"}
      status={siteScaleLocked ? "Ready" : hasSiteDimensions ? "Editing" : "Not set"}
      statusClassName={siteScaleLocked ? "bg-emerald-50 text-emerald-700" : hasSiteDimensions ? "bg-sky-50 text-sky-700" : "bg-amber-50 text-amber-700"}
    >
      <p className="mb-3 text-xs leading-5 text-slate-500">
        Enter a size centered on the address, or draw the exact boundary on the canvas.
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
        <label className="flex flex-col gap-1 font-semibold">
          Width (ft)
          <span className="sr-only">Site width in feet</span>
          <input
            type="number"
            value={lotWidth}
            disabled={siteScaleLocked}
            onChange={(event) => onLotWidthChange(event.target.value)}
            className="rounded-[7px] border border-slate-200 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
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
            className="rounded-[7px] border border-slate-200 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
          />
        </label>
      </div>
      {siteTooLargeForWarning ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          {oversizedSiteMessage}
        </p>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          data-testid="setup-draw-site-boundary"
          aria-label="Draw Site Boundary"
          onClick={onStartSiteBoundaryDraw}
          disabled={siteScaleLocked}
          className="rounded-[7px] border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {siteScaleLocked ? "Site is ready" : "Draw Site Boundary"}
        </button>
        <button
          type="button"
          data-testid="create-centered-site-button"
          onClick={siteScaleLocked ? onUnlockSite : siteAddress.trim() ? onCreateCenteredSite : onApplySite}
          disabled={!siteScaleLocked && !canLockBoundary}
          title={!siteScaleLocked && !canLockBoundary ? "Enter width and depth, or draw a boundary first" : undefined}
          className="rounded-[7px] border border-blue-600 bg-blue-600 px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-500"
        >
          {siteScaleLocked ? "Edit site" : canLockBoundary ? "Use this site" : "Enter a size"}
        </button>
      </div>
      <button
        type="button"
        onClick={() => {
          onLotWidthChange("1000");
          onLotHeightChange("1000");
        }}
        disabled={siteScaleLocked}
        className="mt-2 w-full px-2 py-1.5 text-xs font-semibold text-slate-500 transition hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        data-testid="use-1000-site-size"
      >
        Use 1000 x 1000 ft
      </button>
    </DisclosurePanel>
  );
}
