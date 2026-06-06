import { useEffect, useRef, useState } from "react";
import type { Preview3DItem } from "../types";

export default function Preview3DCanvas({
  items,
  interactive,
  previewQuality = "standard",
  onOpenFullscreen,
}: {
  items: Preview3DItem[];
  interactive: boolean;
  previewQuality?: "standard" | "high";
  onOpenFullscreen?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [rotation, setRotation] = useState({ x: 0.75, z: -0.8 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const width = parent.clientWidth;
    const height = parent.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!items.length) {
      ctx.fillStyle = "#94a3b8";
      ctx.font = "14px ui-sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No geometry to render yet.", width / 2, height / 2);
      return;
    }

    const minX = Math.min(...items.map((item) => item.x));
    const minY = Math.min(...items.map((item) => item.y));
    const maxX = Math.max(...items.map((item) => item.x + item.w));
    const maxY = Math.max(...items.map((item) => item.y + item.h));
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const scale = Math.min(width / spanX, height / spanY) * 0.65;
    const centerX = width / 2;
    const centerY = height / 2 + 20;

    const project = (x: number, y: number, z: number) => {
      const cx = x - (minX + spanX / 2);
      const cy = y - (minY + spanY / 2);
      const cosZ = Math.cos(rotation.z);
      const sinZ = Math.sin(rotation.z);
      const rx = cx * cosZ - cy * sinZ;
      const ry = cx * sinZ + cy * cosZ;
      const cosX = Math.cos(rotation.x);
      const sinX = Math.sin(rotation.x);
      const ry2 = ry * cosX - z * sinX;
      return {
        x: centerX + rx * scale,
        y: centerY + ry2 * scale,
      };
    };

    const highQuality = previewQuality === "high";
    const layerStyles = (layer: string) => {
      const key = layer.toUpperCase();
      if (!highQuality) {
        return {
          top: itemColorFallback(key, "#dbe5ff"),
          sideDark: key === "BUILDING" ? "#94a3b8" : "#cbd5f5",
          sideLight: key === "BUILDING" ? "#bfc7d4" : "#dbe5ff",
        };
      }
      if (key === "BUILDING") {
        return { top: "#334155", sideDark: "#1f2937", sideLight: "#475569" };
      }
      if (key === "ROAD" || key === "PARKING") {
        return { top: "#3f4652", sideDark: "#252b34", sideLight: "#5b6472" };
      }
      if (key === "DRAINAGE" || key === "WATER") {
        return { top: "#38bdf8", sideDark: "#0369a1", sideLight: "#7dd3fc" };
      }
      if (key === "UTILITY") {
        return { top: "#8b5cf6", sideDark: "#5b21b6", sideLight: "#a78bfa" };
      }
      if (key === "LANDSCAPE" || key === "TERRAIN") {
        return { top: "#86efac", sideDark: "#16a34a", sideLight: "#bbf7d0" };
      }
      return { top: "#cbd5e1", sideDark: "#94a3b8", sideLight: "#e2e8f0" };
    };

    ctx.fillStyle = highQuality ? "#f8fafc" : "#eef2f7";
    ctx.fillRect(0, 0, width, height);

    const drawFace = (points: { x: number; y: number }[], color: string) => {
      ctx.beginPath();
      points.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "rgba(15,23,42,0.15)";
      ctx.stroke();
    };
    const itemColorFallback = (layer: string, fallback: string) => {
      if (layer === "BUILDING") return "#bfc7d4";
      if (layer === "ROAD" || layer === "PARKING") return "#cbd5e1";
      if (layer === "DRAINAGE" || layer === "WATER") return "#bfdbfe";
      if (layer === "UTILITY") return "#e9d5ff";
      if (layer === "LANDSCAPE" || layer === "TERRAIN") return "#dcfce7";
      return fallback;
    };

    const sorted = [...items].sort((a, b) => a.x + a.y - (b.x + b.y));
    for (const item of sorted) {
      const baseZ = item.z ?? 0;
      const topZ = baseZ + item.height;
      const base = [
        project(item.x, item.y, baseZ),
        project(item.x + item.w, item.y, baseZ),
        project(item.x + item.w, item.y + item.h, baseZ),
        project(item.x, item.y + item.h, baseZ),
      ];
      const top = [
        project(item.x, item.y, topZ),
        project(item.x + item.w, item.y, topZ),
        project(item.x + item.w, item.y + item.h, topZ),
        project(item.x, item.y + item.h, topZ),
      ];
      const style = layerStyles(item.layer);
      drawFace([base[0], base[1], top[1], top[0]], style.sideDark);
      drawFace([base[1], base[2], top[2], top[1]], style.sideLight);
      drawFace([top[0], top[1], top[2], top[3]], highQuality ? style.top : item.color || style.top);
      if (highQuality && item.layer === "BUILDING") {
        const ridgeA = project(item.x + item.w * 0.18, item.y + item.h * 0.5, topZ + item.height * 0.05);
        const ridgeB = project(item.x + item.w * 0.82, item.y + item.h * 0.5, topZ + item.height * 0.05);
        ctx.beginPath();
        ctx.moveTo(ridgeA.x, ridgeA.y);
        ctx.lineTo(ridgeB.x, ridgeB.y);
        ctx.strokeStyle = "rgba(255,255,255,0.42)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      if (highQuality && (item.layer === "ROAD" || item.layer === "PARKING")) {
        const midA = project(item.x + item.w * 0.15, item.y + item.h * 0.5, topZ + 0.04);
        const midB = project(item.x + item.w * 0.85, item.y + item.h * 0.5, topZ + 0.04);
        ctx.beginPath();
        ctx.moveTo(midA.x, midA.y);
        ctx.lineTo(midB.x, midB.y);
        ctx.strokeStyle = "rgba(248,250,252,0.55)";
        ctx.setLineDash(item.layer === "PARKING" ? [2, 3] : [6, 5]);
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }, [items, previewQuality, rotation]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !interactive) return;
    const onPointerDown = (event: PointerEvent) => {
      dragRef.current = { x: event.clientX, y: event.clientY };
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragRef.current) return;
      const dx = event.clientX - dragRef.current.x;
      const dy = event.clientY - dragRef.current.y;
      dragRef.current = { x: event.clientX, y: event.clientY };
      setRotation((prev) => ({
        x: Math.max(0.2, Math.min(1.2, prev.x + dy * 0.005)),
        z: prev.z + dx * 0.005,
      }));
    };
    const onPointerUp = () => {
      dragRef.current = null;
    };
    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      canvas.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [interactive]);

  return (
    <div
      className="relative h-[600px] w-full overflow-hidden rounded-[20px] bg-white"
      onDoubleClick={onOpenFullscreen}
    >
      <canvas ref={canvasRef} className="h-full w-full" />
      {interactive ? (
        <div className="pointer-events-none absolute right-4 top-4 rounded-full bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
          Drag to rotate
        </div>
      ) : null}
    </div>
  );
}
