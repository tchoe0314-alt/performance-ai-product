import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { canonicalPreview3DFootprintSignature } from "../utils/canonicalGeometrySignature";
import { normalizePreview3DLayer } from "../utils/preview3DLayer";
import type { Preview3DItem } from "../types";

type PickedObject = {
  id: string | null;
  label: string;
  layer: string;
  confidence: string;
  blockers: string[];
  source: string;
  heightFt: number | null;
  x: number;
  y: number;
};

type Preview3DCanvasProps = {
  items: Preview3DItem[];
  interactive: boolean;
  fullscreen?: boolean;
  previewQuality?: "standard" | "high";
  selectedItemId?: string | null;
  hasTerrainSource?: boolean;
  hasGradingSurface?: boolean;
  onSelectItem?: (id: string | null) => void;
  onOpenFullscreen?: () => void;
};

const layerPalette: Record<string, { top: string; side: string; line: string }> = {
  BUILDING: { top: "#e8edf2", side: "#8e9dad", line: "#27364a" },
  STRUCTURE: { top: "#dcc79f", side: "#b58d4f", line: "#735426" },
  ROAD: { top: "#7f8a96", side: "#65717e", line: "#f8fafc" },
  PARKING: { top: "#aab4bf", side: "#8794a2", line: "#f8fafc" },
  LOT: { top: "#f8fafc", side: "#e2e8f0", line: "#94a3b8" },
  SIDEWALK: { top: "#d6d3d1", side: "#a8a29e", line: "#78716c" },
  DRAINAGE: { top: "#6bb7c8", side: "#3b8ca2", line: "#dff7fb" },
  UTILITY: { top: "#6d5bd0", side: "#4f46e5", line: "#ede9fe" },
  CONSTRAINT: { top: "#f8b4a5", side: "#f97360", line: "#9f3412" },
  TERRAIN: { top: "#cbdcbd", side: "#9fb78c", line: "#4f713f" },
  LANDSCAPE: { top: "#93bb64", side: "#6f944f", line: "#365314" },
};

const resolveLayerPalette = (item: Preview3DItem, layer: string) => {
  if (layer !== "UTILITY") {
    return layerPalette[layer] || { top: item.color || "#cbd5e1", side: item.color || "#94a3b8", line: "#f8fafc" };
  }
  const network = `${String(item.meta?.network || "")} ${String(item.meta?.cad_layer || "")} ${item.label}`.toLowerCase();
  if (network.includes("water")) return { top: "#3b82f6", side: "#2563eb", line: "#dbeafe" };
  if (network.includes("sanitary") || network.includes("sewer")) return { top: "#22c55e", side: "#15803d", line: "#dcfce7" };
  if (network.includes("storm") || network.includes("drain")) return { top: "#22d3ee", side: "#0891b2", line: "#cffafe" };
  return layerPalette.UTILITY;
};

const layerSurfaceLift = (layer: string) => {
  if (layer === "SIDEWALK") return 0.28;
  if (layer === "PARKING") return 0.22;
  if (layer === "ROAD") return 0.16;
  if (layer === "LANDSCAPE") return 0.12;
  if (layer === "LOT") return 0.04;
  return 0;
};

const describeConfidence = (value: Preview3DItem["confidence"]) => {
  if (typeof value === "number" && Number.isFinite(value)) return `${Math.round(value * 100)}%`;
  if (typeof value === "string" && value.trim()) return value.replaceAll("_", " ");
  return "review required";
};

const confidenceState = (item: Preview3DItem) => {
  const text = `${item.confidence || ""} ${item.source || ""} ${(item.blockers || []).join(" ")}`.toLowerCase();
  if (item.unsupported || text.includes("blocked")) return "blocked";
  if (text.includes("stale") || text.includes("dirty")) return "stale";
  if (text.includes("low") || text.includes("infer") || text.includes("missing")) return "low";
  if (text.includes("import")) return "imported";
  return "verified";
};

const createTextSprite = (label: string, color = "#0f172a") => {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(255,255,255,0.92)";
    ctx.strokeStyle = "rgba(15,23,42,0.14)";
    ctx.lineWidth = 4;
    ctx.roundRect(12, 28, 488, 68, 22);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = "600 30px ui-sans-serif, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label.slice(0, 34), 256, 63);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(58, 14.5, 1);
  return sprite;
};

const getItemId = (item: Preview3DItem, index: number) =>
  item.id || `${normalizePreview3DItemLayer(item).toLowerCase()}-${item.label.replace(/\W+/g, "-").toLowerCase()}-${index}`;

const normalizePreview3DItemLayer = (item: Preview3DItem) =>
  normalizePreview3DLayer(item.layer, [
    item.label,
    item.entityType,
    item.source,
    item.meta?.cad_layer,
    item.meta?.layer,
    item.meta?.network,
  ]);

const displayHeightForLayer = (item: Preview3DItem, layer: string) => {
  const explicitHeight = Number(item.height);
  const resolvedHeight = Number.isFinite(explicitHeight) && explicitHeight > 0 ? explicitHeight : null;
  if (layer === "ROAD" || layer === "PARKING") return 0.055;
  if (layer === "SIDEWALK") return 0.035;
  if (layer === "LOT") return 0.025;
  if (layer === "CONSTRAINT") return 0.06;
  if (layer === "LANDSCAPE") return 0.08;
  if (layer === "DRAINAGE") return Math.max(1.2, Math.min(Math.abs(resolvedHeight || 3), 12));
  if (layer === "UTILITY") return Math.max(0.22, Math.min(Math.min(item.w, item.h) * 0.03, 0.7));
  if (layer === "STRUCTURE") return Math.max(4, Math.min(resolvedHeight || 12, 300));
  if (layer === "BUILDING") return Math.max(8, Math.min(resolvedHeight || 28, 500));
  return Math.max(0.35, Math.min(resolvedHeight || 1, 16));
};

const surfaceExtrudeDepth = (heightFt: number, layer: string) => {
  if (layer === "ROAD" || layer === "PARKING" || layer === "LOT" || layer === "SIDEWALK" || layer === "CONSTRAINT" || layer === "LANDSCAPE") {
    return Math.max(0.025, heightFt);
  }
  return Math.max(heightFt, 0.35);
};

const flatPlanOpacity = (layer: string, state: string) => {
  if (layer === "LOT") return 0.018;
  if (layer === "PARKING") return state === "low" ? 0.9 : 0.98;
  if (layer === "ROAD") return state === "low" ? 0.88 : 0.98;
  if (layer === "SIDEWALK") return state === "low" ? 0.78 : 0.92;
  if (layer === "LANDSCAPE") return state === "low" ? 0.42 : 0.58;
  if (state === "low") return 0.5;
  if (state === "imported") return 0.58;
  if (state === "stale") return 0.5;
  return 0.62;
};

const isDenseConceptLot = (item: Preview3DItem) =>
  Boolean(
    item.meta?.dense_subdivision_cad_plan ||
      item.meta?.urbanization_campus_plan ||
      item.meta?.subdivision_cad_recreation ||
      item.meta?.cad_reference_recreation,
  );

function stableUnitValue(seed: string, offset = 0) {
  let hash = 2166136261 + offset;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function dedupePlanPoints(points: Array<[number, number]>) {
  return points.filter(([x, y], index) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
    if (index === 0) return true;
    const [prevX, prevY] = points[index - 1];
    return Math.hypot(x - prevX, y - prevY) > 0.01;
  });
}

function scalePlanPoints(points: Array<[number, number]>, scale: number) {
  if (!points.length) return [];
  const center = points.reduce(
    (acc, [x, y]) => ({ x: acc.x + x / points.length, y: acc.y + y / points.length }),
    { x: 0, y: 0 },
  );
  return points.map(([x, y]) => [center.x + (x - center.x) * scale, center.y + (y - center.y) * scale] as [number, number]);
}

function organicRectPoints(item: Preview3DItem, inset = 0) {
  const count = 36;
  const centerX = item.x + item.w / 2;
  const centerY = item.y + item.h / 2;
  const radiusX = Math.max(item.w * (0.5 - inset), 0.5);
  const radiusY = Math.max(item.h * (0.5 - inset), 0.5);
  return Array.from({ length: count }, (_, index) => {
    const angle = (Math.PI * 2 * index) / count;
    const variation = 1 + Math.sin(angle * 3 + 0.7) * 0.028 + Math.sin(angle * 5 - 0.35) * 0.018;
    return [centerX + Math.cos(angle) * radiusX * variation, centerY + Math.sin(angle) * radiusY * variation] as [number, number];
  });
}

function shapeFromPlanPoints(points: Array<[number, number]>, centerX: number, centerY: number) {
  const shape = new THREE.Shape();
  points.forEach(([x, y], index) => {
    const sceneX = x - centerX;
    const sceneY = centerY - y;
    if (index === 0) shape.moveTo(sceneX, sceneY);
    else shape.lineTo(sceneX, sceneY);
  });
  shape.closePath();
  return shape;
}

