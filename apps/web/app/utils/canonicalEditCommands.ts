import type { BuildingPlacement } from "../types";

export type CanonicalEditSource = "manual_cad" | "chat" | "generator" | "dependency" | "system";
export type CanonicalControlState = "fixed" | "flexible" | "suggested" | "existing" | "reference";

export type CanonicalUpdateCommand = {
  kind: "update_object";
  objectId: string;
  updates: Partial<BuildingPlacement>;
  source: CanonicalEditSource;
  transactionId: string;
  createdAt: string;
};

export type CanonicalEditResult = {
  object: BuildingPlacement;
  command: CanonicalUpdateCommand;
  changedFields: string[];
  blockedReason: string | null;
};

const GEOMETRY_FIELDS: Array<keyof BuildingPlacement> = ["x", "y", "w", "d", "h", "rotation", "geometry"];

export function canonicalControlState(object: BuildingPlacement): CanonicalControlState {
  const declared = String(object.meta?.canonical_control_state ?? "").trim().toLowerCase();
  if (["fixed", "flexible", "suggested", "existing", "reference"].includes(declared)) {
    return declared as CanonicalControlState;
  }
  if (object.locked) return "fixed";
  if (object.source === "detected_from_gis" || object.meta?.existing_condition === true) return "existing";
  if (object.generated || object.source === "generated" || object.source === "inferred") return "suggested";
  return "flexible";
}

export function createCanonicalUpdateCommand(
  objectId: string,
  updates: Partial<BuildingPlacement>,
  source: CanonicalEditSource = "manual_cad",
  transactionId = `canonical-${objectId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  createdAt = new Date().toISOString(),
): CanonicalUpdateCommand {
  return { kind: "update_object", objectId, updates, source, transactionId, createdAt };
}

/** Check the whole deletion group before changing state or invalidating results. */
export function canonicalDeletionBlocker(objects: BuildingPlacement[]): string | null {
  for (const object of objects) {
    const state = canonicalControlState(object);
    if (object.type === "site" || object.capabilities?.deletable === false || object.meta?.ai_realism_artifact) {
      return `${object.label} is required or source-only evidence and cannot be deleted here.`;
    }
    if (object.locked || ["fixed", "existing", "reference"].includes(state)) {
      return `${object.label} is protected (${state}). Explicitly unlock it and set it to flexible before deleting.`;
    }
  }
  return null;
}

/** Regeneration deletes the old generated program; it must honor the same protection. */
export function canonicalConceptReplacementBlocker(objects: BuildingPlacement[]): string | null {
  const reason = canonicalDeletionBlocker(objects.filter(object => object.type !== "site" && object.meta?.dense_concept_generated));
  return reason ? `Concept replacement blocked. ${reason} The working plan is unchanged.` : null;
}

export function applyCanonicalUpdateCommand(
  current: BuildingPlacement,
  command: CanonicalUpdateCommand,
): CanonicalEditResult {
  const changedFields = Object.keys(command.updates).filter((key) => key !== "meta");
  const controlState = canonicalControlState(current);
  const changesGeometry = GEOMETRY_FIELDS.some((field) => command.updates[field] !== undefined);
  const explicitlyUnlocks = command.updates.locked === false || command.updates.meta?.canonical_control_state === "flexible";
  const mayOverrideProtection = command.source === "system" || explicitlyUnlocks;

  if (changesGeometry && !mayOverrideProtection && ["fixed", "existing", "reference"].includes(controlState)) {
    return {
      object: current,
      command,
      changedFields: [],
      blockedReason: `${current.label} is ${controlState}. Set it to flexible before changing its geometry.`,
    };
  }

  const previousRevision = Number(current.meta?.canonical_revision ?? 0);
  const nextControlState = command.updates.locked === true
    ? "fixed"
    : command.updates.locked === false
      ? "flexible"
      : command.updates.meta?.canonical_control_state ?? controlState;
  const object: BuildingPlacement = {
    ...current,
    ...command.updates,
    meta: {
      ...(current.meta ?? {}),
      ...(command.updates.meta ?? {}),
      canonical_control_state: nextControlState,
      canonical_revision: previousRevision + 1,
      canonical_last_edit: {
        transaction_id: command.transactionId,
        source: command.source,
        command: command.kind,
        changed_fields: changedFields,
        created_at: command.createdAt,
      },
    },
  };

  return { object, command, changedFields, blockedReason: null };
}
