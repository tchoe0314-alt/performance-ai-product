import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Preview3DItem } from "../types";

type PickedObject = {
  id: string | null;
  label: string;
  layer: string;
  confidence: string;
  blockers: string[];
  source: string;
  x: number;
  y: number;
};

type Preview3DCanvasProps = {
  items: Preview3DItem[];
  interactive: boolean;
  previewQuality?: "standard" | "high";
  selectedItemId?: string | null;
  hasTerrainSource?: boolean;
  hasGradingSurface?: boolean;
  onSelectItem?: (id: string | null) => void;
  onOpenFullscreen?: () => void;
};

const layerPalette: Record<string, { top: string; side: string; line: string }> = {
  BUILDING: { top: "#f3f4f6", side: "#cbd5e1", line: "#64748b" },
  STRUCTURE: { top: "#e7dbc6", side: "#c6a978", line: "#8a6d3b" },
  ROAD: { top: "#4b5563", side: "#374151", line: "#f8fafc" },
  PARKING: { top: "#6b7280", side: "#4b5563", line: "#f8fafc" },
  SIDEWALK: { top: "#d6d3d1", side: "#a8a29e", line: "#78716c" },
  DRAINAGE: { top: "#6bb7c8", side: "#3b8ca2", line: "#dff7fb" },
  UTILITY: { top: "#6d5bd0", side: "#4f46e5", line: "#ede9fe" },
  CONSTRAINT: { top: "#f8b4a5", side: "#f97360", line: "#9f3412" },
  TERRAIN: { top: "#d7e7c6", side: "#adc894", line: "#5c7f46" },
};

