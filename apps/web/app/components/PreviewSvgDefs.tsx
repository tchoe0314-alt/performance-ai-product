export function PreviewSvgDefs() {
  return (
    <defs>
      <filter id="plan-ink-soften" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="0" dy="0.08" stdDeviation="0.08" floodColor="rgba(15,23,42,0.18)" />
      </filter>
      <pattern id="cad-hatch-diagonal" patternUnits="userSpaceOnUse" width="2.4" height="2.4" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="2.4" stroke="rgba(15,23,42,0.34)" strokeWidth="0.16" />
      </pattern>
      <pattern id="cad-building-poche" patternUnits="userSpaceOnUse" width="3.2" height="3.2" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="3.2" stroke="rgba(15,23,42,0.16)" strokeWidth="0.12" />
      </pattern>
      <pattern id="cad-asphalt-light" patternUnits="userSpaceOnUse" width="3.4" height="3.4">
        <path d="M 0 3.4 L 3.4 0" stroke="rgba(51,65,85,0.08)" strokeWidth="0.12" />
        <path d="M 1.7 3.4 L 3.4 1.7" stroke="rgba(51,65,85,0.06)" strokeWidth="0.1" />
      </pattern>
      <pattern id="cad-hatch-water" patternUnits="userSpaceOnUse" width="4.4" height="2.6">
        <path d="M 0 1.3 C 1.1 0.3 2.2 2.3 3.3 1.3 S 5.5 1.3 6.6 1.3" fill="none" stroke="rgba(2,132,199,0.42)" strokeWidth="0.18" />
      </pattern>
      <pattern id="cad-hatch-landscape" patternUnits="userSpaceOnUse" width="3.6" height="3.6">
        <path d="M 0 3.2 L 3.2 0" stroke="rgba(22,101,52,0.34)" strokeWidth="0.14" />
        <circle cx="2.8" cy="2.8" r="0.22" fill="rgba(22,101,52,0.34)" />
      </pattern>
      <marker id="survey-flow-arrow" viewBox="0 0 4 4" refX="3.5" refY="2" markerWidth="2.6" markerHeight="2.6" orient="auto">
        <path d="M 0 0 L 4 2 L 0 4 z" fill="#64748b" opacity="0.72" />
      </marker>
    </defs>
  );
}
