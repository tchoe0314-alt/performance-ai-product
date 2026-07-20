import { useCallback, useEffect, useRef, useState } from "react";

import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";

export function useDashboardDraftHistoryState() {
  const [lastDraftAction, setLastDraftAction] = useState<DraftUndoAction | null>(null);
  const lastDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [redoDraftAction, setRedoDraftAction] = useState<DraftUndoAction | null>(null);
  const redoDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [recentChanges, setRecentChanges] = useState<RecentChange[]>([]);
  const [recentChangesOpen, setRecentChangesOpen] = useState(false);

  useEffect(() => {
    lastDraftActionRef.current = lastDraftAction;
  }, [lastDraftAction]);

  useEffect(() => {
    redoDraftActionRef.current = redoDraftAction;
  }, [redoDraftAction]);

  const recordDraftUndoAction = useCallback((action: DraftUndoAction) => {
    lastDraftActionRef.current = action;
    setLastDraftAction(action);
    redoDraftActionRef.current = null;
    setRedoDraftAction(null);
  }, []);

  const recordDraftRedoAction = useCallback((action: DraftUndoAction) => {
    redoDraftActionRef.current = action;
    setRedoDraftAction(action);
  }, []);

  const clearDraftUndoAction = useCallback(() => {
    lastDraftActionRef.current = null;
    setLastDraftAction(null);
  }, []);

  return {
    clearDraftUndoAction,
    lastDraftAction,
    lastDraftActionRef,
    recentChanges,
    recentChangesOpen,
    recordDraftRedoAction,
    recordDraftUndoAction,
    redoDraftAction,
    redoDraftActionRef,
    setRecentChanges,
    setRecentChangesOpen,
  };
}