const normalizeLayer = (layer: string) => {
  const key = String(layer || "").toUpperCase();
  if (key.includes("BUILDING") || key.includes("PAD")) return "BUILDING";
  if (key.includes("STRUCTURE")) return "STRUCTURE";
  if (key.includes("PARK")) return "PARKING";
  if (key.includes("SIDEWALK") || key.includes("WALK")) return "SIDEWALK";
  if (key.includes("DRAIN") || key.includes("BASIN") || key.includes("STORM")) return "DRAINAGE";
  if (key.includes("UTILITY") || key.includes("WATER") || key.includes("SAN") || key.includes("HYDRANT") || key.includes("MANHOLE")) return "UTILITY";
  if (key.includes("LOT") || key.includes("EASEMENT") || key.includes("CONSTRAINT") || key.includes("SETBACK")) return "CONSTRAINT";
  if (key.includes("TERRAIN") || key.includes("SITE")) return "TERRAIN";
  if (key.includes("ROAD") || key.includes("DRIVE")) return "ROAD";
  return key || "OBJECT";
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
  item.id || `${normalizeLayer(item.layer).toLowerCase()}-${item.label.replace(/\W+/g, "-").toLowerCase()}-${index}`;

const displayHeightForLayer = (item: Preview3DItem, layer: string) => {
  if (layer === "ROAD" || layer === "PARKING") return 0.12;
  if (layer === "SIDEWALK") return 0.08;
  if (layer === "CONSTRAINT") return 0.06;
  if (layer === "DRAINAGE") return Math.max(1.4, Math.min(Math.abs(item.height || 2.4), 5));
  if (layer === "UTILITY") return Math.max(0.22, Math.min(Math.min(item.w, item.h) * 0.03, 0.7));
  if (layer === "BUILDING") return Math.max(14, Math.min(item.height || Math.min(item.w, item.h) * 0.22, 52));
  return Math.max(0.35, Math.min(item.height || 1, 8));
};

const surfaceExtrudeDepth = (heightFt: number, layer: string) => {
  if (layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK" || layer === "CONSTRAINT") {
    return Math.max(0.08, heightFt);
  }
  return Math.max(heightFt, 0.35);
};

export default function Preview3DCanvas({
  items,
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
    () =>
      items
        .map((item, index) => ({
          id: getItemId(item, index),
          label: item.label,
          layer: normalizeLayer(item.layer),
          confidence: describeConfidence(item.confidence),
          blockers: item.blockers || [],
          source: item.source || "preview object",
        }))
        .filter((item) => item.layer !== "TERRAIN")
        .slice(0, 10),
    [items],
  );

  const selectObject = (object: (typeof objectChips)[number]) => {
    onSelectItem?.(object.id);
    setPicked({
      id: object.id,
      label: object.label,
      layer: object.layer,
      confidence: object.confidence,
      blockers: object.blockers,
      source: object.source,
      x: 22,
      y: 118,
    });
  };

  const modelBounds = useMemo(() => {
    if (!items.length) return { minX: 0, minY: 0, maxX: 240, maxY: 160, spanX: 240, spanY: 160 };
    const minX = Math.min(...items.map((item) => item.x));
    const minY = Math.min(...items.map((item) => item.y));
    const maxX = Math.max(...items.map((item) => item.x + item.w));
    const maxY = Math.max(...items.map((item) => item.y + item.h));
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
    if (!sourceSamples.length) {
      return {
        label: "Flat site fallback - terrain source missing",
        detail: "No preview elevation samples were supplied; no terrain is inferred.",
        mode: "fallback" as const,
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
    scene.background = new THREE.Color(previewQuality === "high" ? "#eef5f7" : "#f3f6f8");

    const renderer = new THREE.WebGLRenderer({ antialias: previewQuality === "high", preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, previewQuality === "high" ? 2 : 1.35));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = previewQuality === "high";
    renderer.shadowMap.type = THREE.PCFShadowMap;
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 5000);
    const maxSpan = Math.max(modelBounds.spanX, modelBounds.spanY);
    camera.position.set(maxSpan * 0.86, maxSpan * 0.58, maxSpan * 0.80);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.minDistance = Math.max(maxSpan * 0.18, 25);
    controls.maxDistance = Math.max(maxSpan * 3.2, 300);
    controls.target.set(0, 0, 0);
    controls.update();
    controlsRef.current = controls;

    const ambient = new THREE.HemisphereLight("#ffffff", "#b6c4cf", previewQuality === "high" ? 1.95 : 1.75);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight("#fff7ed", previewQuality === "high" ? 2.35 : 1.55);
    sun.position.set(maxSpan * 0.42, maxSpan * 0.95, maxSpan * 0.52);
    sun.castShadow = previewQuality === "high";
    scene.add(sun);

    const root = new THREE.Group();
    root.rotation.x = 0;
    scene.add(root);

    const centerX = modelBounds.minX + modelBounds.spanX / 2;
    const centerY = modelBounds.minY + modelBounds.spanY / 2;
    const toScene = (x: number, y: number, z = 0) =>
      new THREE.Vector3(x - centerX, z, y - centerY);

    const terrainGeometry =
      terrainState.mode === "terrain"
        ? new THREE.PlaneGeometry(modelBounds.spanX, modelBounds.spanY, previewQuality === "high" ? 24 : 12, previewQuality === "high" ? 24 : 12)
        : new THREE.PlaneGeometry(modelBounds.spanX, modelBounds.spanY, 1, 1);
    terrainGeometry.rotateX(-Math.PI / 2);
    if (terrainState.mode === "terrain") {
      const positions = terrainGeometry.attributes.position;
      const samples = items
        .filter((item) => item.terrainSample && typeof item.z === "number" && Number.isFinite(item.z))
        .map((item) => ({
          x: item.x + item.w / 2 - centerX,
          z: item.y + item.h / 2 - centerY,
          y: Number(item.z),
        }));
      for (let i = 0; i < positions.count; i += 1) {
        const vx = positions.getX(i);
        const vz = positions.getZ(i);
        let weighted = 0;
        let weight = 0;
        samples.forEach((sample) => {
          const distance = Math.max(Math.hypot(sample.x - vx, sample.z - vz), 1);
          const nextWeight = 1 / distance;
          weighted += sample.y * nextWeight;
          weight += nextWeight;
        });
        positions.setY(i, weight ? weighted / weight : 0);
      }
      positions.needsUpdate = true;
      terrainGeometry.computeVertexNormals();
    }
    const terrainMaterial = new THREE.MeshStandardMaterial({
      color: terrainState.mode === "fallback" ? "#f3f1e8" : "#d7e7c6",
      roughness: 0.9,
      metalness: 0,
      wireframe: previewQuality === "standard" && terrainState.mode === "terrain",
      transparent: terrainState.mode === "fallback",
      opacity: terrainState.mode === "fallback" ? 0.96 : 1,
    });
    const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
    terrain.receiveShadow = true;
    root.add(terrain);

    const pickables: THREE.Object3D[] = [];
    let visibleLabelCount = 0;
    const maxVisibleLabels = selectedItemId ? 1 : 0;
    items.forEach((item, index) => {
      const layer = normalizeLayer(item.layer);
      if (layer === "TERRAIN") return;
      const id = getItemId(item, index);
      const palette = layerPalette[layer] || { top: item.color || "#cbd5e1", side: item.color || "#94a3b8", line: "#f8fafc" };
      const heightFt = displayHeightForLayer(item, layer);
      const baseY = typeof item.z === "number" && Number.isFinite(item.z) ? item.z : 0;
      const state = confidenceState(item);
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
      };

      const cadMaterial = new THREE.MeshStandardMaterial({
        color: state === "blocked" ? "#dc2626" : state === "low" ? "#94a3b8" : item.unsupported ? "#f59e0b" : palette.top,
        roughness: layer === "ROAD" || layer === "PARKING" ? 0.86 : layer === "DRAINAGE" ? 0.42 : 0.72,
        transparent: item.unsupported || layer === "CONSTRAINT" || state === "low" || state === "imported" || state === "stale",
        opacity: item.unsupported ? 0.58 : state === "low" ? 0.66 : state === "imported" ? 0.8 : state === "stale" ? 0.72 : layer === "CONSTRAINT" ? 0.36 : 1,
      });
      let renderedCadGeometry = false;
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
      if (item.unsupported) {
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
      } else if ((item.geometryType === "polyline" || item.geometryType === "polygon") && Array.isArray(item.geometry) && item.geometry.length >= 2) {
        const points = item.geometry.map(([x, y]) => toScene(x, y, baseY + 0.55));
        if (item.geometryType === "polygon" && points.length >= 3) {
          const shape = new THREE.Shape();
          item.geometry.forEach(([x, y], pointIndex) => {
            const sx = x - centerX;
            const sy = y - centerY;
            if (pointIndex === 0) shape.moveTo(sx, sy);
            else shape.lineTo(sx, sy);
          });
          shape.closePath();
          const displayDepth = surfaceExtrudeDepth(heightFt, layer);
          const geometry = new THREE.ExtrudeGeometry(shape, {
            depth: displayDepth,
            bevelEnabled: layer === "BUILDING",
            bevelSegments: layer === "BUILDING" ? 1 : 0,
            bevelSize: layer === "BUILDING" ? 0.6 : 0,
            bevelThickness: layer === "BUILDING" ? 0.4 : 0,
          });
          geometry.rotateX(-Math.PI / 2);
          const mesh = new THREE.Mesh(geometry, cadMaterial);
          mesh.userData = object.userData;
          object.add(mesh);
          addExactEdges(mesh, state === "blocked" ? "#fecaca" : palette.line, state === "low" ? 0.42 : 0.62);
          if (layer === "PARKING" && item.source !== "fallback" && Math.max(item.w, item.h) >= 42 && Math.min(item.w, item.h) >= 32) {
            const stripeMaterial = new THREE.LineBasicMaterial({ color: "#f8fafc", transparent: true, opacity: state === "low" ? 0.34 : 0.58 });
            const bounds = new THREE.Box3().setFromObject(mesh);
            const stripeCount = Math.max(3, Math.min(14, Math.floor((bounds.max.x - bounds.min.x) / 9)));
            for (let stripeIndex = 1; stripeIndex < stripeCount; stripeIndex += 1) {
              const x = bounds.min.x + ((bounds.max.x - bounds.min.x) * stripeIndex) / stripeCount;
              const line = new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                  new THREE.Vector3(x, baseY + displayDepth + 0.06, bounds.min.z),
                  new THREE.Vector3(x, baseY + displayDepth + 0.06, bounds.max.z),
                ]),
                stripeMaterial,
              );
              object.add(line);
            }
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
          const lineMaterial = new THREE.LineBasicMaterial({
            color: layer === "ROAD" ? "#f8fafc" : palette.line,
            transparent: true,
            opacity: layer === "ROAD" ? 0.54 : 0.42,
          });
          item.geometry.slice(0, -1).forEach(([x1, y1], segmentIndex) => {
            const [x2, y2] = item.geometry?.[segmentIndex + 1] ?? [x1, y1];
            const dx = x2 - x1;
            const dy = y2 - y1;
            const length = Math.hypot(dx, dy);
            if (length < 0.01) return;
            const segment = new THREE.Mesh(
              new THREE.BoxGeometry(length, slabDepth, corridorWidth),
              slabMaterial,
            );
            segment.position.copy(toScene((x1 + x2) / 2, (y1 + y2) / 2, baseY + slabDepth / 2 + 0.05));
            segment.rotation.y = -Math.atan2(dy, dx);
            segment.userData = object.userData;
            object.add(segment);
            addExactEdges(segment, layer === "ROAD" ? "rgba(15,23,42,0.34)" : palette.line, layer === "ROAD" ? 0.2 : 0.32);
            if (layer === "ROAD" && state !== "low") {
              const centerline = new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                  toScene(x1, y1, baseY + slabDepth + 0.12),
                  toScene(x2, y2, baseY + slabDepth + 0.12),
                ]),
                lineMaterial,
              );
              object.add(centerline);
            }
          });
        } else {
          const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.01);
          const tubeRadius =
            layer === "ROAD"
              ? Math.max(5, Math.min(Number(item.corridorWidth ?? 28) / 2, 21))
              : layer === "SIDEWALK"
                ? Math.max(1.8, Math.min(Number(item.corridorWidth ?? 6) / 2, 6))
                : layer === "UTILITY"
                  ? 0.42
                  : Math.max(Math.min(item.w, item.h) * 0.012, 0.22);
          const tube = new THREE.Mesh(
            new THREE.TubeGeometry(curve, Math.max(points.length * 10, 10), tubeRadius, 8, false),
            cadMaterial,
          );
          tube.userData = object.userData;
          object.add(tube);
          if (layer === "ROAD" && state !== "low") {
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
        if (state === "low" || state === "imported" || state === "stale" || state === "blocked") {
          const reviewRing = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w, 1), 0.08, Math.max(item.h, 1))),
            new THREE.LineBasicMaterial({ color: state === "blocked" ? "#dc2626" : "#f59e0b", transparent: true, opacity: 0.28 }),
          );
          reviewRing.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + Math.max(heightFt, 0.35) + 0.08));
          object.add(reviewRing);
        }
      } else if (layer === "DRAINAGE") {
        const depth = Math.max(1.2, Math.abs(Math.min(baseY, 0)) || Math.min(heightFt, 4));
        const basin = new THREE.Mesh(
          new THREE.CylinderGeometry(1, 0.64, Math.max(depth, 0.75), 64),
          new THREE.MeshStandardMaterial({ color: "#7fc6a4", roughness: 0.84, transparent: true, opacity: 0.72 }),
        );
        basin.scale.set(Math.max(item.w * 0.5, 1), 1, Math.max(item.h * 0.5, 1));
        basin.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, -depth / 2));
        basin.userData = object.userData;
        object.add(basin);

        const water = new THREE.Mesh(
          new THREE.CylinderGeometry(1, 1, 0.08, 64),
          new THREE.MeshStandardMaterial({ color: "#7dd3fc", roughness: 0.18, metalness: 0.02, transparent: true, opacity: 0.68 }),
        );
        water.scale.set(Math.max(item.w * 0.36, 1), 1, Math.max(item.h * 0.34, 1));
        water.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, 0.05));
        object.add(water);

        const rimPoints = Array.from({ length: 96 }, (_, pointIndex) => {
          const angle = (Math.PI * 2 * pointIndex) / 95;
          return new THREE.Vector3(
            Math.cos(angle) * Math.max(item.w * 0.52, 1),
            0.16,
            Math.sin(angle) * Math.max(item.h * 0.52, 1),
          );
        });
        const rim = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(rimPoints),
          new THREE.LineBasicMaterial({ color: "#236a7b", transparent: true, opacity: 0.7 }),
        );
        rim.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, 0));
        object.add(rim);
      } else if (layer === "UTILITY") {
        const geometry = new THREE.CapsuleGeometry(0.46, Math.max(item.w, item.h), 6, 12);
        const utility = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({ color: palette.side, roughness: 0.6, metalness: 0.02 }),
        );
        utility.rotation.z = Math.PI / 2;
        utility.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, Math.max(baseY, 1.5)));
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
        const material = new THREE.MeshStandardMaterial({
          color: previewQuality === "high" ? palette.top : item.color || palette.top,
          roughness: layer === "ROAD" || layer === "PARKING" ? 0.72 : 0.58,
          metalness: 0.02,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = previewQuality === "high" && layer === "BUILDING";
        mesh.receiveShadow = true;
        mesh.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt / 2));
        mesh.userData = object.userData;
        object.add(mesh);

        if (layer === "BUILDING") {
          const roof = new THREE.Mesh(
            new THREE.BoxGeometry(Math.max(item.w * 0.98, 1), 0.18, Math.max(item.h * 0.98, 1)),
            new THREE.MeshStandardMaterial({ color: "#e5e7eb", roughness: 0.78 }),
          );
          roof.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 0.12));
          object.add(roof);
          addExactEdges(mesh, "#475569", 0.42);
        }

        if (layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK") {
          const stripe = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w * 0.96, 1), 0.08, Math.max(item.h * 0.96, 1))),
            new THREE.LineBasicMaterial({ color: palette.line, transparent: true, opacity: 0.78 }),
          );
          stripe.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 0.08));
          object.add(stripe);
          if (layer === "PARKING" && item.w >= 48 && item.h >= 34) {
            const stallMaterial = new THREE.LineBasicMaterial({
              color: "#f8fafc",
              transparent: true,
              opacity: 0.54,
            });
            const stallCount = Math.max(4, Math.min(18, Math.floor(item.w / 10)));
            for (let stripeIndex = 1; stripeIndex < stallCount; stripeIndex += 1) {
              const x = item.x + (item.w * stripeIndex) / stallCount;
              const stall = new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                  toScene(x, item.y + item.h * 0.10, baseY + heightFt + 0.14),
                  toScene(x, item.y + item.h * 0.90, baseY + heightFt + 0.14),
                ]),
                stallMaterial,
              );
              object.add(stall);
            }
            const aisle = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints([
                toScene(item.x + item.w * 0.05, item.y + item.h * 0.5, baseY + heightFt + 0.15),
                toScene(item.x + item.w * 0.95, item.y + item.h * 0.5, baseY + heightFt + 0.15),
              ]),
              new THREE.LineBasicMaterial({ color: "#dbeafe", transparent: true, opacity: 0.62 }),
            );
            object.add(aisle);
          }
        }
      }

      const needsBadge =
        object.userData.blockers.length > 0 ||
        /low|missing|review/i.test(String(object.userData.confidence));
      if (needsBadge && visibleLabelCount < maxVisibleLabels) {
        const sprite = createTextSprite(needsBadge ? `${item.label} | review` : item.label, needsBadge ? "#b45309" : "#0f172a");
        sprite.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 8));
        object.add(sprite);
        visibleLabelCount += 1;
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
      className="relative h-[min(600px,calc(100dvh-11rem))] min-h-[360px] w-full min-w-0 overflow-hidden rounded-xl bg-white md:rounded-[20px]"
      data-testid="civil-3d-viewer"
      onDoubleClick={onOpenFullscreen}
    >
      <div ref={mountRef} className="h-full w-full touch-none" data-testid="civil-3d-canvas-mount" />
      <div className="pointer-events-none absolute bottom-4 left-4 max-w-[calc(100%-2rem)] rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm">
        Review visualization only | visual mode does not mutate canonical geometry
      </div>
      <div className="pointer-events-none absolute right-4 top-20 rounded-full bg-slate-900/75 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white sm:top-4">
        Orbit | Pan | Zoom
      </div>
      {objectChips.length ? (
        <div className="absolute right-4 top-28 z-[90] flex max-h-44 w-[min(260px,calc(100%-2rem))] flex-col gap-1 overflow-y-auto rounded-xl border border-slate-200 bg-white/92 p-2 shadow-sm backdrop-blur sm:top-16" data-testid="civil-3d-object-strip">
          {objectChips.map((object) => (
            <button
              key={object.id}
              type="button"
              onClick={() => selectObject(object)}
              className={`min-w-0 rounded-lg border px-2 py-1.5 text-left text-[11px] font-semibold transition ${
                selectedItemId === object.id
                  ? "border-amber-300 bg-amber-50 text-amber-800"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              <span className="block truncate">{object.label}</span>
              <span className="block truncate text-[10px] uppercase tracking-[0.12em] text-slate-400">{object.layer} | {object.confidence}</span>
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
          <p className="mt-2 text-slate-500">{picked.blockers[0] || picked.source}</p>
        </div>
      ) : null}
    </div>
  );
}
