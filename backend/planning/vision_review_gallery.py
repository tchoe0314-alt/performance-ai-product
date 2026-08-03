from __future__ import annotations

from html import escape
import json
from typing import Any, Dict, List

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_public_bootstrap import verify_public_review_sprint


def build_public_review_gallery_html(review_sprint: Dict[str, Any], *, image_prefix: str = "images") -> str:
    validation = verify_public_review_sprint(review_sprint)
    if not validation["valid"]:
        raise ValueError("Review sprint failed verification: " + ", ".join(validation["blockers"]))
    meta = safe_dict(review_sprint.get("meta"))
    vision_report = safe_dict(meta.get("civora_vision_detection_report_v2"))
    frames = [safe_dict(item) for item in safe_list(vision_report.get("imagery_frames")) if safe_dict(item)]
    inbox = safe_dict(meta.get("candidate_review_inbox_v1"))
    candidates = [safe_dict(item) for item in safe_list(inbox.get("candidates")) if safe_dict(item)]
    candidates_by_frame: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in candidates:
        source = safe_dict(candidate.get("source_record"))
        properties = safe_dict(source.get("properties"))
        frame_id = safe_str(properties.get("imagery_frame_id") or source.get("imagery_frame_id"))
        pixel_geometry = safe_dict(properties.get("pixel_geometry"))
        points = _polygon_points(pixel_geometry)
        if not frame_id or not points:
            continue
        candidates_by_frame.setdefault(frame_id, []).append(
            {
                "candidate_id": safe_str(candidate.get("candidate_id")),
                "label": safe_str(candidate.get("label"), "Building proposal"),
                "confidence": candidate.get("confidence"),
                "points": points,
            }
        )
    gallery_frames = []
    normalized_prefix = image_prefix.strip("/")
    for frame in frames:
        asset = safe_dict(frame.get("source_asset"))
        file_name = safe_str(asset.get("file_name"))
        frame_id = safe_str(frame.get("frame_id"))
        gallery_frames.append(
            {
                "frame_id": frame_id,
                "image_src": f"{normalized_prefix}/{file_name}" if normalized_prefix else file_name,
                "image_width": int(safe_float(frame.get("image_width_px"))),
                "image_height": int(safe_float(frame.get("image_height_px"))),
                "geography_id": safe_str(frame.get("geography_id")),
                "captured_at": safe_str(frame.get("captured_at")),
                "season": safe_str(frame.get("season")),
                "imagery_quality_band": safe_str(frame.get("imagery_quality_band")),
                "resolution_meters": frame.get("resolution_meters"),
                "candidates": candidates_by_frame.get(frame_id, []),
            }
        )
    data = {
        "review_sprint_fingerprint": safe_str(review_sprint.get("review_sprint_fingerprint")),
        "frames": gallery_frames,
        "candidate_count": len(candidates),
    }
    serialized = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    title = escape("Civora public vision review sprint")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f5f7f8; color: #17202a; }}
    header {{ position: sticky; top: 0; z-index: 20; border-bottom: 1px solid #dfe5e8; background: rgba(255,255,255,.96); padding: 16px 22px; backdrop-filter: blur(12px); }}
    h1 {{ margin: 0; font-size: 18px; }}
    p {{ margin: 5px 0 0; color: #60707a; font-size: 13px; }}
    .controls {{ display: grid; grid-template-columns: minmax(180px, 1fr) auto auto; gap: 10px; margin-top: 12px; align-items: center; }}
    input, select, button {{ border: 1px solid #ccd5da; border-radius: 6px; background: white; color: #17202a; min-height: 38px; padding: 8px 10px; font: inherit; }}
    button {{ cursor: pointer; background: #17202a; color: white; font-weight: 650; }}
    button:disabled {{ cursor: not-allowed; opacity: .45; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 16px; padding: 18px; }}
    article {{ overflow: hidden; border: 1px solid #dfe5e8; border-radius: 8px; background: white; box-shadow: 0 8px 24px rgba(27,42,50,.06); }}
    .frame-head {{ display: flex; justify-content: space-between; gap: 10px; padding: 12px 14px; border-bottom: 1px solid #e6ebee; }}
    .frame-head strong {{ font-size: 13px; }}
    .frame-head span {{ color: #6b7b85; font-size: 11px; text-align: right; }}
    .image-wrap {{ position: relative; aspect-ratio: 1; background: #e8edef; }}
    .image-wrap img, .image-wrap svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .image-wrap img {{ object-fit: contain; }}
    polygon {{ fill: rgba(0,155,255,.08); stroke: #00a3ff; stroke-width: 2; vector-effect: non-scaling-stroke; }}
    polygon.accept {{ fill: rgba(26,160,86,.14); stroke: #15914b; }}
    polygon.reject {{ fill: rgba(220,53,69,.12); stroke: #d73545; }}
    .rows {{ max-height: 230px; overflow: auto; }}
    .candidate {{ display: grid; grid-template-columns: minmax(0,1fr) 110px; gap: 8px; align-items: center; padding: 9px 12px; border-top: 1px solid #edf0f2; }}
    .candidate label {{ min-width: 0; font-size: 12px; font-weight: 620; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .candidate small {{ display: block; margin-top: 2px; color: #78868e; font-weight: 500; }}
    .empty {{ padding: 13px; color: #6d7b83; font-size: 12px; }}
    .attest {{ display: flex; gap: 8px; align-items: center; font-size: 12px; font-weight: 620; }}
    .attest input {{ min-height: 0; }}
    #summary {{ font-variant-numeric: tabular-nums; font-weight: 650; }}
    #export-status {{ min-height: 16px; }}
    @media (max-width: 700px) {{ .controls {{ grid-template-columns: 1fr; }} main {{ grid-template-columns: 1fr; padding: 10px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>Compare every proposal with its registered USGS NAIP frame. Nothing starts as ground truth.</p>
    <div class="controls">
      <input id="reviewer" autocomplete="off" placeholder="Reviewer name or ID" aria-label="Reviewer name or ID">
      <label class="attest"><input id="attest" type="checkbox"> I inspected each submitted proposal against its source frame.</label>
      <button id="export" type="button" disabled>Export reviewed decisions</button>
    </div>
    <p id="summary">0 accepted / 0 rejected / {len(candidates)} pending</p>
    <p id="export-status" role="status" aria-live="polite"></p>
  </header>
  <main id="gallery"></main>
  <script id="review-data" type="application/json">{serialized}</script>
  <script>
    const data = JSON.parse(document.getElementById('review-data').textContent);
    const decisions = new Map();
    const gallery = document.getElementById('gallery');
    const reviewer = document.getElementById('reviewer');
    const attest = document.getElementById('attest');
    const exportButton = document.getElementById('export');
    const summary = document.getElementById('summary');
    const exportStatus = document.getElementById('export-status');
    function stableJson(value) {{
      if (Array.isArray(value)) return `[${{value.map(stableJson).join(',')}}]`;
      if (value && typeof value === 'object') {{
        return `{{${{Object.keys(value).sort().map(key => `${{JSON.stringify(key)}}:${{stableJson(value[key])}}`).join(',')}}}}`;
      }}
      return JSON.stringify(value);
    }}
    async function sha256Hex(value) {{
      const bytes = new TextEncoder().encode(stableJson(value));
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
    }}
    function update() {{
      const values = [...decisions.values()];
      const accepted = values.filter(value => value === 'accept').length;
      const rejected = values.filter(value => value === 'reject').length;
      summary.textContent = `${{accepted}} accepted / ${{rejected}} rejected / ${{data.candidate_count - accepted - rejected}} pending`;
      exportButton.disabled = !reviewer.value.trim() || !attest.checked || accepted + rejected === 0;
    }}
    for (const frame of data.frames) {{
      const article = document.createElement('article');
      const frameHead = document.createElement('div');
      frameHead.className = 'frame-head';
      const frameTitle = document.createElement('strong');
      frameTitle.textContent = frame.geography_id || frame.frame_id;
      const frameDetails = document.createElement('span');
      frameDetails.append(
        `${{frame.captured_at || 'date unknown'}} · ${{frame.season || 'season unknown'}}`,
        document.createElement('br'),
        frame.imagery_quality_band || 'quality unknown',
      );
      frameHead.append(frameTitle, frameDetails);
      article.appendChild(frameHead);
      const imageWrap = document.createElement('div');
      imageWrap.className = 'image-wrap';
      const image = document.createElement('img');
      image.src = frame.image_src;
      image.alt = `Registered source frame ${{frame.frame_id}}`;
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', `0 0 ${{frame.image_width}} ${{frame.image_height}}`);
      for (const candidate of frame.candidates) {{
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', candidate.points.map(point => point.join(',')).join(' '));
        polygon.dataset.candidateId = candidate.candidate_id;
        svg.appendChild(polygon);
      }}
      imageWrap.append(image, svg);
      article.appendChild(imageWrap);
      const rows = document.createElement('div');
      rows.className = 'rows';
      if (!frame.candidates.length) rows.innerHTML = '<div class="empty">No weak building proposals in this frame.</div>';
      for (const candidate of frame.candidates) {{
        const row = document.createElement('div');
        row.className = 'candidate';
        const label = document.createElement('label');
        label.textContent = candidate.label;
        const small = document.createElement('small');
        small.textContent = `Confidence ${{candidate.confidence ?? 'unknown'}} · ${{candidate.candidate_id}}`;
        label.appendChild(small);
        const select = document.createElement('select');
        select.setAttribute('aria-label', `Review ${{candidate.label}}`);
        select.innerHTML = '<option value="pending">Pending</option><option value="accept">Accept</option><option value="reject">Reject</option>';
        select.addEventListener('change', () => {{
          const value = select.value;
          decisions.set(candidate.candidate_id, value);
          const polygon = svg.querySelector(`[data-candidate-id="${{candidate.candidate_id}}"]`);
          if (polygon) polygon.setAttribute('class', value === 'pending' ? '' : value);
          update();
        }});
        row.append(label, select);
        rows.appendChild(row);
      }}
      article.appendChild(rows);
      gallery.appendChild(article);
    }}
    reviewer.addEventListener('input', update);
    attest.addEventListener('change', update);
    exportButton.addEventListener('click', async () => {{
      const reviewed = [...decisions.entries()]
        .filter(([, action]) => action === 'accept' || action === 'reject')
        .map(([candidate_id, action]) => ({{
          candidate_id,
          action,
          reason: action === 'accept'
            ? 'Inspected against the registered source frame and accepted the visible building outline.'
            : 'Inspected against the registered source frame and rejected the weak building proposal.'
        }}));
      const payload = {{
        version: 'civora_public_vision_review_decisions_v1',
        review_sprint_fingerprint: data.review_sprint_fingerprint,
        reviewer_id: reviewer.value.trim(),
        source_frame_review_attested: true,
        exported_at: new Date().toISOString(),
        decisions: reviewed,
      }};
      payload.decisions_fingerprint = await sha256Hex(payload);
      const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'vision-review-decisions.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      exportStatus.textContent = `Exported ${{reviewed.length}} decisions · checksum ${{payload.decisions_fingerprint.slice(0, 12)}}…`;
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }});
  </script>
</body>
</html>
"""


def _polygon_points(geometry: Dict[str, Any]) -> List[List[float]]:
    if safe_str(geometry.get("type")) != "Polygon":
        return []
    rings = safe_list(geometry.get("coordinates"))
    ring = safe_list(rings[0]) if rings else []
    result = []
    for point in ring:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            result.append([round(safe_float(point[0]), 4), round(safe_float(point[1]), 4)])
    return result if len(result) >= 4 else []


__all__ = ["build_public_review_gallery_html"]
