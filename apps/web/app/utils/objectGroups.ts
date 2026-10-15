import type {BuildingPlacement} from "../types";
export function groupDescendantIds(groupId: string, objects: BuildingPlacement[]): string[] {
  const ids = new Set([groupId]);
  let grew=true;
  while (grew) {
    grew=false;
    for (const item of objects) if (typeof item.meta?.group_id==="string" && ids.has(item.meta.group_id) && !ids.has(item.id)) { ids.add(item.id); grew=true; }
  }
  ids.delete(groupId);
  return [...ids];
}
/** Visibility is presentation, not permission to omit a physical obstacle. */
export function isPhysicalCanvasObject(item: {id?:string;type?:string;meta?:Record<string,unknown>}, objects: Array<{id?:string;meta?:Record<string,unknown>}>): boolean {
  if (item.type === "group") return false;
  if (Array.isArray(item.meta?.combined_from_object_ids) && item.meta.combined_from_object_ids.length && item.meta?.semantic_source_mode !== "linework") return false;
  const owner=objects.find(object=>object.id===item.meta?.combined_into_object_id);
  return owner?.meta?.semantic_source_mode !== "linework";
}
