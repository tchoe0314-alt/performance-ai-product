let preview3DModulePromise: ReturnType<typeof importPreview3DCanvas> | null = null;

function importPreview3DCanvas() {
  return import("./Preview3DCanvas");
}

export function loadPreview3DCanvas() {
  preview3DModulePromise ??= importPreview3DCanvas();
  return preview3DModulePromise;
}
