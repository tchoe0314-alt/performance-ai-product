from __future__ import annotations

from html import escape
import json
from typing import Any, Dict, List

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_public_bootstrap import verify_public_review_sprint


_GALLERY_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --ink: #17211c;
      --muted: #65716b;
      --subtle: #8a948f;
      --line: #dfe5e1;
      --line-strong: #cbd4ce;
      --paper: #ffffff;
      --wash: #f4f6f4;
      --canvas: #111713;
      --green: #167a49;
      --green-soft: #e8f5ed;
      --red: #b13a3a;
      --red-soft: #faecea;
      --amber: #9a6208;
      --amber-soft: #fbf2dc;
      --blue: #236b91;
      --blue-soft: #e8f2f7;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; }
    body { margin: 0; overflow: hidden; background: var(--wash); color: var(--ink); }
    button, input, select { font: inherit; letter-spacing: 0; }
    button { cursor: pointer; }
    button:focus-visible, input:focus-visible, select:focus-visible {
      outline: 2px solid #3b82a4;
      outline-offset: 2px;
    }
    button:disabled { cursor: not-allowed; opacity: .42; }
    .app { display: grid; width: 100%; height: 100vh; grid-template-rows: auto minmax(0, 1fr); }
    .topbar {
      position: relative;
      z-index: 20;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, .97);
      box-shadow: 0 1px 0 rgba(20, 35, 27, .03);
      backdrop-filter: blur(14px);
    }
    .topbar-inner { max-width: 1600px; margin: 0 auto; padding: 14px 20px 12px; }
    .topline { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
    .brand { display: flex; min-width: 0; align-items: center; gap: 11px; }
    .brand-mark {
      display: grid;
      width: 32px;
      height: 32px;
      flex: 0 0 auto;
      place-items: center;
      border: 1px solid #244d38;
      border-radius: 7px;
      background: #173b2a;
      color: white;
      font-size: 12px;
      font-weight: 760;
    }
    h1 { margin: 0; font-size: 17px; font-weight: 720; line-height: 1.25; }
    .subtitle { margin: 3px 0 0; color: var(--muted); font-size: 12px; line-height: 1.4; }
    .progress-copy { flex: 0 0 auto; text-align: right; }
    .progress-copy strong { display: block; font-size: 13px; font-variant-numeric: tabular-nums; }
    .progress-copy span { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; }
    .progress-track { height: 3px; margin-top: 11px; overflow: hidden; background: #e8ece9; }
    .progress-bar { width: 0; height: 100%; background: var(--green); transition: width 180ms ease; }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(170px, 1.1fr) minmax(145px, .8fr) minmax(145px, .8fr) auto auto;
      gap: 8px;
      margin-top: 11px;
      align-items: center;
    }
    .field, .toolbar-button {
      min-width: 0;
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: 7px;
      background: var(--paper);
      color: var(--ink);
      padding: 8px 10px;
      font-size: 12px;
    }
    .toolbar-button { font-weight: 670; }
    .toolbar-button:hover:not(:disabled) { background: var(--wash); }
    .toolbar-button.primary { border-color: #173b2a; background: #173b2a; color: white; }
    .toolbar-button.primary:hover:not(:disabled) { background: #214c37; }
    .attestation {
      display: flex;
      grid-column: 1 / -1;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 590;
    }
    .attestation input { width: 15px; height: 15px; margin: 0; accent-color: var(--green); }
    #export-status { min-height: 15px; margin-left: auto; text-align: right; }
    .workspace {
      display: grid;
      min-height: 0;
      max-width: 1600px;
      width: 100%;
      height: 100%;
      margin: 0 auto;
      grid-template-columns: 320px minmax(0, 1fr);
      background: var(--paper);
    }
    .queue {
      display: grid;
      min-height: 0;
      grid-template-rows: auto minmax(0, 1fr);
      border-right: 1px solid var(--line);
      background: #fbfcfb;
    }
    .queue-head { border-bottom: 1px solid var(--line); padding: 13px 14px 11px; }
    .queue-title { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
    .queue-title strong { font-size: 12px; }
    .queue-title span { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
    .queue-search {
      width: 100%;
      min-height: 36px;
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      padding: 8px 10px;
      color: var(--ink);
      font-size: 12px;
    }
    .queue-list { min-height: 0; overflow: auto; overscroll-behavior: contain; }
    .queue-empty { padding: 22px 16px; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .queue-item {
      display: grid;
      width: 100%;
      grid-template-columns: 8px minmax(0, 1fr) auto;
      align-items: center;
      gap: 9px;
      border: 0;
      border-bottom: 1px solid #edf0ee;
      background: transparent;
      padding: 10px 13px;
      text-align: left;
    }
    .queue-item:hover { background: #f2f5f3; }
    .queue-item.active { background: #edf3ef; box-shadow: inset 3px 0 0 #235e42; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #aab2ad; }
    .status-dot.accept { background: var(--green); }
    .status-dot.reject { background: var(--red); }
    .status-dot.redraw { background: var(--amber); }
    .queue-copy { min-width: 0; }
    .queue-copy strong { display: block; overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
    .queue-copy small { display: block; overflow: hidden; margin-top: 3px; color: var(--muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
    .queue-confidence { color: var(--subtle); font-size: 10px; font-variant-numeric: tabular-nums; }
    .review {
      display: grid;
      min-width: 0;
      min-height: 0;
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto minmax(0, 1fr);
      background: var(--wash);
    }
    .review-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      background: var(--paper);
      padding: 11px 16px;
    }
    .review-head-copy { min-width: 0; }
    .review-head h2 { overflow: hidden; margin: 0; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
    .review-head p { overflow: hidden; margin: 3px 0 0; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
    .head-actions { display: flex; flex: 0 0 auto; gap: 6px; }
    .icon-button {
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      color: var(--ink);
      font-size: 15px;
      font-weight: 700;
    }
    .icon-button:hover:not(:disabled) { background: var(--wash); }
    .review-body {
      display: grid;
      min-width: 0;
      min-height: 0;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 14px;
      padding: 14px;
    }
    .viewport-shell {
      display: grid;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      border: 1px solid #202c25;
      border-radius: 8px;
      background: var(--canvas);
      grid-template-rows: minmax(0, 1fr) auto;
      box-shadow: 0 12px 32px rgba(24, 36, 29, .11);
    }
    .viewport { position: relative; min-height: 0; overflow: hidden; }
    .viewport svg { display: block; width: 100%; height: 100%; min-height: 360px; }
    .viewport polygon {
      fill: rgba(50, 151, 210, .06);
      stroke: rgba(92, 190, 239, .75);
      stroke-width: 1.5;
      vector-effect: non-scaling-stroke;
      pointer-events: all;
      cursor: pointer;
    }
    .viewport polygon.other { opacity: .34; }
    .viewport polygon.current { fill: rgba(38, 163, 92, .13); stroke: #34d27e; stroke-width: 2.2; opacity: 1; }
    .viewport polygon.accept { fill: rgba(29, 170, 89, .13); stroke: #44d98b; }
    .viewport polygon.reject { fill: rgba(220, 68, 68, .13); stroke: #ff7272; }
    .viewport polygon.redraw { fill: rgba(235, 165, 43, .15); stroke: #ffc95d; }
    .viewport-foot {
      display: flex;
      min-height: 43px;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #27342c;
      background: #172019;
      padding: 8px 11px;
      color: #dce5df;
    }
    .viewport-foot span { overflow: hidden; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
    .view-toggle {
      flex: 0 0 auto;
      min-height: 28px;
      border: 1px solid #45544a;
      border-radius: 6px;
      background: #202c24;
      color: white;
      padding: 5px 8px;
      font-size: 10px;
      font-weight: 670;
    }
    .decision-panel {
      min-width: 0;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      padding: 14px;
    }
    .eyebrow { margin: 0; color: var(--subtle); font-size: 10px; font-weight: 720; text-transform: uppercase; }
    .candidate-name { margin: 6px 0 0; font-size: 16px; line-height: 1.3; }
    .candidate-id { overflow: hidden; margin: 4px 0 0; color: var(--muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
    .facts { display: grid; gap: 0; margin: 14px 0; border-top: 1px solid var(--line); }
    .fact { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 9px 0; font-size: 11px; }
    .fact span { color: var(--muted); }
    .fact strong { text-align: right; font-weight: 650; }
    .decision-actions { display: grid; gap: 7px; }
    .decision-button {
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 7px;
      background: white;
      color: var(--ink);
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 690;
      text-align: left;
    }
    .decision-button:hover { background: var(--wash); }
    .decision-button.accept.active, .decision-button.accept:hover { border-color: #9fceb1; background: var(--green-soft); color: var(--green); }
    .decision-button.reject.active, .decision-button.reject:hover { border-color: #e4b6b2; background: var(--red-soft); color: var(--red); }
    .decision-button.redraw.active, .decision-button.redraw:hover { border-color: #e4c985; background: var(--amber-soft); color: var(--amber); }
    .clear-decision { width: 100%; margin-top: 7px; border: 0; background: transparent; padding: 7px; color: var(--muted); font-size: 11px; font-weight: 630; }
    .clear-decision:hover:not(:disabled) { color: var(--ink); }
    .decision-note { margin: 13px 0 0; color: var(--muted); font-size: 10px; line-height: 1.5; }
    .empty-stage { display: grid; min-height: 300px; place-items: center; color: var(--muted); font-size: 13px; }
    @media (max-width: 980px) {
      body { overflow: auto; }
      .app { height: auto; min-height: 100vh; }
      .workspace { height: auto; }
      .workspace { grid-template-columns: minmax(0, 1fr); }
      .queue { max-height: 280px; border-right: 0; border-bottom: 1px solid var(--line); }
      .review-body { grid-template-columns: minmax(0, 1fr) 250px; }
    }
    @media (max-width: 720px) {
      .topbar-inner { padding: 12px; }
      .topline { gap: 12px; }
      .progress-copy span { display: none; }
      .toolbar { grid-template-columns: 1fr 1fr; }
      .toolbar .field:first-child { grid-column: 1 / -1; }
      .toolbar-button.primary { grid-column: 1 / -1; }
      .attestation { align-items: flex-start; }
      #export-status { margin-left: 0; text-align: left; }
      .review-head { padding: 10px 12px; }
      .review-body { grid-template-columns: minmax(0, 1fr); padding: 10px; }
      .viewport svg { min-height: 320px; }
      .decision-panel { overflow: visible; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="topline">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">CV</span>
            <div>
              <h1>__TITLE__</h1>
              <p class="subtitle">Compare each proposal with its registered source frame. Nothing starts as ground truth.</p>
            </div>
          </div>
          <div class="progress-copy">
            <strong id="summary">0 reviewed</strong>
            <span>__FRAME_COUNT__ frames · __CANDIDATE_COUNT__ proposals</span>
          </div>
        </div>
        <div class="progress-track" aria-hidden="true"><div id="progress-bar" class="progress-bar"></div></div>
        <div class="toolbar">
          <input id="reviewer" class="field" autocomplete="off" placeholder="Reviewer name or ID" aria-label="Reviewer name or ID">
          <select id="geography-filter" class="field" aria-label="Filter by geography"></select>
          <select id="status-filter" class="field" aria-label="Filter by review status">
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="accept">Accepted</option>
            <option value="reject">Rejected</option>
            <option value="redraw">Needs redraw</option>
          </select>
          <button id="undo" class="toolbar-button" type="button" disabled title="Undo last decision" aria-label="Undo last decision">Undo</button>
          <button id="export" class="toolbar-button primary" type="button" disabled>Export reviewed</button>
          <label class="attestation">
            <input id="attest" type="checkbox">
            <span>I inspected every submitted decision against its registered source frame.</span>
            <span id="export-status" role="status" aria-live="polite"></span>
          </label>
        </div>
      </div>
    </header>
    <main class="workspace">
      <aside class="queue" aria-label="Review queue">
        <div class="queue-head">
          <div class="queue-title"><strong>Review queue</strong><span id="queue-count">0 items</span></div>
          <input id="queue-search" class="queue-search" type="search" placeholder="Search proposals" aria-label="Search proposals">
        </div>
        <div id="review-queue" class="queue-list" data-testid="vision-review-queue"></div>
      </aside>
      <section class="review" aria-label="Active proposal">
        <div class="review-head">
          <div class="review-head-copy">
            <h2 id="frame-title">Select a proposal</h2>
            <p id="frame-details">Source frame details appear here.</p>
          </div>
          <div class="head-actions">
            <button id="previous" class="icon-button" type="button" title="Previous proposal" aria-label="Previous proposal">&#8592;</button>
            <button id="next" class="icon-button" type="button" title="Next proposal" aria-label="Next proposal">&#8594;</button>
          </div>
        </div>
        <div id="review-body" class="review-body"></div>
      </section>
    </main>
  </div>
  <script id="review-data" type="application/json">__DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById('review-data').textContent);
    const knownStates = new Set(['accept', 'reject', 'redraw']);
    const allCandidates = data.frames.flatMap((frame, frameIndex) =>
      frame.candidates.map((candidate, candidateIndex) => ({ ...candidate, frame, frameIndex, candidateIndex }))
    );
    const candidateIds = new Set(allCandidates.map(candidate => candidate.candidate_id));
    const storageKey = `civora-vision-review:${data.review_sprint_fingerprint}`;
    let restored = {};
    try { restored = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch { restored = {}; }
    const decisions = new Map(
      Object.entries(restored.decisions || {}).filter(([candidateId, state]) => candidateIds.has(candidateId) && knownStates.has(state))
    );
    const history = [];
    let activeCandidateId = allCandidates[0]?.candidate_id || '';
    let focusProposal = true;
    let searchTerm = '';
    let geographyFilter = 'all';
    let statusFilter = 'all';

    const reviewer = document.getElementById('reviewer');
    const attest = document.getElementById('attest');
    const exportButton = document.getElementById('export');
    const undoButton = document.getElementById('undo');
    const summary = document.getElementById('summary');
    const progressBar = document.getElementById('progress-bar');
    const exportStatus = document.getElementById('export-status');
    const geographySelect = document.getElementById('geography-filter');
    const statusSelect = document.getElementById('status-filter');
    const queueSearch = document.getElementById('queue-search');
    const queue = document.getElementById('review-queue');
    const queueCount = document.getElementById('queue-count');
    const reviewBody = document.getElementById('review-body');
    const frameTitle = document.getElementById('frame-title');
    const frameDetails = document.getElementById('frame-details');
    const previousButton = document.getElementById('previous');
    const nextButton = document.getElementById('next');

    reviewer.value = typeof restored.reviewer === 'string' ? restored.reviewer : '';
    const geographies = [...new Set(data.frames.map(frame => frame.geography_id).filter(Boolean))].sort();
    geographySelect.innerHTML = '<option value="all">All locations</option>';
    for (const geography of geographies) {
      const option = document.createElement('option');
      option.value = geography;
      option.textContent = geography.replaceAll('_', ' ');
      geographySelect.appendChild(option);
    }

    function stableJson(value) {
      if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
      if (value && typeof value === 'object') {
        return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
      }
      return JSON.stringify(value);
    }

    async function sha256Hex(value) {
      const bytes = new TextEncoder().encode(stableJson(value));
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
    }

    function candidateState(candidateId) { return decisions.get(candidateId) || 'pending'; }

    function stateLabel(state) {
      return {
        accept: 'Accepted',
        pending: 'Pending',
        redraw: 'Needs redraw',
        reject: 'Rejected',
      }[state] || humanLabel(state);
    }

    function filteredCandidates() {
      const query = searchTerm.trim().toLowerCase();
      return allCandidates.filter(candidate => {
        if (geographyFilter !== 'all' && candidate.frame.geography_id !== geographyFilter) return false;
        if (statusFilter !== 'all' && candidateState(candidate.candidate_id) !== statusFilter) return false;
        if (!query) return true;
        return [candidate.label, candidate.candidate_id, candidate.frame.geography_id, candidate.frame.frame_id]
          .some(value => String(value || '').toLowerCase().includes(query));
      });
    }

    function saveProgress() {
      try {
        localStorage.setItem(storageKey, JSON.stringify({
          reviewer: reviewer.value.trim(),
          decisions: Object.fromEntries(decisions),
          saved_at: new Date().toISOString(),
        }));
      } catch {
        exportStatus.textContent = 'Progress is kept in this tab; browser storage is unavailable.';
      }
    }

    function counts() {
      const values = [...decisions.values()];
      return {
        accepted: values.filter(value => value === 'accept').length,
        rejected: values.filter(value => value === 'reject').length,
        redraw: values.filter(value => value === 'redraw').length,
        reviewed: values.filter(value => knownStates.has(value)).length,
      };
    }

    function updateSummary() {
      const current = counts();
      const pending = Math.max(0, data.candidate_count - current.reviewed);
      summary.textContent = `${current.reviewed} reviewed · ${pending} pending`;
      summary.title = `${current.accepted} accepted, ${current.rejected} rejected, ${current.redraw} need redraw`;
      progressBar.style.width = `${data.candidate_count ? current.reviewed / data.candidate_count * 100 : 0}%`;
      exportButton.textContent = current.reviewed ? `Export reviewed (${current.reviewed})` : 'Export reviewed';
      exportButton.disabled = !reviewer.value.trim() || !attest.checked || current.reviewed === 0;
      undoButton.disabled = history.length === 0;
    }

    function formatConfidence(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return 'Unknown';
      return `${Math.round(parsed * 100)}%`;
    }

    function humanLabel(value) {
      return String(value || 'unknown')
        .replaceAll('_', ' ')
        .replaceAll('-', ' ')
        .split(/\s+/)
        .filter(Boolean)
        .map((part, index, parts) => part.length === 2 && index === parts.length - 1
          ? part.toUpperCase()
          : part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
    }

    function qualityLabel(value) {
      const labels = {
        high_resolution_up_to_0_30m: 'High resolution (up to 0.30 m)',
        medium_resolution_0_31m_to_0_60m: 'Medium resolution (0.31-0.60 m)',
        low_resolution_over_0_60m: 'Low resolution (over 0.60 m)',
      };
      return labels[value] || humanLabel(value || 'quality unknown');
    }

    function setActive(candidateId, { scroll = true } = {}) {
      if (!candidateIds.has(candidateId)) return;
      activeCandidateId = candidateId;
      focusProposal = true;
      render();
      if (scroll) {
        queue.querySelector(`[data-candidate-id="${candidateId}"]`)?.scrollIntoView({ block: 'nearest' });
      }
    }

    function setDecision(candidateId, state) {
      if (!candidateIds.has(candidateId)) return;
      const previous = decisions.get(candidateId) || 'pending';
      if (previous === state) return;
      history.push({ candidateId, previous });
      if (state === 'pending') decisions.delete(candidateId);
      else decisions.set(candidateId, state);
      exportStatus.textContent = '';
      saveProgress();
      const currentList = filteredCandidates();
      if (statusFilter === 'pending' && state !== 'pending') {
        const previousIndex = currentList.findIndex(candidate => candidate.candidate_id === candidateId);
        const nextCandidate = currentList[previousIndex + 1] || currentList[previousIndex - 1];
        if (nextCandidate) activeCandidateId = nextCandidate.candidate_id;
      }
      render();
    }

    function undoLastDecision() {
      const previous = history.pop();
      if (!previous) return;
      if (previous.previous === 'pending') decisions.delete(previous.candidateId);
      else decisions.set(previous.candidateId, previous.previous);
      activeCandidateId = previous.candidateId;
      saveProgress();
      render();
    }

    function moveActive(offset) {
      const list = filteredCandidates();
      if (!list.length) return;
      const currentIndex = Math.max(0, list.findIndex(candidate => candidate.candidate_id === activeCandidateId));
      const nextIndex = (currentIndex + offset + list.length) % list.length;
      setActive(list[nextIndex].candidate_id);
    }

    function polygonBounds(points, frame) {
      if (!points.length) return `0 0 ${frame.image_width} ${frame.image_height}`;
      const xs = points.map(point => Number(point[0]));
      const ys = points.map(point => Number(point[1]));
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = Math.max(12, maxX - minX);
      const height = Math.max(12, maxY - minY);
      const size = Math.max(width * 2.6, height * 2.6, 132);
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      const left = Math.max(0, Math.min(frame.image_width - size, centerX - size / 2));
      const top = Math.max(0, Math.min(frame.image_height - size, centerY - size / 2));
      const safeSize = Math.min(size, frame.image_width, frame.image_height);
      return `${left} ${top} ${safeSize} ${safeSize}`;
    }

    function createSvgElement(name) { return document.createElementNS('http://www.w3.org/2000/svg', name); }

    function renderQueue() {
      const list = filteredCandidates();
      queue.replaceChildren();
      queueCount.textContent = `${list.length} item${list.length === 1 ? '' : 's'}`;
      if (!list.length) {
        const empty = document.createElement('div');
        empty.className = 'queue-empty';
        empty.textContent = 'No proposals match this view.';
        queue.appendChild(empty);
        return list;
      }
      if (!list.some(candidate => candidate.candidate_id === activeCandidateId)) activeCandidateId = list[0].candidate_id;
      const fragment = document.createDocumentFragment();
      for (const candidate of list) {
        const state = candidateState(candidate.candidate_id);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `queue-item${candidate.candidate_id === activeCandidateId ? ' active' : ''}`;
        button.dataset.candidateId = candidate.candidate_id;
        button.setAttribute('aria-label', `Review ${candidate.label}`);
        button.setAttribute('aria-current', candidate.candidate_id === activeCandidateId ? 'true' : 'false');
        const dot = document.createElement('span');
        dot.className = `status-dot ${state}`;
        dot.setAttribute('aria-hidden', 'true');
        const copy = document.createElement('span');
        copy.className = 'queue-copy';
        const title = document.createElement('strong');
        title.textContent = humanLabel(candidate.label || 'Building proposal');
        const detail = document.createElement('small');
        detail.textContent = `${humanLabel(candidate.frame.geography_id)} · ${stateLabel(state)}`;
        copy.append(title, detail);
        const confidence = document.createElement('span');
        confidence.className = 'queue-confidence';
        confidence.textContent = formatConfidence(candidate.confidence);
        button.append(dot, copy, confidence);
        button.addEventListener('click', () => setActive(candidate.candidate_id, { scroll: false }));
        fragment.appendChild(button);
      }
      queue.appendChild(fragment);
      return list;
    }

    function renderStage(list) {
      const candidate = allCandidates.find(item => item.candidate_id === activeCandidateId);
      reviewBody.replaceChildren();
      if (!candidate || !list.length) {
        frameTitle.textContent = 'No proposal selected';
        frameDetails.textContent = 'Adjust the review filters to continue.';
        const empty = document.createElement('div');
        empty.className = 'empty-stage';
        empty.textContent = 'No proposal matches this view.';
        reviewBody.appendChild(empty);
        previousButton.disabled = true;
        nextButton.disabled = true;
        return;
      }
      const frame = candidate.frame;
      frameTitle.textContent = humanLabel(frame.geography_id || frame.frame_id || 'Source frame');
      frameDetails.textContent = [
        frame.captured_at || 'date unknown',
        humanLabel(frame.season || 'season unknown'),
        humanLabel(frame.permanent_split || 'split unknown'),
        qualityLabel(frame.imagery_quality_band),
      ].join(' · ');
      previousButton.disabled = list.length < 2;
      nextButton.disabled = list.length < 2;

      const viewportShell = document.createElement('div');
      viewportShell.className = 'viewport-shell';
      viewportShell.dataset.testid = 'vision-review-viewport';
      const viewport = document.createElement('div');
      viewport.className = 'viewport';
      const svg = createSvgElement('svg');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', `Registered source frame for ${humanLabel(candidate.label)}`);
      svg.setAttribute('viewBox', focusProposal ? polygonBounds(candidate.points, frame) : `0 0 ${frame.image_width} ${frame.image_height}`);
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      const image = createSvgElement('image');
      image.setAttribute('href', frame.image_src);
      image.setAttribute('width', frame.image_width);
      image.setAttribute('height', frame.image_height);
      image.setAttribute('preserveAspectRatio', 'none');
      svg.appendChild(image);
      for (const frameCandidate of frame.candidates) {
        const state = candidateState(frameCandidate.candidate_id);
        const polygon = createSvgElement('polygon');
        polygon.setAttribute('points', frameCandidate.points.map(point => point.join(',')).join(' '));
        polygon.setAttribute('class', `${state}${frameCandidate.candidate_id === candidate.candidate_id ? ' current' : ' other'}`.trim());
        polygon.dataset.candidateId = frameCandidate.candidate_id;
        polygon.setAttribute('aria-label', humanLabel(frameCandidate.label || 'Building proposal'));
        polygon.addEventListener('click', () => setActive(frameCandidate.candidate_id));
        svg.appendChild(polygon);
      }
      viewport.appendChild(svg);
      const viewportFoot = document.createElement('div');
      viewportFoot.className = 'viewport-foot';
      const sourceCopy = document.createElement('span');
      sourceCopy.textContent = `${frame.frame_id} · ${Number(frame.resolution_meters || 0).toFixed(2)} m imagery`;
      const viewToggle = document.createElement('button');
      viewToggle.type = 'button';
      viewToggle.className = 'view-toggle';
      viewToggle.textContent = focusProposal ? 'Show full frame' : 'Focus proposal';
      viewToggle.addEventListener('click', () => { focusProposal = !focusProposal; renderStage(filteredCandidates()); });
      viewportFoot.append(sourceCopy, viewToggle);
      viewportShell.append(viewport, viewportFoot);

      const panel = document.createElement('aside');
      panel.className = 'decision-panel';
      panel.dataset.testid = 'vision-review-actions';
      const eyebrow = document.createElement('p');
      eyebrow.className = 'eyebrow';
      eyebrow.textContent = `${list.findIndex(item => item.candidate_id === candidate.candidate_id) + 1} of ${list.length}`;
      const name = document.createElement('h3');
      name.className = 'candidate-name';
      name.textContent = humanLabel(candidate.label || 'Building proposal');
      const id = document.createElement('p');
      id.className = 'candidate-id';
      id.textContent = candidate.candidate_id;
      const facts = document.createElement('div');
      facts.className = 'facts';
      for (const [label, value] of [
        ['Location', humanLabel(frame.geography_id)],
        ['Confidence', formatConfidence(candidate.confidence)],
        ['Dataset split', humanLabel(frame.permanent_split)],
        ['Source license', humanLabel(frame.source_license || 'not recorded')],
      ]) {
        const fact = document.createElement('div');
        fact.className = 'fact';
        const factLabel = document.createElement('span');
        factLabel.textContent = label;
        const factValue = document.createElement('strong');
        factValue.textContent = value;
        fact.append(factLabel, factValue);
        facts.appendChild(fact);
      }
      const actions = document.createElement('div');
      actions.className = 'decision-actions';
      const activeState = candidateState(candidate.candidate_id);
      for (const [state, label, shortcut] of [
        ['accept', 'Accept visible outline', 'A'],
        ['reject', 'Reject proposal', 'R'],
        ['redraw', 'Needs redraw', 'W'],
      ]) {
        const action = document.createElement('button');
        action.type = 'button';
        action.className = `decision-button ${state}${activeState === state ? ' active' : ''}`;
        action.textContent = label;
        action.dataset.action = state;
        action.setAttribute('aria-keyshortcuts', shortcut);
        action.addEventListener('click', () => setDecision(candidate.candidate_id, state));
        actions.appendChild(action);
      }
      const clear = document.createElement('button');
      clear.type = 'button';
      clear.className = 'clear-decision';
      clear.textContent = 'Clear decision';
      clear.disabled = activeState === 'pending';
      clear.addEventListener('click', () => setDecision(candidate.candidate_id, 'pending'));
      const note = document.createElement('p');
      note.className = 'decision-note';
      note.textContent = activeState === 'redraw'
        ? 'This proposal will export as rejected with a redraw-required reason; corrected geometry belongs in Civora Draw.'
        : 'Only accepted outlines become reviewer-attributed training evidence. Rejected and redraw items do not become ground truth.';
      panel.append(eyebrow, name, id, facts, actions, clear, note);
      reviewBody.append(viewportShell, panel);
    }

    function render() {
      const list = renderQueue();
      renderStage(list);
      updateSummary();
    }

    reviewer.addEventListener('input', () => { saveProgress(); updateSummary(); });
    attest.addEventListener('change', updateSummary);
    geographySelect.addEventListener('change', () => { geographyFilter = geographySelect.value; render(); });
    statusSelect.addEventListener('change', () => { statusFilter = statusSelect.value; render(); });
    queueSearch.addEventListener('input', () => { searchTerm = queueSearch.value; render(); });
    undoButton.addEventListener('click', undoLastDecision);
    previousButton.addEventListener('click', () => moveActive(-1));
    nextButton.addEventListener('click', () => moveActive(1));

    document.addEventListener('keydown', event => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target;
      if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement) return;
      const key = event.key.toLowerCase();
      if (key === 'a') setDecision(activeCandidateId, 'accept');
      else if (key === 'r') setDecision(activeCandidateId, 'reject');
      else if (key === 'w') setDecision(activeCandidateId, 'redraw');
      else if (key === 'z') undoLastDecision();
      else if (key === 'arrowright' || key === 'j') moveActive(1);
      else if (key === 'arrowleft' || key === 'k') moveActive(-1);
      else if (key === 'f') { focusProposal = !focusProposal; renderStage(filteredCandidates()); }
      else return;
      event.preventDefault();
    });

    exportButton.addEventListener('click', async () => {
      if (!globalThis.crypto?.subtle) {
        exportStatus.textContent = 'Checksum export needs a secure browser context. Serve this folder over localhost.';
        return;
      }
      const reviewed = [...decisions.entries()].map(([candidate_id, state]) => {
        const candidate = candidates.find(item => item.candidate_id === candidate_id);
        const featureLabel = humanLabel(candidate?.label || 'visible feature').toLowerCase();
        return {
          candidate_id,
          action: state === 'accept' ? 'accept' : 'reject',
          reason: state === 'accept'
            ? `Inspected against the registered source frame and accepted the visible ${featureLabel} outline.`
            : state === 'redraw'
              ? `Inspected against the registered source frame; ${featureLabel} proposal rejected because corrected geometry must be redrawn in Civora Draw.`
              : `Inspected against the registered source frame and rejected the weak ${featureLabel} proposal.`,
        };
      });
      const payload = {
        version: 'civora_public_vision_review_decisions_v1',
        review_sprint_fingerprint: data.review_sprint_fingerprint,
        reviewer_id: reviewer.value.trim(),
        source_frame_review_attested: true,
        exported_at: new Date().toISOString(),
        decisions: reviewed,
      };
      payload.decisions_fingerprint = await sha256Hex(payload);
      const blob = new Blob([JSON.stringify(payload, null, 2) + '\n'], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'vision-review-decisions.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      exportStatus.textContent = `Exported ${reviewed.length} decisions · checksum ${payload.decisions_fingerprint.slice(0, 12)}...`;
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });

    render();
  </script>
</body>
</html>
"""


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
        points = _polygon_points(safe_dict(properties.get("pixel_geometry")))
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
        source_rights = safe_dict(frame.get("source_rights"))
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
                "permanent_split": safe_str(frame.get("permanent_split")),
                "source_license": safe_str(source_rights.get("license"), "not recorded"),
                "candidates": candidates_by_frame.get(frame_id, []),
            }
        )
    data = {
        "review_sprint_fingerprint": safe_str(review_sprint.get("review_sprint_fingerprint")),
        "frames": gallery_frames,
        "candidate_count": len(candidates),
    }
    serialized = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    title = escape("Civora vision review")
    return (
        _GALLERY_TEMPLATE.replace("__TITLE__", title)
        .replace("__FRAME_COUNT__", str(len(gallery_frames)))
        .replace("__CANDIDATE_COUNT__", str(len(candidates)))
        .replace("__DATA__", serialized)
    )


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
