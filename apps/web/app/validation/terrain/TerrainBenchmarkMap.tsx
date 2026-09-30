const terrain = [
  [83.719, 83.895, 83.954, 83.953, 84.251, 84.562, 84.849, 85.14],
  [83.703, 83.856, 83.942, 83.99, 84.315, 84.547, 84.754, 85.038],
  [83.732, 83.798, 83.915, 84.085, 84.631, 84.686, 84.753, 84.986],
  [83.685, 83.758, 83.887, 84.035, 84.555, 84.734, 84.779, 84.946],
  [83.654, 83.723, 83.847, 83.997, 84.578, 84.78, 84.927, 84.983],
  [83.933, 83.689, 83.812, 84.072, 84.923, 85.194, 85.248, 85.429],
  [83.663, 83.623, 83.753, 83.971, 84.631, 85.099, 85.384, 85.636],
  [83.642, 83.586, 83.715, 84.037, 85.219, 85.369, 85.464, 85.558],
];

const minimum = 83.358;
const maximum = 86.005;

function terrainColor(value: number) {
  const ratio = Math.max(0, Math.min(1, (value - minimum) / (maximum - minimum)));
  const hue = 210 - ratio * 170;
  const lightness = 44 + ratio * 22;
  return `hsl(${hue} 70% ${lightness}%)`;
}

export default function TerrainBenchmarkMap() {
  return (
    <figure aria-labelledby="terrain-map-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 p-4 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">USGS 3DEP · public domain</p>
          <h2 id="terrain-map-title" className="mt-2 text-xl font-semibold text-white">Real terrain Civora processed</h2>
        </div>
        <p className="text-xs text-slate-400">32.7350–32.7356° N · 117.1614–117.1608° W</p>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_auto]">
        <svg viewBox="0 0 800 800" role="img" aria-label="Elevation heatmap rising from blue low ground in the west to tan high ground in the east" className="aspect-square w-full rounded-xl bg-slate-900">
          {terrain.flatMap((row, rowIndex) =>
            row.map((value, columnIndex) => (
              <rect
                key={`${rowIndex}-${columnIndex}`}
                x={columnIndex * 100}
                y={rowIndex * 100}
                width="101"
                height="101"
                fill={terrainColor(value)}
              />
            )),
          )}
          {[0, 1, 2, 3, 4].map((index) => (
            <path
              key={index}
              d={`M ${145 + index * 108} 0 C ${115 + index * 116} 170, ${230 + index * 86} 315, ${170 + index * 111} 470 S ${230 + index * 110} 690, ${190 + index * 115} 800`}
              fill="none"
              stroke="rgba(255,255,255,.58)"
              strokeWidth="3"
            />
          ))}
          <text x="24" y="45" fill="white" fontSize="25" fontWeight="700">Lower</text>
          <text x="687" y="45" fill="white" fontSize="25" fontWeight="700">Higher</text>
        </svg>

        <div className="flex min-w-16 flex-row items-stretch gap-3 sm:flex-col">
          <div className="min-h-12 flex-1 rounded-full bg-gradient-to-r from-blue-700 via-emerald-400 via-55% to-amber-100 sm:min-h-0 sm:w-5 sm:bg-gradient-to-t" aria-hidden="true" />
          <div className="flex justify-between text-[11px] font-medium text-slate-300 sm:h-full sm:flex-col">
            <span>86.00 m</span>
            <span>83.36 m</span>
          </div>
        </div>
      </div>

      <figcaption className="mt-4 text-sm leading-6 text-slate-300">
        This display is an 8×8 visual summary of the verified 64×64 source raster. Calculations use all 4,096 cells, not the simplified display.
      </figcaption>
    </figure>
  );
}