function corridorSurfaceGeometry(
  rawPoints: Array<[number, number]>,
  widthFt: number,
  elevation: number,
  centerX: number,
  centerY: number,
) {
  const points = dedupePlanPoints(rawPoints);
  if (points.length < 2) return null;
  const halfWidth = Math.max(widthFt / 2, 0.2);
  const pairs = points.map(([x, y], index) => {
    const previous = points[Math.max(0, index - 1)];
    const next = points[Math.min(points.length - 1, index + 1)];
    const prevDx = x - previous[0];
    const prevDy = y - previous[1];
    const nextDx = next[0] - x;
    const nextDy = next[1] - y;
    const prevLength = Math.hypot(prevDx, prevDy) || 1;
    const nextLength = Math.hypot(nextDx, nextDy) || 1;
    const prevNormal = { x: -prevDy / prevLength, y: prevDx / prevLength };
    const nextNormal = { x: -nextDy / nextLength, y: nextDx / nextLength };
    const summed = { x: prevNormal.x + nextNormal.x, y: prevNormal.y + nextNormal.y };
    const summedLength = Math.hypot(summed.x, summed.y);
    const normal = summedLength > 0.001
      ? { x: summed.x / summedLength, y: summed.y / summedLength }
      : index === 0
        ? nextNormal
        : prevNormal;
    const denominator = Math.max(Math.abs(normal.x * nextNormal.x + normal.y * nextNormal.y), 0.32);
    const miter = Math.min(halfWidth / denominator, halfWidth * 2.2);
    return {
      left: [x + normal.x * miter - centerX, elevation, y + normal.y * miter - centerY] as [number, number, number],
      right: [x - normal.x * miter - centerX, elevation, y - normal.y * miter - centerY] as [number, number, number],
    };
  });
  const positions = pairs.flatMap((pair) => [...pair.left, ...pair.right]);
  const indices: number[] = [];
  for (let index = 0; index < pairs.length - 1; index += 1) {
    const left = index * 2;
    const right = left + 1;
    const nextLeft = left + 2;
    const nextRight = left + 3;
    indices.push(left, right, nextLeft, right, nextRight, nextLeft);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function polygonParkingStripeSegments(points: Array<[number, number]>) {
  const clean = dedupePlanPoints(points);
  if (clean.length < 3) return [];
  const bounds = clean.reduce(
    (acc, [x, y]) => ({
      minX: Math.min(acc.minX, x),
      minY: Math.min(acc.minY, y),
      maxX: Math.max(acc.maxX, x),
      maxY: Math.max(acc.maxY, y),
    }),
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );
  const vertical = bounds.maxX - bounds.minX >= bounds.maxY - bounds.minY;
  const min = vertical ? bounds.minX : bounds.minY;
  const max = vertical ? bounds.maxX : bounds.maxY;
  const spacing = Math.max(7.5, Math.min(10, (max - min) / 22));
  const segments: Array<[[number, number], [number, number]]> = [];
  for (let value = min + spacing; value < max - spacing * 0.45; value += spacing) {
    const intersections: number[] = [];
    clean.forEach(([x1, y1], index) => {
      const [x2, y2] = clean[(index + 1) % clean.length];
      const a1 = vertical ? x1 : y1;
      const a2 = vertical ? x2 : y2;
      const b1 = vertical ? y1 : x1;
      const b2 = vertical ? y2 : x2;
      if (Math.abs(a2 - a1) < 0.0001) return;
      const low = Math.min(a1, a2);
      const high = Math.max(a1, a2);
      if (value < low || value >= high) return;
      const t = (value - a1) / (a2 - a1);
      intersections.push(b1 + (b2 - b1) * t);
    });
    intersections.sort((a, b) => a - b);
    for (let index = 0; index + 1 < intersections.length; index += 2) {
      const start = intersections[index];
      const end = intersections[index + 1];
      if (end - start < 3) continue;
      const inset = Math.min(2.2, (end - start) * 0.08);
      segments.push(
        vertical
          ? [[value, start + inset], [value, end - inset]]
          : [[start + inset, value], [end - inset, value]],
      );
    }
  }
  return segments.slice(0, 48);
}

export default function Preview3DCanvas({
  items,
  fullscreen = false,
  previewQuality = "standard",
  selectedItemId,
  hasTerrainSource = false,
  hasGradingSurface = false,
  onSelectItem,
  onOpenFullscreen,
}: Preview3DCanvasProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const pickablesRef = useRef<THREE.Object3D[]>([]);
  const selectedRef = useRef<string | null | undefined>(selectedItemId);
  const [picked, setPicked] = useState<PickedObject | null>(null);
  const objectChips = useMemo(
    () => {
      const hasReviewContourSurface = items.some(
        (item) => item.terrainSample && /review contour/i.test(String(item.source || "")),
      );
      return items
        .filter((item) => {
          if (item.terrainSample) return false;
          if (hasReviewContourSurface && /grading surface missing/i.test(String(item.label || ""))) return false;
          return true;
        })
        .map((item, index) => ({
          id: getItemId(item, index),
          label: item.label,
          layer: normalizePreview3DItemLayer(item),
          confidence: describeConfidence(item.confidence),
          blockers: item.blockers || [],
          source: item.source || "preview object",
          geometrySignature: canonicalPreview3DFootprintSignature(item),
          heightFt: normalizePreview3DItemLayer(item) === "BUILDING" || normalizePreview3DItemLayer(item) === "STRUCTURE"
            ? displayHeightForLayer(item, normalizePreview3DItemLayer(item))
            : null,
          priority:
            getItemId(item, index) === selectedItemId
              ? -2
              : item.meta?.hero_massing
              ? -1
              : normalizePreview3DItemLayer(item) === "BUILDING"
              ? 0
              : normalizePreview3DItemLayer(item) === "STRUCTURE"
                ? 1
                : normalizePreview3DItemLayer(item) === "DRAINAGE"
                  ? 2
                : normalizePreview3DItemLayer(item) === "LANDSCAPE"
                  ? 3
                : normalizePreview3DItemLayer(item) === "ROAD"
                    ? 4
                    : normalizePreview3DItemLayer(item) === "PARKING"
                      ? 5
                      : normalizePreview3DItemLayer(item) === "UTILITY"
                        ? 6
                        : 9,
        }))
        .filter((item) => item.layer !== "TERRAIN")
        .sort((a, b) => a.priority - b.priority || a.label.localeCompare(b.label));
    },
    [items, selectedItemId],
  );
  const massingStats = useMemo(() => {
    const visibleObjects = items.filter((item) => !item.terrainSample);
    const vertical = visibleObjects.filter((item) => {
      const layer = normalizePreview3DItemLayer(item);
      return layer === "BUILDING" || layer === "STRUCTURE" || (layer === "LOT" && isDenseConceptLot(item));
    }).length;
    const buildingDetail = visibleObjects.reduce((count, item) => {
      const layer = normalizePreview3DItemLayer(item);
      if (layer === "BUILDING") return count + 1;
      if (layer === "LOT" && isDenseConceptLot(item) && Math.min(item.w, item.h) >= 18) return count + 1;
      return count;
    }, 0);
    const civilFlat = visibleObjects.filter((item) => {
      const layer = normalizePreview3DItemLayer(item);
      return ["ROAD", "PARKING", "LOT", "SIDEWALK", "UTILITY", "DRAINAGE"].includes(layer);
    }).length;
    return { vertical, civilFlat, buildingDetail };
  }, [items]);

  const selectObject = (object: (typeof objectChips)[number]) => {
    onSelectItem?.(object.id);
    setPicked({
      id: object.id,
      label: object.label,
      layer: object.layer,
      confidence: object.confidence,
      blockers: object.blockers,
      source: object.source,
      heightFt: object.heightFt,
      x: 22,
      y: 118,
    });
  };

  const modelBounds = useMemo(() => {
    if (!items.length) return { minX: 0, minY: 0, maxX: 240, maxY: 160, spanX: 240, spanY: 160 };
    const siteExtent = items.find(
      (item) => normalizePreview3DItemLayer(item) === "TERRAIN" && !item.terrainSample && item.w > 0 && item.h > 0,
    );
    const framingItems = siteExtent ? [siteExtent] : items.filter((item) => !item.terrainSample);
    const minX = Math.min(...framingItems.map((item) => item.x));
    const minY = Math.min(...framingItems.map((item) => item.y));
    const maxX = Math.max(...framingItems.map((item) => item.x + item.w));
    const maxY = Math.max(...framingItems.map((item) => item.y + item.h));
    return {
      minX,
      minY,
      maxX,
      maxY,
      spanX: Math.max(maxX - minX, 1),
      spanY: Math.max(maxY - minY, 1),
    };
  }, [items]);

  const terrainState = useMemo(() => {
    const sourceSamples = items.filter(
      (item) => item.terrainSample && typeof item.z === "number" && Number.isFinite(item.z),
    );
    const terrainZValues = sourceSamples.map((item) => Number(item.z));
    const terrainZRange = terrainZValues.length ? Math.max(...terrainZValues) - Math.min(...terrainZValues) : 0;
    const hasReviewContourSamples = sourceSamples.some((item) => /review contour/i.test(String(item.source || "")));
    const hasSourceDemSamples = sourceSamples.some((item) => item.meta?.source_surface_ready === true);
    if (!sourceSamples.length) {
      if (hasTerrainSource) {
        return {
          label: hasGradingSurface
            ? "Grading surface present - preview elevations unavailable"
            : "Terrain context found - surface mesh not generated",
          detail: hasGradingSurface
            ? "The grading result does not include preview elevation samples, so the 3D ground stays flat."
            : "Elevation or terrain context exists, but no triangulated or contour-derived surface is available for 3D yet.",
          mode: "flat-source" as const,
        };
      }
      return {
        label: "Flat site fallback - terrain source missing",
        detail: "No preview elevation samples were supplied; no terrain is inferred.",
        mode: "fallback" as const,
      };
    }
    if (hasReviewContourSamples && terrainZRange >= 0.5) {
      return {
        label: "Review contour surface - not survey control",
        detail: `${sourceSamples.length} contour-derived visual sample(s); use for review visualization only.`,
        mode: "terrain" as const,
      };
    }
    if (hasSourceDemSamples && terrainZRange >= 0.25) {
      const firstSourceSample = sourceSamples.find((item) => item.meta?.source_surface_ready === true);
      const resolution = String(firstSourceSample?.meta?.horizontal_resolution || "public DEM resolution");
      return {
        label: "Public DEM terrain surface - not survey control",
        detail: `${sourceSamples.length} source elevation sample(s); ${resolution}.`,
        mode: "terrain" as const,
      };
    }
    if (hasSourceDemSamples) {
      return {
        label: "Public DEM loaded - sampled surface is nearly flat",
        detail: `${sourceSamples.length} source elevation sample(s); no vertical shape was invented.`,
        mode: "flat-source" as const,
      };
    }
    if (!hasTerrainSource || !hasGradingSurface || terrainZRange < 0.5) {
      return {
        label: "Terrain source loaded - flat sampled surface",
        detail: `${sourceSamples.length} supplied elevation sample(s); vertical variation is not enough for a mesh.`,
        mode: "flat-source" as const,
      };
    }
    return {
      label: "Terrain mesh from preview elevations",
      detail: `${sourceSamples.length} supplied preview elevation sample(s) visible.`,
      mode: "terrain" as const,
    };
  }, [hasGradingSurface, hasTerrainSource, items]);

  useEffect(() => {
    selectedRef.current = selectedItemId;
    const pickables = pickablesRef.current;
    pickables.forEach((object) => {
      const selected = object.userData.itemId === selectedItemId;
      object.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (!("material" in mesh)) return;
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        materials.forEach((material) => {
          if (material instanceof THREE.MeshStandardMaterial) {
            material.emissive.set(selected ? "#f59e0b" : "#000000");
            material.emissiveIntensity = selected ? 0.22 : 0;
          }
        });
      });
    });
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  }, [selectedItemId]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    mount.innerHTML = "";

    const width = Math.max(mount.clientWidth, 320);
    const height = Math.max(mount.clientHeight, 320);
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(previewQuality === "high" ? "#dde4e9" : "#e5eaed");

    const renderer = new THREE.WebGLRenderer({ antialias: previewQuality === "high", preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, previewQuality === "high" ? 2 : 1.35));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = previewQuality === "high";
    renderer.shadowMap.type = THREE.PCFShadowMap;
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 5000);
    const maxSpan = Math.max(modelBounds.spanX, modelBounds.spanY);
    const maxObjectHeight = Math.max(
      12,
      ...items
        .filter((item) => !item.terrainSample)
        .map((item) => displayHeightForLayer(item, normalizePreview3DItemLayer(item))),
    );
    camera.position.set(maxSpan * 0.78, Math.max(maxSpan * 0.66, maxObjectHeight * 3.1), maxSpan * 1.03);
    camera.zoom = previewQuality === "high" ? 1.1 : 1.06;
    camera.updateProjectionMatrix();
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.minDistance = Math.max(maxSpan * 0.14, 25);
    controls.maxDistance = Math.max(maxSpan * 2.6, 300);
    controls.target.set(0, Math.min(maxObjectHeight * 0.18, maxSpan * 0.08), 0);
    controls.update();
    controlsRef.current = controls;

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = previewQuality === "high" ? 1 : 0.98;

    const ambient = new THREE.HemisphereLight("#f8fbff", "#7f9182", previewQuality === "high" ? 0.98 : 1.08);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight("#fff7ed", previewQuality === "high" ? 2.05 : 1.5);
    sun.position.set(maxSpan * 0.42, maxSpan * 0.95, maxSpan * 0.52);
    sun.castShadow = previewQuality === "high";
    sun.shadow.mapSize.width = previewQuality === "high" ? 2048 : 1024;
    sun.shadow.mapSize.height = previewQuality === "high" ? 2048 : 1024;
    sun.shadow.camera.left = -maxSpan * 0.75;
    sun.shadow.camera.right = maxSpan * 0.75;
    sun.shadow.camera.top = maxSpan * 0.75;
    sun.shadow.camera.bottom = -maxSpan * 0.75;
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = maxSpan * 3;
    sun.shadow.bias = -0.0003;
    scene.add(sun);

    const root = new THREE.Group();
    root.rotation.x = 0;
    scene.add(root);

    const centerX = modelBounds.minX + modelBounds.spanX / 2;
    const centerY = modelBounds.minY + modelBounds.spanY / 2;
    const terrainSamples = items
      .filter((item) => item.terrainSample && typeof item.z === "number" && Number.isFinite(item.z))
      .map((item) => ({
        x: item.x + item.w / 2,
        y: item.y + item.h / 2,
        z: Number(item.z),
      }));
    const terrainElevationAt = (x: number, y: number) => {
      if (terrainState.mode !== "terrain" || !terrainSamples.length) return 0;
      const exactSample = terrainSamples.find((sample) => Math.hypot(sample.x - x, sample.y - y) < 0.01);
      if (exactSample) return exactSample.z;
      let weighted = 0;
      let weight = 0;
      terrainSamples.forEach((sample) => {
        const distance = Math.hypot(sample.x - x, sample.y - y);
        const nextWeight = 1 / Math.max(distance * distance, 1);
        weighted += sample.z * nextWeight;
        weight += nextWeight;
      });
      return weight ? weighted / weight : 0;
    };
    const toScene = (x: number, y: number, z = 0) =>
      new THREE.Vector3(x - centerX, z, y - centerY);
      const addBuildingDetailCues = (
      object: THREE.Group,
      item: Preview3DItem,
      baseY: number,
      heightFt: number,
      options: { smallLot?: boolean } = {},
    ) => {
        const width = Math.max(item.w, 1);
      const depth = Math.max(item.h, 1);
      const topY = baseY + heightFt;
      const minDim = Math.min(width, depth);
      const maxDim = Math.max(width, depth);
      const facadeColor = options.smallLot ? "#64748b" : "#334155";
      const lineOpacity = options.smallLot ? 0.2 : 0.32;
      const facadeLineMaterial = new THREE.LineBasicMaterial({
        color: facadeColor,
        transparent: true,
        opacity: lineOpacity,
      });
      const addLine = (from: THREE.Vector3, to: THREE.Vector3) => {
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, to]), facadeLineMaterial);
        line.name = "civil-3d-building-facade-cue";
        object.add(line);
      };

      const plinth = new THREE.Mesh(
        new THREE.BoxGeometry(width * 1.025, 0.18, depth * 1.025),
        new THREE.MeshStandardMaterial({
          color: "#cbd5e1",
          roughness: 0.88,
          transparent: true,
          opacity: options.smallLot ? 0.24 : 0.38,
        }),
      );
      plinth.position.copy(toScene(item.x + width / 2, item.y + depth / 2, baseY + 0.09));
      plinth.userData = object.userData;
      plinth.name = "civil-3d-building-plinth";
      object.add(plinth);

      if (!options.smallLot) {
        const parapetHeight = Math.max(0.42, Math.min(heightFt * 0.035, 2.2));
        const parapetMaterial = new THREE.MeshStandardMaterial({
          color: "#e2e8f0",
          roughness: 0.82,
          metalness: 0.01,
        });
        [
          { x: item.x + width / 2, y: item.y + depth * 0.03, w: width * 0.98, d: Math.max(depth * 0.035, 0.8) },
          { x: item.x + width / 2, y: item.y + depth * 0.97, w: width * 0.98, d: Math.max(depth * 0.035, 0.8) },
          { x: item.x + width * 0.03, y: item.y + depth / 2, w: Math.max(width * 0.035, 0.8), d: depth * 0.98 },
          { x: item.x + width * 0.97, y: item.y + depth / 2, w: Math.max(width * 0.035, 0.8), d: depth * 0.98 },
        ].forEach((rail, railIndex) => {
          const parapet = new THREE.Mesh(new THREE.BoxGeometry(rail.w, parapetHeight, rail.d), parapetMaterial);
          parapet.position.copy(toScene(rail.x, rail.y, topY + parapetHeight / 2 + 0.05));
          parapet.userData = object.userData;
          parapet.name = `civil-3d-building-parapet-${railIndex + 1}`;
          object.add(parapet);
        });
      }

      const bandCount = options.smallLot ? 1 : Math.max(2, Math.min(5, Math.floor(heightFt / 18)));
      for (let band = 1; band <= bandCount; band += 1) {
        const z = baseY + (heightFt * band) / (bandCount + 1);
        addLine(toScene(item.x + width * 0.04, item.y + depth * 0.01, z), toScene(item.x + width * 0.96, item.y + depth * 0.01, z));
        addLine(toScene(item.x + width * 0.99, item.y + depth * 0.04, z), toScene(item.x + width * 0.99, item.y + depth * 0.96, z));
        if (!options.smallLot && maxDim >= 42) {
          addLine(toScene(item.x + width * 0.04, item.y + depth * 0.99, z), toScene(item.x + width * 0.96, item.y + depth * 0.99, z));
        }
      }

      const bayCount = options.smallLot ? 2 : Math.max(3, Math.min(10, Math.floor(width / 18)));
      for (let bay = 1; bay < bayCount; bay += 1) {
        const x = item.x + (width * bay) / bayCount;
        addLine(toScene(x, item.y + depth * 0.01, baseY + heightFt * 0.18), toScene(x, item.y + depth * 0.01, topY - heightFt * 0.12));
      }
      const sideBayCount = options.smallLot ? 1 : Math.max(2, Math.min(8, Math.floor(depth / 18)));
      for (let bay = 1; bay < sideBayCount; bay += 1) {
        const y = item.y + (depth * bay) / sideBayCount;
        addLine(toScene(item.x + width * 0.99, y, baseY + heightFt * 0.18), toScene(item.x + width * 0.99, y, topY - heightFt * 0.12));
      }

      if (!options.smallLot && minDim >= 20) {
        const canopyMaterial = new THREE.MeshStandardMaterial({ color: "#cbd5e1", roughness: 0.74, metalness: 0.02 });
        const canopy = new THREE.Mesh(
          new THREE.BoxGeometry(Math.max(width * 0.22, 5), 0.32, Math.max(depth * 0.055, 1.6)),
          canopyMaterial,
        );
        canopy.position.copy(toScene(item.x + width / 2, item.y + depth + Math.max(depth * 0.012, 0.6), baseY + Math.max(heightFt * 0.16, 5)));
        canopy.userData = object.userData;
        canopy.name = "civil-3d-building-entry-canopy";
        object.add(canopy);
      }
    };

    const terrainGeometry =
      terrainState.mode === "terrain"
        ? new THREE.PlaneGeometry(modelBounds.spanX, modelBounds.spanY, previewQuality === "high" ? 24 : 12, previewQuality === "high" ? 24 : 12)
        : new THREE.PlaneGeometry(modelBounds.spanX, modelBounds.spanY, 1, 1);
    terrainGeometry.rotateX(-Math.PI / 2);
    if (terrainState.mode === "terrain") {
      const positions = terrainGeometry.attributes.position;
      for (let i = 0; i < positions.count; i += 1) {
        const vx = positions.getX(i);
        const vz = positions.getZ(i);
        positions.setY(i, terrainElevationAt(vx + centerX, vz + centerY));
      }
      positions.needsUpdate = true;
      terrainGeometry.computeVertexNormals();
    }
    const terrainMaterial = new THREE.MeshStandardMaterial({
      color: terrainState.mode === "fallback" ? "#cad6cd" : "#bfd2b8",
      roughness: 0.9,
      metalness: 0,
      wireframe: previewQuality === "standard" && terrainState.mode === "terrain",
      transparent: false,
      opacity: 1,
    });
    const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
    terrain.receiveShadow = true;
    root.add(terrain);

    const siteBoundaryPoints = [
      toScene(modelBounds.minX, modelBounds.minY, terrainElevationAt(modelBounds.minX, modelBounds.minY) + 0.12),
      toScene(modelBounds.maxX, modelBounds.minY, terrainElevationAt(modelBounds.maxX, modelBounds.minY) + 0.12),
      toScene(modelBounds.maxX, modelBounds.maxY, terrainElevationAt(modelBounds.maxX, modelBounds.maxY) + 0.12),
      toScene(modelBounds.minX, modelBounds.maxY, terrainElevationAt(modelBounds.minX, modelBounds.maxY) + 0.12),
    ];
    const siteBoundary = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(siteBoundaryPoints),
      new THREE.LineBasicMaterial({ color: "#334155", transparent: true, opacity: 0.48 }),
    );
    siteBoundary.name = "civil-3d-site-boundary";
    root.add(siteBoundary);

    if (previewQuality === "high" && terrainState.mode === "terrain") {
      const terrainLineMaterial = new THREE.LineBasicMaterial({
        color: "#6f8f54",
        transparent: true,
        opacity: 0.24,
      });
      const referenceCount = 7;
      for (let lineIndex = 1; lineIndex < referenceCount; lineIndex += 1) {
        const t = lineIndex / referenceCount;
        const y = modelBounds.minY + modelBounds.spanY * t;
        const wave = Math.sin(t * Math.PI * 2) * modelBounds.spanY * 0.018;
        const points = [
          [modelBounds.minX, y + wave],
          [modelBounds.minX + modelBounds.spanX * 0.25, y - wave * 0.45],
          [modelBounds.minX + modelBounds.spanX * 0.55, y + wave * 0.75],
          [modelBounds.maxX, y - wave],
        ].map(([x, pointY]) =>
          toScene(x, pointY, terrainElevationAt(x, pointY) + 0.1),
        );
        const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.06);
        root.add(
          new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)),
            terrainLineMaterial,
          ),
        );
      }
    }

    const pickables: THREE.Object3D[] = [];
    let visibleLabelCount = 0;
    const maxVisibleLabels = selectedItemId ? 1 : 0;
    items.forEach((item, index) => {
      const layer = normalizePreview3DItemLayer(item);
      if (layer === "TERRAIN") return;
      const id = getItemId(item, index);
      const palette = resolveLayerPalette(item, layer);
      const heightFt = displayHeightForLayer(item, layer);
      const itemOffset = typeof item.z === "number" && Number.isFinite(item.z) ? item.z : 0;
      const terrainBaseY = terrainElevationAt(item.x + item.w / 2, item.y + item.h / 2);
      // Basin depths describe engineering intent, but the review mesh does not
      // cut holes into the terrain. Keep the visible basin surfaces above the
      // terrain instead of burying them and losing the object entirely.
      const baseY = terrainBaseY + (layer === "DRAINAGE" ? Math.max(itemOffset, 0) : itemOffset);
      const state = confidenceState(item);
      const minPlanDimension = Math.min(Math.max(item.w, 0), Math.max(item.h, 0));
      const maxPlanDimension = Math.max(Math.max(item.w, 0), Math.max(item.h, 0));
      const planArea = Math.max(item.w, 0) * Math.max(item.h, 0);
      const isDraftedPlanDetail =
        (item.geometryType === "polyline" || item.geometryType === "polygon") &&
        minPlanDimension > 0 &&
        minPlanDimension < 18 &&
        (layer === "OBJECT" || layer === "PARKING" || layer === "ROAD");
      const isSmallPavementDetail =
        (layer === "PARKING" || layer === "ROAD") &&
        minPlanDimension > 0 &&
        (minPlanDimension < 28 || planArea < 2800 || (maxPlanDimension > 0 && maxPlanDimension / Math.max(minPlanDimension, 1) > 5));
      if (layer === "PARKING" && item.geometryType === "polyline") return;
      if (isDraftedPlanDetail && !item.corridorWidth) return;
      if (isSmallPavementDetail && !item.corridorWidth) return;
      const object = new THREE.Group();
      object.userData = {
        itemId: id,
        label: item.label,
        layer,
        confidence: describeConfidence(item.confidence),
        blockers: item.blockers || [],
        source: item.source || (layer === "UTILITY" ? "utility evidence only where supplied" : "preview object"),
        linkedObjectId: item.linkedObjectId,
        sourceEntityId: item.sourceEntityId,
        heightFt: layer === "BUILDING" || layer === "STRUCTURE" ? heightFt : null,
      };

      const isFlatPlanLayer = layer === "ROAD" || layer === "PARKING" || layer === "LOT" || layer === "SIDEWALK" || layer === "LANDSCAPE";
      const preserveSolidMassing = layer === "BUILDING" || layer === "STRUCTURE";
      const visualLift = layerSurfaceLift(layer);
      const cadMaterial = new THREE.MeshStandardMaterial({
        color: layer === "LOT" ? palette.top : state === "blocked" ? "#dc2626" : item.unsupported ? "#f59e0b" : palette.top,
        roughness: layer === "ROAD" || layer === "PARKING" ? 0.86 : layer === "DRAINAGE" ? 0.42 : 0.72,
        transparent: isFlatPlanLayer || item.unsupported || layer === "CONSTRAINT" || (!preserveSolidMassing && (state === "low" || state === "imported" || state === "stale")),
        depthWrite: !isFlatPlanLayer,
        polygonOffset: isFlatPlanLayer,
        polygonOffsetFactor: isFlatPlanLayer ? -1 : 0,
        polygonOffsetUnits: isFlatPlanLayer ? -1 : 0,
        opacity: isFlatPlanLayer
          ? flatPlanOpacity(layer, state)
          : item.unsupported
          ? 0.62
          : preserveSolidMassing
            ? 1
          : state === "low"
            ? layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK"
              ? 0.82
              : 0.9
            : state === "imported"
              ? 0.88
                : state === "stale"
                  ? 0.82
                  : layer === "CONSTRAINT"
                    ? 0.34
                  : 1,
      });
      let renderedCadGeometry = false;
      const roofProfile = String(item.meta?.roof_profile || "").toLowerCase();
      const isTreeSymbol = String(item.meta?.landscape_symbol || "").toLowerCase() === "tree";
      const addExactEdges = (mesh: THREE.Mesh, color = palette.line, opacity = 0.62) => {
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(mesh.geometry),
          new THREE.LineBasicMaterial({ color, transparent: true, opacity }),
        );
        edges.position.copy(mesh.position);
        edges.rotation.copy(mesh.rotation);
        edges.scale.copy(mesh.scale);
        object.add(edges);
      };
      const simplifyLowConfidencePlanGeometry =
        state === "low" && (layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK");

      if (isTreeSymbol && layer === "LANDSCAPE") {
        const trunk = new THREE.Mesh(
          new THREE.CylinderGeometry(0.34, 0.42, 4.2, 8),
          new THREE.MeshStandardMaterial({ color: "#7c4a23", roughness: 0.82 }),
        );
        trunk.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 2.1));
        trunk.userData = object.userData;
        object.add(trunk);
        const crown = new THREE.Mesh(
          new THREE.SphereGeometry(Math.max(Math.min(item.w, item.h) * 0.34, 2.8), 14, 10),
          new THREE.MeshStandardMaterial({ color: "#4d7c0f", roughness: 0.9 }),
        );
        crown.scale.set(1.08, 0.82, 1.08);
        crown.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 6.0));
        crown.userData = object.userData;
        object.add(crown);
        renderedCadGeometry = true;
      } else if (item.unsupported) {
        const placeholder = new THREE.Mesh(
          new THREE.BoxGeometry(Math.max(item.w, 1), 0.7, Math.max(item.h, 1)),
          cadMaterial,
        );
        placeholder.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 0.5));
        placeholder.userData = object.userData;
        object.add(placeholder);
        const outline = new THREE.LineSegments(
          new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w, 1), 0.82, Math.max(item.h, 1))),
          new THREE.LineBasicMaterial({ color: "#92400e" }),
        );
        outline.position.copy(placeholder.position);
        object.add(outline);
        renderedCadGeometry = true;
      } else if (
        !simplifyLowConfidencePlanGeometry &&
        (item.geometryType === "polyline" || item.geometryType === "polygon") &&
        Array.isArray(item.geometry) &&
        item.geometry.length >= 2
      ) {
        const planPoints = dedupePlanPoints(item.geometry);
        const points = planPoints.map(([x, y]) => toScene(x, y, baseY + 0.55));
        if (item.geometryType === "polygon" && points.length >= 3) {
          const displayDepth = surfaceExtrudeDepth(heightFt, layer);
          if (layer === "DRAINAGE") {
            const shelfPoints = scalePlanPoints(planPoints, 0.78);
            const waterPoints = scalePlanPoints(planPoints, 0.54);
            const outerGeometry = new THREE.ShapeGeometry(shapeFromPlanPoints(planPoints, centerX, centerY));
            const shelfGeometry = new THREE.ShapeGeometry(shapeFromPlanPoints(shelfPoints, centerX, centerY));
            const waterGeometry = new THREE.ShapeGeometry(shapeFromPlanPoints(waterPoints, centerX, centerY));
            [outerGeometry, shelfGeometry, waterGeometry].forEach((geometry) => geometry.rotateX(-Math.PI / 2));
            const outer = new THREE.Mesh(
              outerGeometry,
              new THREE.MeshStandardMaterial({ color: "#759463", roughness: 0.92, transparent: true, opacity: 0.96, side: THREE.DoubleSide }),
            );
            outer.position.y = baseY + 0.32;
            outer.userData = object.userData;
            outer.receiveShadow = true;
            object.add(outer);
            const shelf = new THREE.Mesh(
              shelfGeometry,
              new THREE.MeshStandardMaterial({ color: "#9bc47d", roughness: 0.9, transparent: true, opacity: 0.98, side: THREE.DoubleSide }),
            );
            shelf.position.y = baseY + 0.46;
            shelf.userData = object.userData;
            object.add(shelf);
            const water = new THREE.Mesh(
              waterGeometry,
              new THREE.MeshStandardMaterial({
                color: "#24a9cf",
                roughness: 0.28,
                metalness: 0.02,
                transparent: true,
                opacity: 0.9,
                side: THREE.DoubleSide,
              }),
            );
            water.position.y = baseY + 0.6;
            water.userData = object.userData;
            object.add(water);
            [planPoints, shelfPoints, waterPoints].forEach((ringPoints, ringIndex) => {
              const ring = new THREE.LineLoop(
                new THREE.BufferGeometry().setFromPoints(
                  ringPoints.map(([x, y]) => toScene(x, y, baseY + 0.36 + ringIndex * 0.14)),
                ),
                new THREE.LineBasicMaterial({ color: ringIndex === 2 ? "#0e7490" : "#4d7c5a", transparent: true, opacity: 0.58 }),
              );
              object.add(ring);
            });
          } else {
            const shape = shapeFromPlanPoints(planPoints, centerX, centerY);
            const geometry = new THREE.ExtrudeGeometry(shape, {
              depth: displayDepth,
              bevelEnabled: layer === "BUILDING",
              bevelSegments: layer === "BUILDING" ? 1 : 0,
              bevelSize: layer === "BUILDING" ? Math.min(0.35, displayDepth * 0.015) : 0,
              bevelThickness: layer === "BUILDING" ? Math.min(0.25, displayDepth * 0.01) : 0,
            });
            geometry.rotateX(-Math.PI / 2);
            const mesh = new THREE.Mesh(geometry, cadMaterial);
            mesh.position.y = baseY + visualLift;
            mesh.userData = object.userData;
            mesh.castShadow = previewQuality === "high" && layer === "BUILDING";
            mesh.receiveShadow = layer !== "PARKING" && layer !== "ROAD" && layer !== "SIDEWALK";
            object.add(mesh);
            if (layer === "LOT") {
              addExactEdges(mesh, palette.line, 0.24);
            } else if (layer !== "PARKING" && layer !== "ROAD" && layer !== "SIDEWALK" && layer !== "LANDSCAPE") {
              addExactEdges(mesh, state === "blocked" ? "#fecaca" : palette.line, state === "low" ? 0.34 : 0.48);
            }
            if (layer === "BUILDING" && previewQuality === "high") {
              const floorCount = Math.max(1, Math.min(30, Math.round(displayDepth / 12)));
              for (let floor = 1; floor < floorCount; floor += 1) {
                const band = new THREE.LineLoop(
                  new THREE.BufferGeometry().setFromPoints(
                    planPoints.map(([x, y]) => toScene(x, y, baseY + (displayDepth * floor) / floorCount)),
                  ),
                  new THREE.LineBasicMaterial({ color: "#475569", transparent: true, opacity: 0.22 }),
                );
                object.add(band);
              }
              const roofLine = new THREE.LineLoop(
                new THREE.BufferGeometry().setFromPoints(
                  scalePlanPoints(planPoints, 0.94).map(([x, y]) => toScene(x, y, baseY + displayDepth + 0.22)),
                ),
                new THREE.LineBasicMaterial({ color: "#475569", transparent: true, opacity: 0.42 }),
              );
              object.add(roofLine);
            }
            if (layer === "BUILDING") {
              const roofMaterial = new THREE.MeshStandardMaterial({
                color: roofProfile === "tower" ? "#111827" : roofProfile === "dome" ? "#6b7280" : "#d1d5db",
                roughness: 0.78,
                metalness: roofProfile === "dome" ? 0.03 : 0,
              });
              if (roofProfile === "dome") {
                const dome = new THREE.Mesh(
                  new THREE.SphereGeometry(Math.max(Math.min(item.w, item.h) * 0.36, 4), 32, 12, 0, Math.PI * 2, 0, Math.PI / 2),
                  roofMaterial,
                );
                dome.scale.set(1.28, 0.56, 1);
                dome.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + displayDepth + 0.12));
                dome.userData = object.userData;
                object.add(dome);
              } else if (roofProfile === "gable") {
                const roof = new THREE.Mesh(
                  new THREE.ConeGeometry(
                    Math.max(Math.min(item.w, item.h) * 0.52, 4),
                    Math.max(Math.min(item.w, item.h) * 0.22, 2.2),
                    4,
                  ),
                  roofMaterial,
                );
                roof.rotation.y = Math.PI / 4;
                roof.scale.set(Math.max(item.w / Math.max(item.h, 1), 0.8), 0.75, 1);
                roof.position.copy(
                  toScene(
                    item.x + item.w / 2,
                    item.y + item.h / 2,
                    baseY + displayDepth + Math.max(Math.min(item.w, item.h) * 0.09, 1.2),
                  ),
                );
                roof.userData = object.userData;
                object.add(roof);
              } else if (roofProfile === "tower") {
                const roof = new THREE.Mesh(
                  new THREE.ShapeGeometry(shapeFromPlanPoints(scalePlanPoints(planPoints, 0.96), centerX, centerY)),
                  roofMaterial,
                );
                roof.geometry.rotateX(-Math.PI / 2);
                roof.position.y = baseY + displayDepth + 0.14;
                roof.userData = object.userData;
                object.add(roof);
                const spire = new THREE.Mesh(
                  new THREE.ConeGeometry(Math.max(Math.min(item.w, item.h) * 0.12, 1.2), Math.max(displayDepth * 0.34, 8), 12),
                  new THREE.MeshStandardMaterial({ color: "#020617", roughness: 0.5 }),
                );
                spire.position.copy(
                  toScene(
                    item.x + item.w / 2,
                    item.y + item.h / 2,
                    baseY + displayDepth + Math.max(displayDepth * 0.18, 4),
                  ),
                );
                spire.userData = object.userData;
                object.add(spire);
              }
              if (previewQuality === "high") addBuildingDetailCues(object, item, baseY, displayDepth);
            }
          }
          if (layer === "PARKING" && item.source !== "fallback" && Math.max(item.w, item.h) >= 42 && Math.min(item.w, item.h) >= 32) {
            const stripeMaterial = new THREE.LineBasicMaterial({ color: "#f8fafc", transparent: true, opacity: 0.34 });
            const stripeSegments = polygonParkingStripeSegments(planPoints);
            stripeSegments.forEach(([start, end]) => {
              const line = new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                  toScene(start[0], start[1], baseY + visualLift + displayDepth + 0.06),
                  toScene(end[0], end[1], baseY + visualLift + displayDepth + 0.06),
                ]),
                stripeMaterial,
              );
              object.add(line);
            });
          }
        } else if (layer === "ROAD" || layer === "SIDEWALK") {
          const corridorWidth = Math.max(
            layer === "ROAD" ? 16 : 4,
            Math.min(Number(item.corridorWidth ?? (layer === "ROAD" ? 28 : 6)), layer === "ROAD" ? 42 : 12),
          );
          const slabDepth = surfaceExtrudeDepth(heightFt, layer);
          const slabMaterial = new THREE.MeshStandardMaterial({
            color: palette.top,
            roughness: layer === "ROAD" ? 0.9 : 0.82,
            metalness: 0.01,
          });
          const lineMaterial = new THREE.LineDashedMaterial({
            color: layer === "ROAD" ? "#f8fafc" : palette.line,
            transparent: true,
            opacity: layer === "ROAD" ? 0.62 : 0.42,
            dashSize: layer === "ROAD" ? 8 : 2,
            gapSize: layer === "ROAD" ? 6 : 2,
          });
          const corridorGeometry = corridorSurfaceGeometry(
            planPoints,
            corridorWidth,
            baseY + visualLift + slabDepth + 0.05,
            centerX,
            centerY,
          );
          if (corridorGeometry) {
            const corridor = new THREE.Mesh(corridorGeometry, slabMaterial);
            corridor.userData = object.userData;
            corridor.receiveShadow = true;
            object.add(corridor);
            addExactEdges(corridor, layer === "ROAD" ? "#475569" : palette.line, layer === "ROAD" ? 0.34 : 0.42);
          }
          if (layer === "ROAD") {
            const centerline = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints(
                planPoints.map(([x, y]) => toScene(x, y, baseY + visualLift + slabDepth + 0.15)),
              ),
              lineMaterial,
            );
            centerline.computeLineDistances();
            object.add(centerline);
          }
        } else {
          if (layer === "UTILITY") {
            const utilityPoints = item.geometry.map(([x, y]) => toScene(x, y, baseY + 0.18));
            const utilityLine = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints(utilityPoints),
              new THREE.LineBasicMaterial({
                color: palette.side,
                transparent: true,
                opacity: previewQuality === "high" ? 0.78 : 0.62,
              }),
            );
            utilityLine.userData = object.userData;
            object.add(utilityLine);
            if (previewQuality === "high") {
              utilityPoints.forEach((point, pointIndex) => {
                const node = new THREE.Mesh(
                  new THREE.SphereGeometry(pointIndex === 0 || pointIndex === utilityPoints.length - 1 ? 0.42 : 0.28, 10, 8),
                  new THREE.MeshStandardMaterial({ color: palette.side, roughness: 0.72, transparent: true, opacity: 0.82 }),
                );
                node.position.copy(point);
                node.userData = object.userData;
                object.add(node);
              });
            }
          } else {
            const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.01);
            const tubeRadius =
              layer === "ROAD"
                ? Math.max(4, Math.min(Number(item.corridorWidth ?? 28) / 2, 18))
                : layer === "SIDEWALK"
                  ? Math.max(1.8, Math.min(Number(item.corridorWidth ?? 6) / 2, 6))
                  : Math.max(Math.min(item.w, item.h) * 0.012, 0.22);
            const tube = new THREE.Mesh(
              new THREE.TubeGeometry(curve, Math.max(points.length * 10, 10), tubeRadius, 8, false),
              cadMaterial,
            );
            tube.userData = object.userData;
            object.add(tube);
          }
          if (layer === "ROAD") {
            const centerline = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints(points.map((point) => point.clone().add(new THREE.Vector3(0, 0.12, 0)))),
              new THREE.LineBasicMaterial({ color: "#f8fafc", transparent: true, opacity: 0.72 }),
            );
            object.add(centerline);
          }
        }
        renderedCadGeometry = true;
      } else if (item.geometryType === "circle" && typeof item.radius === "number" && item.radius > 0) {
        const circle = new THREE.Mesh(
          new THREE.CylinderGeometry(item.radius, item.radius, Math.max(heightFt, 0.35), 48),
          cadMaterial,
        );
        circle.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + Math.max(heightFt, 0.35) / 2));
        circle.userData = object.userData;
        object.add(circle);
        renderedCadGeometry = true;
      } else if (item.geometryType === "point" && item.entityType) {
        const marker = new THREE.Mesh(
          new THREE.SphereGeometry(Math.max(Math.min(item.w, item.h) * 0.18, 0.75), 16, 12),
          cadMaterial,
        );
        marker.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 1.25));
        marker.userData = object.userData;
        object.add(marker);
        renderedCadGeometry = true;
      }

      if (renderedCadGeometry) {
        const showReviewRing =
          selectedItemId === id || item.unsupported || state === "blocked" || (state === "stale" && layer !== "ROAD" && layer !== "PARKING");
        if (showReviewRing) {
          const reviewRing = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w, 1), 0.08, Math.max(item.h, 1))),
            new THREE.LineBasicMaterial({ color: state === "blocked" ? "#dc2626" : "#f59e0b", transparent: true, opacity: 0.28 }),
          );
          reviewRing.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + Math.max(heightFt, 0.35) + 0.08));
          object.add(reviewRing);
        }
      } else if (layer === "DRAINAGE") {
        const outerPoints = organicRectPoints(item, 0.01);
        const shelfPoints = scalePlanPoints(outerPoints, 0.76);
        const waterPoints = scalePlanPoints(outerPoints, 0.52);
        const layers = [
          {
            points: outerPoints,
            y: baseY + 0.32,
            material: new THREE.MeshStandardMaterial({ color: "#759463", roughness: 0.92, side: THREE.DoubleSide }),
          },
          {
            points: shelfPoints,
            y: baseY + 0.46,
            material: new THREE.MeshStandardMaterial({ color: "#9bc47d", roughness: 0.9, side: THREE.DoubleSide }),
          },
          {
            points: waterPoints,
            y: baseY + 0.6,
            material: new THREE.MeshStandardMaterial({ color: "#24a9cf", roughness: 0.28, transparent: true, opacity: 0.9, side: THREE.DoubleSide }),
          },
        ];
        layers.forEach((basinLayer, layerIndex) => {
          const geometry = new THREE.ShapeGeometry(shapeFromPlanPoints(basinLayer.points, centerX, centerY));
          geometry.rotateX(-Math.PI / 2);
          const surface = new THREE.Mesh(geometry, basinLayer.material);
          surface.position.y = basinLayer.y;
          surface.userData = object.userData;
          surface.receiveShadow = true;
          object.add(surface);
          const rim = new THREE.LineLoop(
            new THREE.BufferGeometry().setFromPoints(
              basinLayer.points.map(([x, y]) => toScene(x, y, basinLayer.y + 0.04)),
            ),
            new THREE.LineBasicMaterial({ color: layerIndex === 2 ? "#0e7490" : "#4d7c5a", transparent: true, opacity: 0.62 }),
          );
          object.add(rim);
        });
      } else if (layer === "UTILITY") {
        const horizontal = item.w >= item.h;
        const geometry = new THREE.BoxGeometry(
          Math.max(horizontal ? item.w : 1.15, 1.15),
          0.08,
          Math.max(horizontal ? 1.15 : item.h, 1.15),
        );
        const utility = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({
            color: palette.side,
            roughness: 0.72,
            metalness: 0,
            transparent: true,
            opacity: previewQuality === "high" ? 0.76 : 0.58,
          }),
        );
        utility.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 0.12));
        utility.userData = object.userData;
        object.add(utility);
      } else if (layer === "CONSTRAINT") {
        const geometry = new THREE.BoxGeometry(Math.max(item.w, 1), 0.35, Math.max(item.h, 1));
        const material = new THREE.MeshStandardMaterial({
          color: palette.top,
          roughness: 0.7,
          transparent: true,
          opacity: 0.42,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 0.22));
        mesh.userData = object.userData;
        object.add(mesh);

        const outline = new THREE.LineSegments(
          new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w, 1), 0.5, Math.max(item.h, 1))),
          new THREE.LineBasicMaterial({ color: palette.line }),
        );
        outline.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + 0.5));
        object.add(outline);
      } else {
        const geometry = new THREE.BoxGeometry(Math.max(item.w, 1), heightFt, Math.max(item.h, 1));
        const flatPlanSurface = layer === "ROAD" || layer === "PARKING" || layer === "LOT" || layer === "SIDEWALK";
        const material = flatPlanSurface
          ? new THREE.MeshBasicMaterial({
              color: palette.top,
              transparent: true,
              depthWrite: false,
              polygonOffset: true,
              polygonOffsetFactor: -1,
              polygonOffsetUnits: -1,
              opacity: flatPlanOpacity(layer, state),
            })
          : new THREE.MeshStandardMaterial({
              color: layer === "OBJECT" && item.color ? item.color : palette.top,
              roughness: 0.58,
              metalness: 0.02,
            });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = previewQuality === "high" && layer === "BUILDING";
        mesh.receiveShadow = layer !== "ROAD" && layer !== "PARKING" && layer !== "SIDEWALK";
        mesh.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + visualLift + heightFt / 2));
        mesh.userData = object.userData;
        object.add(mesh);

        if (layer === "BUILDING") {
          const roofMaterial = new THREE.MeshStandardMaterial({
            color: roofProfile === "tower" ? "#111827" : roofProfile === "dome" ? "#6b7280" : "#d1d5db",
            roughness: 0.78,
            metalness: roofProfile === "dome" ? 0.03 : 0,
          });
          if (roofProfile === "dome") {
            const dome = new THREE.Mesh(
              new THREE.SphereGeometry(Math.max(Math.min(item.w, item.h) * 0.36, 4), 32, 12, 0, Math.PI * 2, 0, Math.PI / 2),
              roofMaterial,
            );
            dome.scale.set(1.28, 0.56, 1.0);
            dome.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 0.12));
            object.add(dome);
          } else if (roofProfile === "gable") {
            const roof = new THREE.Mesh(
              new THREE.ConeGeometry(Math.max(Math.min(item.w, item.h) * 0.52, 4), Math.max(Math.min(item.w, item.h) * 0.22, 2.2), 4),
              roofMaterial,
            );
            roof.rotation.y = Math.PI / 4;
            roof.scale.set(Math.max(item.w / Math.max(item.h, 1), 0.8), 0.75, 1);
            roof.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + Math.max(Math.min(item.w, item.h) * 0.09, 1.2)));
            object.add(roof);
          } else {
            const roof = new THREE.Mesh(
              new THREE.BoxGeometry(Math.max(item.w * 0.98, 1), roofProfile === "tower" ? 0.5 : 0.18, Math.max(item.h * 0.98, 1)),
              roofMaterial,
            );
            roof.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 0.12));
            object.add(roof);
            if (roofProfile === "tower") {
              const spire = new THREE.Mesh(
                new THREE.ConeGeometry(Math.max(Math.min(item.w, item.h) * 0.12, 1.2), Math.max(heightFt * 0.34, 8), 12),
                new THREE.MeshStandardMaterial({ color: "#020617", roughness: 0.5 }),
              );
              spire.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + Math.max(heightFt * 0.18, 4)));
              object.add(spire);
            }
          }
          if (previewQuality === "high") {
            addBuildingDetailCues(object, item, baseY, heightFt);
            const longSideIsX = item.w >= item.h;
            const entry = new THREE.Mesh(
              new THREE.BoxGeometry(
                Math.max(longSideIsX ? item.w * 0.18 : item.w * 0.22, 3),
                0.34,
                Math.max(longSideIsX ? item.h * 0.12 : item.h * 0.18, 2.2),
              ),
              new THREE.MeshStandardMaterial({ color: "#e5e7eb", roughness: 0.82, metalness: 0.01 }),
            );
            entry.position.copy(
              toScene(
                item.x + item.w / 2,
                item.y + item.h - Math.max(item.h * 0.04, 1.2),
                baseY + 0.34,
              ),
            );
            entry.userData = object.userData;
            object.add(entry);

            const roofLineMaterial = new THREE.LineBasicMaterial({ color: "#64748b", transparent: true, opacity: 0.28 });
            const facadeLineMaterial = new THREE.LineBasicMaterial({ color: "#475569", transparent: true, opacity: 0.18 });
            const roofInset = Math.min(Math.max(Math.min(item.w, item.h) * 0.08, 1.2), 6);
            const yTop = baseY + heightFt + 0.36;
            const roofLines = new THREE.LineSegments(
              new THREE.BufferGeometry().setFromPoints([
                toScene(item.x + roofInset, item.y + roofInset, yTop),
                toScene(item.x + item.w - roofInset, item.y + roofInset, yTop),
                toScene(item.x + item.w - roofInset, item.y + roofInset, yTop),
                toScene(item.x + item.w - roofInset, item.y + item.h - roofInset, yTop),
                toScene(item.x + item.w - roofInset, item.y + item.h - roofInset, yTop),
                toScene(item.x + roofInset, item.y + item.h - roofInset, yTop),
                toScene(item.x + roofInset, item.y + item.h - roofInset, yTop),
                toScene(item.x + roofInset, item.y + roofInset, yTop),
              ]),
              roofLineMaterial,
            );
            object.add(roofLines);
            const facadeBandY = baseY + heightFt * 0.62;
            const facadeLines = new THREE.LineSegments(
              new THREE.BufferGeometry().setFromPoints([
                toScene(item.x, item.y + 0.04, facadeBandY),
                toScene(item.x + item.w, item.y + 0.04, facadeBandY),
                toScene(item.x + item.w - 0.04, item.y, facadeBandY),
                toScene(item.x + item.w - 0.04, item.y + item.h, facadeBandY),
                toScene(item.x + item.w, item.y + item.h - 0.04, facadeBandY),
                toScene(item.x, item.y + item.h - 0.04, facadeBandY),
                toScene(item.x + 0.04, item.y + item.h, facadeBandY),
                toScene(item.x + 0.04, item.y, facadeBandY),
              ]),
              facadeLineMaterial,
            );
            object.add(facadeLines);
            if (Math.min(item.w, item.h) >= 24) {
              const roofUnitMaterial = new THREE.MeshStandardMaterial({ color: "#94a3b8", roughness: 0.8, metalness: 0.02 });
              [
                { x: item.x + item.w * 0.36, y: item.y + item.h * 0.42, w: 0.08, h: 0.08 },
                { x: item.x + item.w * 0.64, y: item.y + item.h * 0.58, w: 0.1, h: 0.07 },
              ].forEach((unit) => {
                const roofUnit = new THREE.Mesh(
                  new THREE.BoxGeometry(Math.max(item.w * unit.w, 3.2), 1.08, Math.max(item.h * unit.h, 2.4)),
                  roofUnitMaterial,
                );
                roofUnit.position.copy(toScene(unit.x, unit.y, yTop + 0.72));
                roofUnit.userData = object.userData;
                object.add(roofUnit);
              });
            }
          }
          addExactEdges(mesh, "#334155", state === "low" ? 0.54 : 0.66);
        }

        if (layer === "LOT") {
          const lotLine = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w * 0.98, 1), 0.08, Math.max(item.h * 0.98, 1))),
	            new THREE.LineBasicMaterial({ color: palette.line, transparent: true, opacity: 0.24 }),
          );
          lotLine.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + visualLift + heightFt + 0.08));
          object.add(lotLine);
          if (previewQuality === "high" && isDenseConceptLot(item) && Math.min(item.w, item.h) >= 18) {
            const unitSeed = `${item.id || item.label || "lot"}-${index}`;
            const widthJitter = 0.34 + stableUnitValue(unitSeed, 1) * 0.18;
            const depthJitter = 0.28 + stableUnitValue(unitSeed, 2) * 0.14;
            const heightJitter = 0.28 + stableUnitValue(unitSeed, 3) * 0.18;
            const houseW = Math.max(item.w * widthJitter, 7.5);
            const houseD = Math.max(item.h * depthJitter, 6.5);
            const houseH = Math.max(Math.min(item.w, item.h) * heightJitter, 8);
            const houseX = item.x + item.w * (0.44 + stableUnitValue(unitSeed, 4) * 0.16);
            const houseY = item.y + item.h * (0.42 + stableUnitValue(unitSeed, 5) * 0.16);
            const bodyTint = stableUnitValue(unitSeed, 6);
            const house = new THREE.Mesh(
              new THREE.BoxGeometry(houseW, houseH, houseD),
              new THREE.MeshStandardMaterial({
                color: bodyTint > 0.66 ? "#e7ded2" : bodyTint > 0.33 ? "#e5e7eb" : "#dbe3ea",
                roughness: 0.76,
                metalness: 0.01,
              }),
            );
            house.position.copy(toScene(houseX, houseY, baseY + houseH / 2 + 0.14));
            house.userData = {
              ...object.userData,
              source: "visual massing for dense concept lot; not source-detected building evidence",
            };
            object.add(house);
            addExactEdges(house, "#475569", 0.34);
            addBuildingDetailCues(
              object,
              {
                ...item,
                x: houseX - houseW / 2,
                y: houseY - houseD / 2,
                w: houseW,
                h: houseD,
              },
              baseY,
              houseH,
              { smallLot: true },
            );
            const roof = new THREE.Mesh(
              new THREE.ConeGeometry(Math.max(Math.min(houseW, houseD) * 0.64, 4), Math.max(houseH * 0.24, 2.4), 4),
              new THREE.MeshStandardMaterial({
                color: stableUnitValue(unitSeed, 7) > 0.55 ? "#cbd5e1" : "#b7c0cb",
                roughness: 0.82,
              }),
            );
            roof.rotation.y = Math.PI / 4;
            roof.scale.set(Math.max(houseW / Math.max(houseD, 1), 0.8), 0.58, 1);
            roof.position.copy(toScene(houseX, houseY, baseY + houseH + Math.max(houseH * 0.08, 1)));
            roof.userData = house.userData;
            object.add(roof);
          }
        }
        if (layer === "ROAD" || layer === "SIDEWALK") {
          const stripe = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w * 0.96, 1), 0.08, Math.max(item.h * 0.96, 1))),
            new THREE.LineBasicMaterial({ color: palette.line, transparent: true, opacity: 0.78 }),
          );
          stripe.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + visualLift + heightFt + 0.08));
          object.add(stripe);
        }
        if (layer === "PARKING" && previewQuality === "high" && item.w >= 70 && item.h >= 42) {
          const topY = baseY + visualLift + heightFt + 0.14;
          const stallMaterial = new THREE.LineBasicMaterial({ color: "#f8fafc", transparent: true, opacity: 0.78 });
          const aisleMaterial = new THREE.LineBasicMaterial({ color: "#cbd5e1", transparent: true, opacity: 0.62 });
          const longAxisIsX = item.w >= item.h;
          const longLength = longAxisIsX ? item.w : item.h;
          const shortLength = longAxisIsX ? item.h : item.w;
          const margin = Math.max(4, Math.min(8, Math.min(item.w, item.h) * 0.08));
          const stallWidth = 9;
          const stallDepth = 18;
          const aisleWidth = 24;
          const moduleDepth = stallDepth * 2 + aisleWidth;
          const moduleCount = Math.max(1, Math.min(3, Math.floor((shortLength - margin * 2) / moduleDepth) || 1));
          const usedDepth = moduleCount * moduleDepth;
          const depthStart = margin + Math.max(0, (shortLength - margin * 2 - usedDepth) / 2);
          const stallCountAlong = Math.max(4, Math.min(30, Math.floor((longLength - margin * 2) / stallWidth)));
          const linePoint = (long: number, short: number) =>
            longAxisIsX
              ? toScene(item.x + long, item.y + short, topY)
              : toScene(item.x + short, item.y + long, topY);

          for (let moduleIndex = 0; moduleIndex < moduleCount; moduleIndex += 1) {
            const moduleStart = depthStart + moduleIndex * moduleDepth;
            const nearRowEnd = moduleStart + stallDepth;
            const farRowStart = nearRowEnd + aisleWidth;
            for (let stallIndex = 0; stallIndex <= stallCountAlong; stallIndex += 1) {
              const long = margin + ((longLength - margin * 2) * stallIndex) / stallCountAlong;
              object.add(
                new THREE.Line(
                  new THREE.BufferGeometry().setFromPoints([
                    linePoint(long, moduleStart),
                    linePoint(long, nearRowEnd),
                  ]),
                  stallMaterial,
                ),
              );
              object.add(
                new THREE.Line(
                  new THREE.BufferGeometry().setFromPoints([
                    linePoint(long, farRowStart),
                    linePoint(long, farRowStart + stallDepth),
                  ]),
                  stallMaterial,
                ),
              );
            }
            [nearRowEnd, farRowStart].forEach((short) => {
              object.add(
                new THREE.Line(
                  new THREE.BufferGeometry().setFromPoints([
                    linePoint(margin, short),
                    linePoint(longLength - margin, short),
                  ]),
                  aisleMaterial,
                ),
              );
            });
          }
        }
      }

      const suppressContradictoryGradingBadge =
        terrainState.mode === "terrain" && /grading surface missing/i.test(String(item.label || ""));
      const needsBadge =
        !suppressContradictoryGradingBadge &&
        (object.userData.blockers.length > 0 ||
        /low|missing|review/i.test(String(object.userData.confidence)));
      if (needsBadge && visibleLabelCount < maxVisibleLabels) {
        const sprite = createTextSprite(needsBadge ? `${item.label} | review` : item.label, needsBadge ? "#b45309" : "#0f172a");
        sprite.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 8));
        object.add(sprite);
        visibleLabelCount += 1;
      }

      const rotationDeg = Number(item.rotation || 0);
      const usesRectangularPlacementGeometry = !item.geometryType || item.geometryType === "rect";
      if (usesRectangularPlacementGeometry && Number.isFinite(rotationDeg) && Math.abs(rotationDeg) > 0.01) {
        const pivot = toScene(item.x + item.w / 2, item.y + item.h / 2, 0);
        object.children.forEach((child) => child.position.sub(pivot));
        object.position.copy(pivot);
        object.rotation.y = THREE.MathUtils.degToRad(-rotationDeg);
      }

      root.add(object);
      pickables.push(object);
    });
    pickablesRef.current = pickables;

    const renderScene = () => {
      controls.update();
      renderer.render(scene, camera);
    };
    let frame: number | null = null;
    const scheduleRender = () => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        renderScene();
      });
    };
    const handleControlsChange = () => scheduleRender();
    controls.addEventListener("change", handleControlsChange);
    scheduleRender();

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const pickAt = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1;
      pointer.y = -(((event.clientY - rect.top) / Math.max(rect.height, 1)) * 2 - 1);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickables, true);
      const hit = hits.find((candidate) => candidate.object.userData.itemId || candidate.object.parent?.userData.itemId);
      const data = hit?.object.userData.itemId ? hit.object.userData : hit?.object.parent?.userData;
      if (!data?.itemId) {
        onSelectItem?.(null);
        setPicked(null);
        return;
      }
      onSelectItem?.(data.itemId);
      setPicked({
        id: data.itemId,
        label: data.label,
        layer: data.layer,
        confidence: data.confidence,
        blockers: data.blockers,
        source: data.source,
        heightFt: typeof data.heightFt === "number" ? data.heightFt : null,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    };
    renderer.domElement.addEventListener("click", pickAt);

    const resizeObserver = new ResizeObserver(([entry]) => {
      const nextWidth = Math.max(entry.contentRect.width, 320);
      const nextHeight = Math.max(entry.contentRect.height, 320);
      renderer.setSize(nextWidth, nextHeight);
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
      scheduleRender();
    });
    resizeObserver.observe(mount);

    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("click", pickAt);
      controls.removeEventListener("change", handleControlsChange);
      controls.dispose();
      renderer.dispose();
      if (sceneRef.current === scene) sceneRef.current = null;
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if ("geometry" in mesh && mesh.geometry) mesh.geometry.dispose();
        if ("material" in mesh && mesh.material) {
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          materials.forEach((material) => material.dispose());
        }
      });
      mount.innerHTML = "";
    };
  }, [items, modelBounds, onSelectItem, previewQuality, selectedItemId, terrainState]);

  return (
    <div
      className={`relative w-full min-w-0 overflow-hidden bg-white ${
        fullscreen
          ? "h-[100dvh] min-h-0 rounded-none"
          : "h-full min-h-[300px] rounded-none"
      }`}
      data-testid="civil-3d-viewer"
      onDoubleClick={onOpenFullscreen}
    >
      <div ref={mountRef} className="h-full w-full touch-none" data-testid="civil-3d-canvas-mount" />
      <div className="pointer-events-none absolute bottom-4 left-4 max-w-[calc(100%-2rem)] rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm">
        Review visualization only | visual mode does not mutate canonical geometry
      </div>
      <div
        className="pointer-events-none absolute left-4 top-4 max-w-[min(330px,calc(100%-2rem))] rounded-xl border border-slate-200 bg-white/88 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm backdrop-blur"
        data-testid="civil-3d-terrain-state"
        title={terrainState.detail}
      >
        {terrainState.label}
      </div>
      <div className="pointer-events-none absolute right-4 top-20 rounded-full bg-slate-900/75 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white sm:top-4">
        Orbit | Pan | Zoom
      </div>
      {previewQuality === "high" ? (
        <div
          className="pointer-events-none absolute left-4 top-20 max-w-[min(330px,calc(100%-2rem))] rounded-xl border border-slate-200 bg-white/88 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm backdrop-blur sm:top-16"
          data-testid="civil-3d-massing-summary"
        >
          3D massing: {massingStats.vertical} vertical / {massingStats.civilFlat} civil layers / {massingStats.buildingDetail} detailed buildings
        </div>
      ) : null}
      {objectChips.length ? (
        <div className="civora-3d-object-strip absolute right-4 top-32 z-[90] flex max-h-36 w-[min(218px,calc(100%-2rem))] flex-col gap-1 overflow-y-auto rounded-xl border border-slate-200 bg-white/76 p-2 shadow-sm backdrop-blur sm:top-16" data-testid="civil-3d-object-strip">
          <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            Objects
          </p>
          {objectChips.map((object) => (
            <button
              key={object.id}
              type="button"
              data-canonical-object-id={object.id}
              data-canonical-geometry-signature={object.geometrySignature}
              onClick={() => selectObject(object)}
              className={`min-w-0 rounded-lg border px-2 py-1.5 text-left text-[11px] font-semibold transition ${
                selectedItemId === object.id
                  ? "border-amber-300 bg-amber-50 text-amber-800"
                  : "border-slate-200/80 bg-white/74 text-slate-700 hover:bg-white"
              }`}
            >
              <span className="block truncate">{object.label}</span>
              <span className="block truncate text-[10px] uppercase tracking-[0.12em] text-slate-400">
                {object.layer}{object.heightFt ? ` | ${Math.round(object.heightFt)} ft` : ""} | {object.confidence}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      {picked ? (
        <div
          className="pointer-events-none absolute z-[95] max-w-[230px] rounded-xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
          data-testid="civil-3d-selection-popover"
          style={{
            left: Math.min(Math.max(picked.x + 12, 8), 360),
            top: Math.max(picked.y - 18, 58),
          }}
        >
          <p className="font-semibold text-slate-900">{picked.label}</p>
          <p className="mt-1 uppercase tracking-[0.12em] text-slate-400">{picked.layer} | {picked.confidence}</p>
          {picked.heightFt ? (
            <p className="mt-2 font-semibold text-slate-700" data-testid="civil-3d-selected-height">
              Height {Math.round(picked.heightFt)} ft
            </p>
          ) : null}
          <p className="mt-2 text-slate-500">{picked.blockers[0] || picked.source}</p>
        </div>
      ) : null}
    </div>
  );
}
