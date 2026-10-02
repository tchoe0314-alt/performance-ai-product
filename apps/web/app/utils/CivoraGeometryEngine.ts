export type Point2D = { x: number; y: number };

/** x/y locate the center of the building footprint. */
export type OBB = {
  x: number;
  y: number;
  width: number;
  length: number;
  rotationDeg: number;
};

export type ClearanceResult = {
  hasCollision: boolean;
  shortestDistanceFt: number;
  closestPointOnCurb: Point2D;
};

type Segment = { a: Point2D; b: Point2D };
type Arc = { center: Point2D; radius: number; start: number; sweep: number };
type Candidate = { distance: number; curb: Point2D };

const TAU = Math.PI * 2;
const EPS = 1e-9;

const add = (a: Point2D, b: Point2D): Point2D => ({ x: a.x + b.x, y: a.y + b.y });
const sub = (a: Point2D, b: Point2D): Point2D => ({ x: a.x - b.x, y: a.y - b.y });
const scale = (v: Point2D, amount: number): Point2D => ({ x: v.x * amount, y: v.y * amount });
const dot = (a: Point2D, b: Point2D) => a.x * b.x + a.y * b.y;
const magnitude = (v: Point2D) => Math.hypot(v.x, v.y);
const distance = (a: Point2D, b: Point2D) => magnitude(sub(a, b));
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

/**
 * Analytic narrow-phase clearance engine for Civora's canonical cul-de-sac.
 *
 * Coordinates follow the concept renderer: the bulb is centered at the origin,
 * the approach road is centered on the Y axis and extends toward positive Y.
 * Positive clearance means separation, zero means curb contact/crossing, and a
 * negative value means the building is wholly inside the roadway envelope.
 */
export class CivoraGeometryEngine {
  public constructor(private readonly transitionRadiusFt = 20) {
    if (!Number.isFinite(transitionRadiusFt) || transitionRadiusFt <= 0) {
      throw new RangeError("transitionRadiusFt must be a positive finite number.");
    }
  }

  public checkClearance(building: OBB, roadWidth: number, bulbRadius: number): ClearanceResult {
    this.validate(building, roadWidth, bulbRadius);

    const halfRoad = roadWidth / 2;
    const filletCenterX = halfRoad + this.transitionRadiusFt;
    const centerDistance = bulbRadius + this.transitionRadiusFt;
    const radicand = centerDistance * centerDistance - filletCenterX * filletCenterX;
    const filletCenterY = Math.sqrt(Math.max(0, radicand));
    const tangentAngle = Math.atan2(filletCenterY, filletCenterX);
    const edges = this.obbEdges(building);
    const arcs: Arc[] = [
      { center: { x: -filletCenterX, y: filletCenterY }, radius: this.transitionRadiusFt, start: 0, sweep: -tangentAngle },
      { center: { x: 0, y: 0 }, radius: bulbRadius, start: Math.PI - tangentAngle, sweep: Math.PI + 2 * tangentAngle },
      { center: { x: filletCenterX, y: filletCenterY }, radius: this.transitionRadiusFt, start: -Math.PI + tangentAngle, sweep: -tangentAngle },
    ];

    let best: Candidate = { distance: Number.POSITIVE_INFINITY, curb: { x: 0, y: 0 } };
    for (const edge of edges) {
      for (const arc of arcs) best = this.prefer(best, this.segmentToArc(edge, arc));
      best = this.prefer(best, this.segmentToVerticalRay(edge, -halfRoad, filletCenterY));
      best = this.prefer(best, this.segmentToVerticalRay(edge, halfRoad, filletCenterY));
    }

    const intersectsCurb = best.distance <= EPS;
    const vertices = edges.map(edge => edge.a);
    const occupiesRoad = vertices.some(point => this.pointInRoad(point, halfRoad, bulbRadius, filletCenterX, filletCenterY)) ||
      this.pointInObb({ x: 0, y: 0 }, building);
    const signedDistance = intersectsCurb ? 0 : occupiesRoad ? -best.distance : best.distance;

    return {
      hasCollision: signedDistance <= 0,
      shortestDistanceFt: signedDistance,
      closestPointOnCurb: best.curb,
    };
  }

  private validate(building: OBB, roadWidth: number, bulbRadius: number) {
    const values = [building.x, building.y, building.width, building.length, building.rotationDeg, roadWidth, bulbRadius];
    if (!values.every(Number.isFinite)) throw new TypeError("All geometry inputs must be finite numbers.");
    if (building.width <= 0 || building.length <= 0) throw new RangeError("Building width and length must be positive.");
    if (roadWidth <= 0 || bulbRadius <= 0) throw new RangeError("Road width and bulb radius must be positive.");
    if (roadWidth >= 2 * bulbRadius) {
      throw new RangeError("A non-degenerate tangent layout requires roadWidth < 2 * bulbRadius.");
    }
  }

  private obbEdges(building: OBB): Segment[] {
    const angle = building.rotationDeg * Math.PI / 180;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const rotate = (x: number, y: number): Point2D => ({
      x: building.x + x * cos - y * sin,
      y: building.y + x * sin + y * cos,
    });
    const hw = building.width / 2, hl = building.length / 2;
    const vertices = [rotate(-hw, -hl), rotate(hw, -hl), rotate(hw, hl), rotate(-hw, hl)];
    return vertices.map((a, index) => ({ a, b: vertices[(index + 1) % vertices.length] }));
  }

