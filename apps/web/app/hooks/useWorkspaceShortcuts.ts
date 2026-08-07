import { useEffect } from "react";

type WorkspaceShortcutActions = {
  onCancelActiveTool: () => void;
  onFocusCommandInput: () => void;
  onOpenShortcuts: () => void;
  onSaveProject: () => void;
  onCopySelectedObject: () => void;
  onPasteSelectedObject: () => void;
  onRedoDraftAction: () => void;
  onUndoDraftAction: () => void;
  onDeleteSelectedObject: () => void;
  onOpenGenerate: () => void;
  onOpenDrawCanvas: () => void;
  onOpenProjects: () => void;
};

const isTypingTarget = (target: EventTarget | null) => {
  const element = target as HTMLElement | null;
  const inputTarget = element instanceof HTMLInputElement ? element : null;
  const isTextInput =
    inputTarget &&
    !["button", "checkbox", "color", "file", "radio", "range", "reset", "submit"].includes(inputTarget.type);
  return Boolean(
    element &&
      (isTextInput ||
        element.tagName === "TEXTAREA" ||
        element.isContentEditable),
  );
};

const consumeShortcut = (event: KeyboardEvent) => {
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
};

export function useWorkspaceShortcuts({
  onCancelActiveTool,
  onFocusCommandInput,
  onOpenShortcuts,
  onSaveProject,
  onCopySelectedObject,
  onPasteSelectedObject,
  onRedoDraftAction,
  onUndoDraftAction,
  onDeleteSelectedObject,
  onOpenGenerate,
  onOpenDrawCanvas,
  onOpenProjects,
}: WorkspaceShortcutActions) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const isTyping = isTypingTarget(event.target);
      const meta = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      if (event.key === "Escape") {
        // Keep Escape observable by the active canvas tool so it can clear its
        // local draft points in addition to resetting workspace-level state.
        event.preventDefault();
        onCancelActiveTool();
        return;
      }
      if (meta && key === "k") {
        consumeShortcut(event);
        onFocusCommandInput();
        return;
      }
      if (!meta && event.key === "/" && !isTyping) {
        consumeShortcut(event);
        onFocusCommandInput();
        return;
      }
      if ((event.key === "?" || (event.shiftKey && event.key === "?")) && !isTyping) {
        consumeShortcut(event);
        onOpenShortcuts();
        return;
      }
      if (meta && key === "s") {
        consumeShortcut(event);
        onSaveProject();
        return;
      }
      if (meta && key === "c" && !isTyping) {
        consumeShortcut(event);
        onCopySelectedObject();
        return;
      }
      if (meta && key === "v" && !isTyping) {
        consumeShortcut(event);
        onPasteSelectedObject();
        return;
      }
      if (meta && (key === "y" || (key === "z" && event.shiftKey))) {
        consumeShortcut(event);
        onRedoDraftAction();
        return;
      }
      if (meta && key === "z") {
        consumeShortcut(event);
        onUndoDraftAction();
        return;
      }
      if (isTyping || meta || event.altKey) return;
      if (event.key === "Delete" || event.key === "Backspace") {
        consumeShortcut(event);
        onDeleteSelectedObject();
        return;
      }
      if (key === "g") {
        consumeShortcut(event);
        onOpenGenerate();
        return;
      }
      if (key === "d") {
        consumeShortcut(event);
        onOpenDrawCanvas();
        return;
      }
      if (key === "p") {
        consumeShortcut(event);
        onOpenProjects();
      }
    };

    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => {
      window.removeEventListener("keydown", onKeyDown, { capture: true });
    };
  }, [
    onCancelActiveTool,
    onCopySelectedObject,
    onDeleteSelectedObject,
    onFocusCommandInput,
    onOpenDrawCanvas,
    onOpenGenerate,
    onOpenProjects,
    onOpenShortcuts,
    onPasteSelectedObject,
    onRedoDraftAction,
    onSaveProject,
    onUndoDraftAction,
  ]);
}
