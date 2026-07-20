import { useCallback, useEffect, useState } from "react";

type ViewportFootprint = {
  widthFt: number;
  heightFt: number;
  bounds?: {
    north: number;
    south: number;
    east: number;
    west: number;
    centerLat: number;
    centerLng: number;
  };
};

type ViewportCenter = {
  lat: number;
  lng: number;
};

type UseDashboardViewportStateInput = {
  onCollapseRightRail: (collapsed: boolean) => void;
};

export function useDashboardViewportState({
  onCollapseRightRail,
}: UseDashboardViewportStateInput) {
  const [mobileViewport, setMobileViewport] = useState(false);
  const [viewportFootprint, setViewportFootprint] = useState<ViewportFootprint | null>(null);
  const [viewportCenter, setViewportCenter] = useState<ViewportCenter | null>(null);

  const handleViewportFootprint = useCallback((value: ViewportFootprint) => {
    setViewportFootprint((prev) => {
      if (
        prev &&
        Math.abs(prev.widthFt - value.widthFt) < 0.01 &&
        Math.abs(prev.heightFt - value.heightFt) < 0.01 &&
        Math.abs((prev.bounds?.north ?? 0) - (value.bounds?.north ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.south ?? 0) - (value.bounds?.south ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.east ?? 0) - (value.bounds?.east ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.west ?? 0) - (value.bounds?.west ?? 0)) < 1e-7
      ) {
        return prev;
      }
      return value;
    });
  }, []);

  const handleViewportCenter = useCallback((value: ViewportCenter) => {
    setViewportCenter((prev) => {
      if (prev && Math.abs(prev.lat - value.lat) < 1e-7 && Math.abs(prev.lng - value.lng) < 1e-7) {
        return prev;
      }
      return value;
    });
  }, []);

  useEffect(() => {
    const syncViewport = () => setMobileViewport(window.innerWidth < 1024);
    syncViewport();
    window.addEventListener("resize", syncViewport);
    if (window.innerWidth < 1024) {
      onCollapseRightRail(true);
    }
    return () => window.removeEventListener("resize", syncViewport);
  }, [onCollapseRightRail]);

  return {
    handleViewportCenter,
    handleViewportFootprint,
    mobileViewport,
    setViewportCenter,
    setViewportFootprint,
    viewportCenter,
    viewportFootprint,
  };
}
