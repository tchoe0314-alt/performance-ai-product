"use client";

type CivoraPerfEntry = {
  label: string;
  durationMs: number;
  startedAt: number;
  endedAt: number;
  metadata?: Record<string, string | number | boolean | null>;
};

type CivoraPerfWindow = Window & {
  __civoraPerf?: {
    entries: CivoraPerfEntry[];
    last: Record<string, CivoraPerfEntry>;
  };
};

const MAX_ENTRIES = 80;

function getPerfStore() {
  if (typeof window === "undefined") return null;
  const perfWindow = window as CivoraPerfWindow;
  if (!perfWindow.__civoraPerf) {
    perfWindow.__civoraPerf = { entries: [], last: {} };
  }
  return perfWindow.__civoraPerf;
}

export function markCivoraInteraction() {
  if (typeof performance === "undefined") return Date.now();
  return performance.now();
}

function measureCivoraInteraction(
  label: string,
  startedAt: number,
  metadata?: CivoraPerfEntry["metadata"],
) {
  if (typeof performance === "undefined") return null;
  const endedAt = performance.now();
  const entry: CivoraPerfEntry = {
    label,
    durationMs: Math.round((endedAt - startedAt) * 10) / 10,
    startedAt,
    endedAt,
    metadata,
  };
  const store = getPerfStore();
  if (store) {
    store.entries.push(entry);
    if (store.entries.length > MAX_ENTRIES) store.entries.shift();
    store.last[label] = entry;
  }
  if (process.env.NODE_ENV !== "production") {
    console.info("[civora-perf]", entry);
  }
  return entry;
}

export function measureCivoraInteractionAfterPaint(
  label: string,
  startedAt: number,
  metadata?: CivoraPerfEntry["metadata"],
) {
  if (typeof window === "undefined") return;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      measureCivoraInteraction(label, startedAt, metadata);
    });
  });
}
