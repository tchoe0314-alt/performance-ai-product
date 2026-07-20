type PreviewMapStatusOverlayProps = {
  debugEnabled: boolean;
  geocode: { lat?: number | null; lng?: number | null } | null | undefined;
  showMap: boolean;
  previewQuality: "standard" | "high";
  previewMode: "2d" | "3d";
  mapLoaded: boolean;
  mapboxRequestCount: number;
  mapboxTileCount: number;
  mapContainerSize: { w: number; h: number } | null;
  mapCanvasSize: { w: number; h: number } | null;
  mapError: string | null;
  showMap3D: boolean;
  siteRotationDeg?: number | null;
};

export function PreviewMapStatusOverlay({
  debugEnabled,
  geocode,
  showMap,
  previewQuality,
  previewMode,
  mapLoaded,
  mapboxRequestCount,
  mapboxTileCount,
  mapContainerSize,
  mapCanvasSize,
  mapError,
  showMap3D,
  siteRotationDeg,
}: PreviewMapStatusOverlayProps) {
  return (
    <>
      {debugEnabled ? (
        <div className="pointer-events-none absolute left-5 top-5 z-30 rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] text-slate-700 shadow-sm">
          <div className="font-semibold">Map Debug</div>
          <div>geocode: {geocode?.lat && geocode?.lng ? `${geocode.lat.toFixed(6)}, ${geocode.lng.toFixed(6)}` : "null"}</div>
          <div>showMap: {showMap ? "true" : "false"}</div>
          <div>quality: {previewQuality}</div>
          <div>dimension: {previewMode}</div>
          <div>mapLoaded: {mapLoaded ? "true" : "false"}</div>
          <div>mapbox requests: {mapboxRequestCount}</div>
          <div>mapbox tiles: {mapboxTileCount}</div>
          <div>container: {mapContainerSize ? `${mapContainerSize.w}×${mapContainerSize.h}` : "null"}</div>
          <div>canvas: {mapCanvasSize ? `${mapCanvasSize.w}×${mapCanvasSize.h}` : "null"}</div>
          {mapError ? <div className="text-rose-600">error: {mapError}</div> : null}
        </div>
      ) : null}
      {showMap ? (
        <div className="pointer-events-none absolute right-5 top-5 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
          {showMap3D ? "3D Map" : "2D Map"} · N ↑ {typeof siteRotationDeg === "number" ? `${siteRotationDeg.toFixed(1)}°` : "0°"}
        </div>
      ) : null}
    </>
  );
}
