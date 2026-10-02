/** A delayed transaction must never save or refresh a newer workspace. */
export async function guardedTransactionSave(options: {
  isCurrent: () => boolean;
  ensureDraft: () => Promise<unknown>;
  save: () => Promise<unknown>;
  refresh?: () => void;
  onFailure: () => void;
}) {
  try {
    if (!options.isCurrent()) return "superseded";
    await options.ensureDraft();
    if (!options.isCurrent()) return "superseded";
    const saved = await options.save();
    if (!options.isCurrent()) return "superseded";
    if (!saved) return "unavailable";
    options.refresh?.();
    return "saved";
  } catch {
    if (options.isCurrent()) options.onFailure();
    return "failed";
  }
}
