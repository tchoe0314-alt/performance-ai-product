import { useCallback, useMemo, useState } from "react";
import { formatCalmCadStatus, type CadCommandHistoryEntry } from "../components/previewPanelTypes";

/** A single feedback history for all preview CAD command paths. */
export function usePreviewCadCommandFeedback() {
  const [cadCommandStatus, setCadCommandStatus] = useState("Commands: LINE, PLINE, RECTANGLE, CIRCLE, ARC, ARRAY, ALIGN, DISTRIBUTE, DIST, OFFSET, TRIM, EXTEND, FILLET, JOIN, SPLIT, CLOSE, OPEN, REVERSE, HATCH, MIRROR, MOVE, ROTATE, SCALE, COPY, DELETE, DIM, TEXT, LAYER, SNAP, ORTHO.");
  const [cadCommandHistory, setCadCommandHistory] = useState<CadCommandHistoryEntry[]>([]);
  const pushCadCommandFeedback = useCallback((command: string, status: CadCommandHistoryEntry["status"], message: string) => {
    setCadCommandStatus(message);
    setCadCommandHistory((prev) => [
      ...prev.slice(-11),
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        command: command || "COMMAND",
        status,
        message,
      },
    ]);
  }, []);
  const cadCommandStatusDisplay = useMemo(() => formatCalmCadStatus(cadCommandStatus), [cadCommandStatus]);
  const cadCommandHistoryDisplay = useMemo(
    () =>
      cadCommandHistory.map((entry) => ({
        ...entry,
        message: formatCalmCadStatus(entry.message),
      })),
    [cadCommandHistory],
  );
  return { setCadCommandStatus, pushCadCommandFeedback, cadCommandStatusDisplay, cadCommandHistoryDisplay };
}
