"""HTML report generation for codesearch results."""

import json

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>codesearch results</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f8f9fa; --surface: #fff; --border: #dee2e6; --text: #212529;
    --muted: #6c757d; --accent: #0d6efd; --accent-light: #e7f1ff;
    --danger: #dc3545; --danger-light: #fff5f5; --warn: #fd7e14;
    --warn-light: #fff8f0; --code-bg: #f1f3f5; --match-hl: #fff3cd;
    --radius: 6px; --shadow: 0 1px 3px rgba(0,0,0,.08);
    --font-mono: 'Cascadia Code','Fira Code','Consolas','Menlo',monospace;
  }
  body { font-family: system-ui,-apple-system,sans-serif; font-size:14px;
    background:var(--bg); color:var(--text); line-height:1.5; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }

  /* Layout */
  #app { display:flex; flex-direction:column; min-height:100vh; }
  header { background:var(--surface); border-bottom:1px solid var(--border);
    padding:12px 20px; display:flex; align-items:center; gap:16px;
    position:sticky; top:0; z-index:10; }
  header h1 { font-size:16px; font-weight:700; letter-spacing:-.3px; }
  header .scan-info { font-size:12px; color:var(--muted); }
  main { flex:1; padding:16px 20px; max-width:1200px; width:100%; }

  /* Stats bar */
  .stats { display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }
  .stat { background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:10px 16px; box-shadow:var(--shadow);
    display:flex; flex-direction:column; gap:2px; min-width:120px; }
  .stat-value { font-size:22px; font-weight:700; line-height:1; }
  .stat-label { font-size:11px; color:var(--muted); text-transform:uppercase;
    letter-spacing:.5px; }
  .stat.danger .stat-value { color:var(--danger); }
  .stat.warn .stat-value { color:var(--warn); }

  /* Controls */
  .controls { display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;
    align-items:center; }
  .controls input[type=text] { border:1px solid var(--border); border-radius:var(--radius);
    padding:6px 10px; font-size:13px; width:220px; background:var(--surface); color:var(--text); }
  .controls input[type=text]:focus { outline:none; border-color:var(--accent);
    box-shadow:0 0 0 3px var(--accent-light); }
  .controls select { border:1px solid var(--border); border-radius:var(--radius);
    padding:6px 8px; font-size:13px; background:var(--surface); color:var(--text);
    cursor:pointer; }
  .view-toggle { display:flex; border:1px solid var(--border); border-radius:var(--radius);
    overflow:hidden; margin-left:auto; }
  .view-toggle button { background:var(--surface); border:none; padding:6px 14px;
    font-size:13px; cursor:pointer; color:var(--muted); transition:background .15s; }
  .view-toggle button.active { background:var(--accent); color:#fff; }
  .view-toggle button:hover:not(.active) { background:var(--bg); }

  /* Sections */
  .section { background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); margin-bottom:8px; box-shadow:var(--shadow);
    overflow:hidden; }
  .section-header { display:flex; align-items:center; gap:10px; padding:10px 14px;
    cursor:pointer; user-select:none; border-bottom:1px solid transparent;
    transition:background .1s; }
  .section-header:hover { background:var(--bg); }
  .section-header.open { border-bottom-color:var(--border); }
  .section-header .chevron { font-size:10px; color:var(--muted); transition:transform .2s;
    flex-shrink:0; }
  .section-header.open .chevron { transform:rotate(90deg); }
  .section-title { font-weight:600; font-size:13px; font-family:var(--font-mono); }
  .section-subtitle { font-size:12px; color:var(--muted); }
  .badge { background:var(--accent); color:#fff; border-radius:10px; padding:1px 7px;
    font-size:11px; font-weight:600; margin-left:auto; flex-shrink:0; }
  .badge.danger { background:var(--danger); }
  .section-body { display:none; }
  .section-body.open { display:block; }

  /* Match list */
  .match { border-bottom:1px solid var(--border); }
  .match:last-child { border-bottom:none; }
  .match-header { display:flex; align-items:baseline; gap:8px; padding:8px 14px;
    cursor:pointer; transition:background .1s; }
  .match-header:hover { background:var(--bg); }
  .match-loc { font-family:var(--font-mono); font-size:12px; color:var(--accent);
    flex-shrink:0; white-space:nowrap; }
  .match-tag { font-family:var(--font-mono); font-size:11px; color:#fff;
    background:var(--muted); border-radius:3px; padding:1px 5px; flex-shrink:0; }
  .match-text { font-family:var(--font-mono); font-size:12px; color:var(--text);
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; }
  .match-toggle { font-size:11px; color:var(--muted); flex-shrink:0; }

  /* Code context */
  .match-context { display:none; background:var(--code-bg);
    border-top:1px solid var(--border); overflow:auto; }
  .match-context.open { display:block; }
  .match-context table { border-collapse:collapse; width:100%; font-family:var(--font-mono);
    font-size:12px; }
  .match-context td { padding:1px 0; white-space:pre; }
  .match-context .ln { padding:1px 12px; color:var(--muted); text-align:right;
    user-select:none; border-right:1px solid var(--border); min-width:44px; }
  .match-context .src { padding:1px 12px; }
  .match-context tr.hl td { background:var(--match-hl); }
  .match-context tr.hl .src { font-weight:600; }

  /* Empty state */
  .empty { text-align:center; padding:48px; color:var(--muted); }
  .empty strong { display:block; font-size:16px; margin-bottom:6px; color:var(--text); }

  /* Hidden */
  .hidden { display:none !important; }
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>codesearch</h1>
    <div class="scan-info" id="scan-info"></div>
  </header>
  <main>
    <div class="stats" id="stats"></div>
    <div class="controls">
      <input type="text" id="filter-text" placeholder="Filter matches…" autocomplete="off">
      <select id="filter-rule"><option value="">All rules</option></select>
      <select id="filter-file"><option value="">All files</option></select>
      <div class="view-toggle">
        <button id="btn-by-rule" class="active" onclick="setView('rule')">By Rule</button>
        <button id="btn-by-file" onclick="setView('file')">By File</button>
      </div>
    </div>
    <div id="results-by-rule"></div>
    <div id="results-by-file" class="hidden"></div>
    <div id="empty-state" class="empty hidden">
      <strong>No matches</strong>
      <span>Try adjusting the filter.</span>
    </div>
  </main>
