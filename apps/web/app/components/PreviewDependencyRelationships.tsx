import type { BuildingPlacement } from "../types";
import { dependencyLinks } from "../utils/dependencyGraph";

type PreviewDependencyRelationshipsProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  mapAnchoredRectPercent: (item: BuildingPlacement) => { left: number; top: number; width: number; height: number };
};

const centerOf = (
  item: BuildingPlacement,
  mapAnchoredRectPercent: PreviewDependencyRelationshipsProps["mapAnchoredRectPercent"],
) => {
  const rect = mapAnchoredRectPercent(item);
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
};

export function PreviewDependencyRelationships({
  objects,
  selectedBuildingId,
  mapAnchoredRectPercent,
}: PreviewDependencyRelationshipsProps) {
  const byId = new Map(objects.map((item) => [item.id, item]));
  const relationships = objects.flatMap((building) =>
    dependencyLinks(building,objects).flatMap(({target_id:parkingId, policy}) => {
      const parking = byId.get(parkingId);
      return parking ? [{ building, parking, policy }] : [];
    }),
  );
  if (!relationships.length) return null;
  return (
    <g data-testid="dependency-relationship-lines" aria-label="Linked object relationships">
      {relationships.map(({ building, parking, policy }) => {
        const from = centerOf(building, mapAnchoredRectPercent);
        const to = centerOf(parking, mapAnchoredRectPercent);
        const selected = building.id === selectedBuildingId || parking.id === selectedBuildingId;
        return (
          <g key={`${building.id}-${parking.id}`} data-testid={`dependency-link-${building.id}-${parking.id}`} data-relationship-policy={policy}>
            <title>{building.label} → {parking.label}: {policy === "follow" ? "Following" : policy}</title>
            <line
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke={selected ? "#2563eb" : "#94a3b8"}
              strokeWidth={selected ? 0.65 : 0.35}
              strokeDasharray={policy === "follow" ? undefined : policy === "fixed" ? "4 1" : policy === "independent" ? "0.4 2" : "1.5 1.25"}
              opacity={selected ? 0.95 : 0.45}
              vectorEffect="non-scaling-stroke"
            />
            {selected ? (
              <>
                <circle cx={from.x} cy={from.y} r="0.8" fill="#2563eb" />
                <circle cx={to.x} cy={to.y} r="0.8" fill="#2563eb" />
              </>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}
