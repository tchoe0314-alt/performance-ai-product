import type { ReactNode } from "react";

type Props = {
  onCancelActiveTool: () => void;
  statusSummary: string;
  toasts: ReactNode;
  header: ReactNode;
  leftRail: ReactNode;
  rightPanel: ReactNode;
  canvas: ReactNode;
  shortcuts: ReactNode;
  commandBar: ReactNode;
};

/** Presentation-only frame: responsive regions and Escape, never project/geometry state. */
export function DashboardWorkspaceFrame(props: Props) {
  return (
    <div className="civora-app-bg min-h-screen text-[var(--civora-text)]" onKeyDownCapture={event => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      props.onCancelActiveTool();
    }}>
      {props.toasts}
      <div className="flex min-h-screen flex-col">
        {props.header}
        <div data-testid="project-status-summary" className="sr-only" aria-live="polite">{props.statusSummary}</div>
        <div className="relative h-[calc(100svh-52px)] min-h-0 w-full max-w-full overflow-hidden lg:h-[calc(100vh-52px)]">
          {props.leftRail}
          {props.rightPanel}
          {props.canvas}
          {props.shortcuts}
          {props.commandBar}
        </div>
      </div>
    </div>
  );
}