</div>
<script>
const DATA = __DATA__;

let currentView = 'rule';
let filterText = '';
let filterRule = '';
let filterFile = '';

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  const d = DATA;
  document.getElementById('scan-info').textContent =
    'Scanned: ' + d.summary.paths.join(', ') +
    (d.summary.generated_at ? '  ·  ' + d.summary.generated_at : '');

  renderStats();
  populateFilters();
  renderAll();

  document.getElementById('filter-text').addEventListener('input', e => {
    filterText = e.target.value.toLowerCase();
    renderAll();
  });
  document.getElementById('filter-rule').addEventListener('change', e => {
    filterRule = e.target.value;
    renderAll();
  });
  document.getElementById('filter-file').addEventListener('change', e => {
    filterFile = e.target.value;
    renderAll();
  });
}

// ── Stats ─────────────────────────────────────────────────────────────────────

function renderStats() {
  const s = DATA.summary;
  const el = document.getElementById('stats');
  el.innerHTML = `
    <div class="stat danger">
      <span class="stat-value">${s.total}</span>
      <span class="stat-label">Matches</span>
    </div>
    <div class="stat">
      <span class="stat-value">${s.files}</span>
      <span class="stat-label">Files</span>
    </div>
    <div class="stat warn">
      <span class="stat-value">${s.rules}</span>
      <span class="stat-label">Rules</span>
    </div>`;
}

// ── Filters ───────────────────────────────────────────────────────────────────

function populateFilters() {
  const rules = [...new Set(DATA.results.map(r => r.capture))].filter(Boolean).sort();
  const files = [...new Set(DATA.results.map(r => r.file))].sort();
  const ruleEl = document.getElementById('filter-rule');
  const fileEl = document.getElementById('filter-file');
  rules.forEach(r => {
    const o = document.createElement('option');
    o.value = r; o.textContent = r;
    ruleEl.appendChild(o);
  });
  files.forEach(f => {
    const o = document.createElement('option');
    o.value = f; o.textContent = f;
    fileEl.appendChild(o);
  });
}

// ── Filtering ─────────────────────────────────────────────────────────────────