  private segmentToArc(segment: Segment, arc: Arc): Candidate {
    const direction = sub(segment.b, segment.a);
    const fromCenter = sub(segment.a, arc.center);
    const qa = dot(direction, direction);
    const qb = 2 * dot(fromCenter, direction);
    const qc = dot(fromCenter, fromCenter) - arc.radius * arc.radius;
    const discriminant = qb * qb - 4 * qa * qc;
    if (discriminant >= -EPS) {
      const root = Math.sqrt(Math.max(0, discriminant));
      for (const t of [(-qb - root) / (2 * qa), (-qb + root) / (2 * qa)]) {
        if (t >= -EPS && t <= 1 + EPS) {
          const point = add(segment.a, scale(direction, clamp(t, 0, 1)));
          if (this.angleOnArc(Math.atan2(point.y - arc.center.y, point.x - arc.center.x), arc)) {
            return { distance: 0, curb: point };
          }
        }
      }
    }

    let best = this.pointToArc(segment.a, arc);
    best = this.prefer(best, this.pointToArc(segment.b, arc));
    for (const angle of [arc.start, arc.start + arc.sweep]) {
      const curb = this.arcPoint(arc, angle);
      const point = this.closestPointOnSegment(curb, segment);
      best = this.prefer(best, { distance: distance(point, curb), curb });
    }

    const closestToCenter = this.closestPointOnSegment(arc.center, segment);
    const radial = sub(closestToCenter, arc.center);
    const radialLength = magnitude(radial);
    if (radialLength > EPS) {
      const curb = add(arc.center, scale(radial, arc.radius / radialLength));
      if (this.angleOnArc(Math.atan2(radial.y, radial.x), arc)) {
        best = this.prefer(best, { distance: distance(closestToCenter, curb), curb });
      }
    }
    return best;
  }

  private segmentToVerticalRay(segment: Segment, x: number, minY: number): Candidate {
    const dx = segment.b.x - segment.a.x;
    if (Math.abs(dx) > EPS) {
      const t = (x - segment.a.x) / dx;
      if (t >= -EPS && t <= 1 + EPS) {
        const y = segment.a.y + t * (segment.b.y - segment.a.y);
        if (y >= minY - EPS) return { distance: 0, curb: { x, y: Math.max(y, minY) } };
      }
    } else if (Math.abs(segment.a.x - x) <= EPS && Math.max(segment.a.y, segment.b.y) >= minY - EPS) {
      return { distance: 0, curb: { x, y: Math.max(minY, Math.min(segment.a.y, segment.b.y)) } };
    }

    let best = this.pointToVerticalRay(segment.a, x, minY);
    best = this.prefer(best, this.pointToVerticalRay(segment.b, x, minY));
    const origin = { x, y: minY };
    const onSegment = this.closestPointOnSegment(origin, segment);
    return this.prefer(best, { distance: distance(onSegment, origin), curb: origin });
  }

  private pointToArc(point: Point2D, arc: Arc): Candidate {
    const radial = sub(point, arc.center);
    const length = magnitude(radial);
    if (length > EPS) {
      const angle = Math.atan2(radial.y, radial.x);
      if (this.angleOnArc(angle, arc)) {
        const curb = add(arc.center, scale(radial, arc.radius / length));
        return { distance: Math.abs(length - arc.radius), curb };
      }
    }
    const start = this.arcPoint(arc, arc.start);
    const end = this.arcPoint(arc, arc.start + arc.sweep);
    return distance(point, start) <= distance(point, end)
      ? { distance: distance(point, start), curb: start }
      : { distance: distance(point, end), curb: end };
  }

  private pointToVerticalRay(point: Point2D, x: number, minY: number): Candidate {
    const curb = { x, y: Math.max(point.y, minY) };
    return { distance: distance(point, curb), curb };
  }

  private closestPointOnSegment(point: Point2D, segment: Segment): Point2D {
    const direction = sub(segment.b, segment.a);
    const lengthSquared = dot(direction, direction);
    const t = lengthSquared <= EPS ? 0 : clamp(dot(sub(point, segment.a), direction) / lengthSquared, 0, 1);
    return add(segment.a, scale(direction, t));
  }

  private pointInRoad(point: Point2D, halfRoad: number, bulbRadius: number, filletCenterX: number, filletCenterY: number) {
    if (point.y < -bulbRadius - EPS) return false;
    const tangentY = bulbRadius * filletCenterY / (bulbRadius + this.transitionRadiusFt);
    const extent = point.y <= tangentY
      ? Math.sqrt(Math.max(0, bulbRadius * bulbRadius - point.y * point.y))
      : point.y < filletCenterY
        ? filletCenterX - Math.sqrt(Math.max(0, this.transitionRadiusFt ** 2 - (point.y - filletCenterY) ** 2))
        : halfRoad;
    return Math.abs(point.x) <= extent + EPS;
  }

  private pointInObb(point: Point2D, building: OBB) {
    const angle = -building.rotationDeg * Math.PI / 180;
    const delta = sub(point, building);
    const localX = delta.x * Math.cos(angle) - delta.y * Math.sin(angle);
    const localY = delta.x * Math.sin(angle) + delta.y * Math.cos(angle);
    return Math.abs(localX) <= building.width / 2 + EPS && Math.abs(localY) <= building.length / 2 + EPS;
  }

  private angleOnArc(angle: number, arc: Arc) {
    const directed = arc.sweep >= 0 ? angle - arc.start : arc.start - angle;
    const progress = ((directed % TAU) + TAU) % TAU;
    return progress <= Math.abs(arc.sweep) + EPS || TAU - progress <= EPS;
  }

  private arcPoint(arc: Arc, angle: number): Point2D {
    return { x: arc.center.x + arc.radius * Math.cos(angle), y: arc.center.y + arc.radius * Math.sin(angle) };
  }

  private prefer(current: Candidate, candidate: Candidate) {
    return candidate.distance < current.distance ? candidate : current;
  }
}
