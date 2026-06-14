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
  BUILDING: { top: "#334155", side: "#475569", line: "#e2e8f0" },
  STRUCTURE: { top: "#a16207", side: "#ca8a04", line: "#fef3c7" },
  ROAD: { top: "#374151", side: "#4b5563", line: "#f8fafc" },
  PARKING: { top: "#64748b", side: "#94a3b8", line: "#f8fafc" },
  SIDEWALK: { top: "#99f6e4", side: "#5eead4", line: "#0f766e" },
  DRAINAGE: { top: "#38bdf8", side: "#0284c7", line: "#e0f2fe" },
  UTILITY: { top: "#a78bfa", side: "#7c3aed", line: "#faf5ff" },
  CONSTRAINT: { top: "#fda4af", side: "#fb7185", line: "#fff1f2" },
  TERRAIN: { top: "#bbf7d0", side: "#86efac", line: "#166534" },
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
  }, [selectedItemId]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    mount.innerHTML = "";

    const width = Math.max(mount.clientWidth, 320);
    const height = Math.max(mount.clientHeight, 320);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(previewQuality === "high" ? "#e2e8f0" : "#eef2f7");

    const renderer = new THREE.WebGLRenderer({ antialias: previewQuality === "high", preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, previewQuality === "high" ? 2 : 1.35));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = previewQuality === "high";
    renderer.shadowMap.type = THREE.PCFShadowMap;
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 5000);
    const maxSpan = Math.max(modelBounds.spanX, modelBounds.spanY);
    camera.position.set(maxSpan * 0.72, maxSpan * 0.62, maxSpan * 0.78);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.minDistance = Math.max(maxSpan * 0.18, 25);
    controls.maxDistance = Math.max(maxSpan * 3.2, 300);
    controls.target.set(0, 0, 0);
    controls.update();
    controlsRef.current = controls;

    const ambient = new THREE.HemisphereLight("#ffffff", "#94a3b8", previewQuality === "high" ? 2.4 : 2.0);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight("#ffffff", previewQuality === "high" ? 2.8 : 1.8);
    sun.position.set(maxSpan * 0.3, maxSpan * 0.8, maxSpan * 0.6);
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
      color: terrainState.mode === "fallback" ? "#f1f5f9" : "#bbf7d0",
      roughness: 0.9,
      metalness: 0,
      wireframe: previewQuality === "standard" && terrainState.mode === "terrain",
      transparent: terrainState.mode === "fallback",
      opacity: terrainState.mode === "fallback" ? 0.92 : 1,
    });
    const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
    terrain.receiveShadow = true;
    root.add(terrain);

    const grid = new THREE.GridHelper(Math.max(modelBounds.spanX, modelBounds.spanY), previewQuality === "high" ? 20 : 10, "#94a3b8", "#cbd5e1");
    grid.position.y = 0.035;
    root.add(grid);

    const pickables: THREE.Object3D[] = [];
    const labels: THREE.Sprite[] = [];
    items.forEach((item, index) => {
      const layer = normalizeLayer(item.layer);
      if (layer === "TERRAIN") return;
      const id = getItemId(item, index);
      const palette = layerPalette[layer] || { top: item.color || "#cbd5e1", side: item.color || "#94a3b8", line: "#f8fafc" };
      const heightFt = Math.max(layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK" ? 0.45 : 1, item.height || 1);
      const baseY = typeof item.z === "number" && Number.isFinite(item.z) ? item.z : 0;
      const object = new THREE.Group();
      object.userData = {
        itemId: id,
        label: item.label,
        layer,
        confidence: describeConfidence(item.confidence),
        blockers: item.blockers || [],
        source: item.source || (layer === "UTILITY" ? "utility evidence only where supplied" : "preview object"),
      };

      if (layer === "DRAINAGE") {
        const depth = Math.max(1.2, Math.abs(Math.min(baseY, 0)) || Math.min(heightFt, 4));
        const basin = new THREE.Mesh(
          new THREE.BoxGeometry(Math.max(item.w * 0.72, 1), Math.max(depth, 0.75), Math.max(item.h * 0.72, 1)),
          new THREE.MeshStandardMaterial({ color: palette.top, roughness: 0.55, transparent: true, opacity: 0.74 }),
        );
        basin.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, -depth / 2));
        basin.userData = object.userData;
        object.add(basin);

        const rim = new THREE.LineSegments(
          new THREE.EdgesGeometry(new THREE.BoxGeometry(item.w, 0.35, item.h)),
          new THREE.LineBasicMaterial({ color: palette.line }),
        );
        rim.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, 0.2));
        object.add(rim);
      } else if (layer === "UTILITY") {
        const geometry = new THREE.CapsuleGeometry(Math.max(Math.min(item.w, item.h) * 0.08, 0.45), Math.max(item.w, item.h), 8, 16);
        const utility = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({ color: palette.side, roughness: 0.45, metalness: 0.05 }),
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

        if (layer === "ROAD" || layer === "PARKING" || layer === "SIDEWALK") {
          const stripe = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(Math.max(item.w * 0.96, 1), 0.08, Math.max(item.h * 0.96, 1))),
            new THREE.LineBasicMaterial({ color: palette.line, transparent: true, opacity: 0.78 }),
          );
          stripe.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 0.08));
          object.add(stripe);
        }
      }

      const needsBadge =
        object.userData.blockers.length > 0 ||
        /low|missing|review/i.test(String(object.userData.confidence));
      if (needsBadge || previewQuality === "high") {
        const sprite = createTextSprite(needsBadge ? `${item.label} | review` : item.label, needsBadge ? "#b45309" : "#0f172a");
        sprite.position.copy(toScene(item.x + item.w / 2, item.y + item.h / 2, baseY + heightFt + 8));
        labels.push(sprite);
        object.add(sprite);
      }

      root.add(object);
      pickables.push(object);
    });
    pickablesRef.current = pickables;

    const terrainLabel = createTextSprite(terrainState.label, terrainState.mode === "fallback" ? "#b45309" : "#166534");
    terrainLabel.position.set(0, 12, -modelBounds.spanY / 2 - 14);
    root.add(terrainLabel);

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      frame = window.requestAnimationFrame(animate);
    };
    let frame = window.requestAnimationFrame(animate);

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
    });
    resizeObserver.observe(mount);

    return () => {
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("click", pickAt);
      controls.dispose();
      renderer.dispose();
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
  }, [items, modelBounds, onSelectItem, previewQuality, terrainState]);

  return (
    <div
      className="relative h-[min(600px,calc(100dvh-11rem))] min-h-[360px] w-full min-w-0 overflow-hidden rounded-xl bg-white md:rounded-[20px]"
      data-testid="civil-3d-viewer"
      onDoubleClick={onOpenFullscreen}
    >
      <div ref={mountRef} className="h-full w-full touch-none" data-testid="civil-3d-canvas-mount" />
      <div className="pointer-events-none absolute left-4 top-4 max-w-[calc(100%-2rem)] rounded-xl border border-white/60 bg-white/88 px-3 py-2 text-xs text-slate-700 shadow-sm backdrop-blur">
        <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">{terrainState.label}</p>
        <p className="mt-1 text-[11px] text-slate-500">{terrainState.detail}</p>
      </div>
      <div className="pointer-events-none absolute bottom-4 left-4 max-w-[calc(100%-2rem)] rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm">
        Engineer-review visualization only | visual mode does not mutate canonical geometry
      </div>
      <div className="pointer-events-none absolute right-4 top-20 rounded-full bg-slate-900/75 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white sm:top-4">
        Orbit | Pan | Zoom
      </div>
      {objectChips.length ? (
        <div className="absolute bottom-16 right-4 flex max-h-44 w-[min(260px,calc(100%-2rem))] flex-col gap-1 overflow-y-auto rounded-xl border border-slate-200 bg-white/92 p-2 shadow-sm backdrop-blur" data-testid="civil-3d-object-strip">
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
          className="pointer-events-none absolute max-w-[230px] rounded-xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
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