function filteredResults() {
  return DATA.results.filter(r => {
    if (filterRule && r.capture !== filterRule) return false;
    if (filterFile && r.file !== filterFile) return false;
    if (filterText) {
      const haystack = (r.file + r.text + r.capture).toLowerCase();
      if (!haystack.includes(filterText)) return false;
    }
    return true;
  });
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function setView(v) {
  currentView = v;
  document.getElementById('btn-by-rule').classList.toggle('active', v === 'rule');
  document.getElementById('btn-by-file').classList.toggle('active', v === 'file');
  document.getElementById('results-by-rule').classList.toggle('hidden', v !== 'rule');
  document.getElementById('results-by-file').classList.toggle('hidden', v !== 'file');
}

function renderAll() {
  const results = filteredResults();
  renderByRule(results);
  renderByFile(results);
  document.getElementById('empty-state').classList.toggle('hidden', results.length > 0);
}

function groupBy(results, key) {
  const groups = {};
  for (const r of results) {
    const k = r[key] || '(unlabeled)';
    (groups[k] = groups[k] || []).push(r);
  }
  return groups;
}

function renderByRule(results) {
  const container = document.getElementById('results-by-rule');
  const groups = groupBy(results, 'capture');
  const keys = Object.keys(groups).sort();
  if (keys.length === 0) { container.innerHTML = ''; return; }
  container.innerHTML = keys.map(rule =>
    renderSection(rule, groups[rule], r => matchRow(r, 'file'))
  ).join('');
  attachToggleHandlers(container);
}

function renderByFile(results) {
  const container = document.getElementById('results-by-file');
  const groups = groupBy(results, 'file');
  const keys = Object.keys(groups).sort();
  if (keys.length === 0) { container.innerHTML = ''; return; }
  container.innerHTML = keys.map(file =>
    renderSection(file, groups[file], r => matchRow(r, 'rule'))
  ).join('');
  attachToggleHandlers(container);
}

function renderSection(title, results, rowFn) {
  const id = 'sec-' + Math.random().toString(36).slice(2);
  const rows = results.map(rowFn).join('');
  return `
<div class="section">
  <div class="section-header" data-target="${id}">
    <span class="chevron">&#9654;</span>
    <span class="section-title">${esc(title)}</span>
    <span class="badge">${results.length}</span>
  </div>
  <div class="section-body" id="${id}">
    ${rows}
  </div>
</div>`;
}

function matchRow(r, labelMode) {
  const id = 'ctx-' + Math.random().toString(36).slice(2);
  const hasCtx = r.context_before.length + r.context_after.length > 0;
  const label = labelMode === 'file' ? esc(r.file) : (r.capture ? `<span class="match-tag">${esc(r.capture)}</span>` : '');
  const loc = labelMode === 'file'
    ? `<span class="match-loc">${esc(r.file)}:${r.line}:${r.col}</span>`
    : `<span class="match-loc">:${r.line}:${r.col}</span>`;
  const tagSpan = labelMode === 'rule' ? '' : (r.capture ? `<span class="match-tag">${esc(r.capture)}</span>` : '');

  return `
<div class="match">
  <div class="match-header" ${hasCtx ? `data-ctx="${id}"` : ''}>
    ${loc}
    ${tagSpan}
    <span class="match-text">${esc(r.text.trim())}</span>
    ${hasCtx ? `<span class="match-toggle">&#9660;</span>` : ''}
  </div>
  ${hasCtx ? `<div class="match-context" id="${id}">${renderContext(r)}</div>` : ''}
</div>`;
}

function renderContext(r) {
  const startLine = r.context_start_line;
  const matchLine = r.line;
  const matchLineText = r.context_match_line !== undefined ? r.context_match_line : r.text;
  const lines = [...r.context_before, matchLineText, ...r.context_after];
  const rows = lines.map((line, i) => {
    const ln = startLine + i;
    const isMatch = ln === matchLine;
    return `<tr${isMatch ? ' class="hl"' : ''}><td class="ln">${ln}</td><td class="src">${esc(line)}</td></tr>`;
  }).join('');
  return `<table>${rows}</table>`;
}

// ── Event delegation ──────────────────────────────────────────────────────────

function attachToggleHandlers(container) {
  container.querySelectorAll('.section-header').forEach(h => {
    h.addEventListener('click', () => {
      const body = document.getElementById(h.dataset.target);
      const open = body.classList.toggle('open');
      h.classList.toggle('open', open);
    });
  });
  container.querySelectorAll('.match-header[data-ctx]').forEach(h => {
    h.addEventListener('click', e => {
      const ctx = document.getElementById(h.dataset.ctx);
      if (ctx) ctx.classList.toggle('open');
    });
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

init();
</script>
</body>
</html>"""


def generate_html(data: dict) -> str:
    """Embed scan data into the dashboard HTML template."""
    json_str = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__DATA__", json_str)
