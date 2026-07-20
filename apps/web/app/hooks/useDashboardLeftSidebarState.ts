import { useEffect, useState } from "react";

export function useDashboardLeftSidebarState() {
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [sidebarRendered, setSidebarRendered] = useState(true);
  const [sidebarVisible, setSidebarVisible] = useState(true);

  useEffect(() => {
    let timeout: number | undefined;
    const frames: number[] = [];

    if (leftSidebarOpen) {
      frames.push(window.requestAnimationFrame(() => setSidebarRendered(true)));
      frames.push(window.requestAnimationFrame(() => setSidebarVisible(true)));
    } else {
      frames.push(window.requestAnimationFrame(() => setSidebarVisible(false)));
      timeout = window.setTimeout(() => setSidebarRendered(false), 180);
    }

    return () => {
      frames.forEach((frame) => window.cancelAnimationFrame(frame));
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [leftSidebarOpen]);

  return {
    leftSidebarOpen,
    setLeftSidebarOpen,
    sidebarRendered,
    sidebarVisible,
    setSidebarVisible,
  };
}
