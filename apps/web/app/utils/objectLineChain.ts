import type { BuildingPlacement } from "../types";

/** Orders an exact connected chain in either direction, without silently snapping. */
export function connectedLineChain(objects: BuildingPlacement[]): { points: Array<[number, number]>; closed: boolean; error?: string } {
  type Point = [number, number];
  const edges: Array<[Point, Point]> = [];
  const same = (a: Point, b: Point) => Math.hypot(a[0]-b[0], a[1]-b[1]) <= 1e-7;
  for (const object of objects) {
    if (object.geometryType !== "polyline" || !object.geometry || object.geometry.length < 2) return { points: [], closed: false, error: "Select connected lines only." };
    for (let i=1; i<object.geometry.length; i++) {
      const a=object.geometry[i-1], b=object.geometry[i];
      if (![...a,...b].every(Number.isFinite) || same(a,b) || edges.some(([c,d]) => (same(a,c)&&same(b,d)) || (same(a,d)&&same(b,c)))) return { points: [], closed: false, error: "Remove duplicate or zero-length lines." };
      edges.push([a,b]);
    }
  }
  if (!edges.length) return { points: [], closed: false, error: "Select at least one line." };
  const vertices: Array<{ point: Point; degree: number }> = [];
  for (const edge of edges) for (const point of edge) {
    const vertex=vertices.find(v=>same(v.point,point));
    if (vertex) vertex.degree++; else vertices.push({point,degree:1});
  }
  const ends=vertices.filter(v=>v.degree===1);
  if (vertices.some(v=>v.degree>2) || ![0,2].includes(ends.length)) return { points: [], closed: false, error: "Select one chain without branches." };
  const points: Point[]=[ends[0]?.point ?? edges[0][0]];
  while (edges.length) {
    const current=points.at(-1)!;
    const index=edges.findIndex(([a,b])=>same(a,current)||same(b,current));
    if (index<0) return { points: [], closed: false, error: "Lines must touch exactly; close gaps first." };
    const [a,b]=edges.splice(index,1)[0];
    points.push(same(a,current)?b:a);
  }
  const closed=same(points[0],points.at(-1)!);
  return { points: closed?points.slice(0,-1):points, closed };
}
