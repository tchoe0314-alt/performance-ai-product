export const PROJECT_TYPE_OPTIONS = [
  { value: "commercial_pad", label: "Commercial pad / retail site" },
  { value: "office_site", label: "Office site" },
  { value: "multifamily_site", label: "Multifamily residential" },
  { value: "mixed_use", label: "Mixed use" },
  { value: "industrial_site", label: "Industrial site" },
  { value: "roadway_corridor", label: "Roadway corridor" },
  { value: "constrained_site", label: "Constrained site" },
  { value: "retaining_wall_site", label: "Retaining wall site" },
] as const;

export function projectTypeLabel(value: string): string | null {
  return PROJECT_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? null;
}
