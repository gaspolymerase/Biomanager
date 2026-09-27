// qPCR block: paste the instrument's export (any columns: Well, Sample,
// Target, Ct or Cq are found by name), pick the reference gene and the
// control sample, and get relative expression by the ΔΔCt method (Livak &
// Schmittgen 2001): mean Ct per sample and target, ΔCt against the
// reference, ΔΔCt against the control, fold change 2^−ΔΔCt with the range
// from the propagated SD. Replicates more than 0.5 cycles apart are
// flagged. The fold changes are plotted per target, one bar per sample.

import { ask, debounce, el, escapeHtml, fmt, isNum, parseDelimited, toNumber } from '../util.js';
import { mean, sd, summary, compare } from './stats.js';
import { renderPlot } from './plot.js';

export function defaultQpcr() {
  return { title: '', rows: [], reference: '', control: '', plotTarget: '' };
}

const HEADERS = {
  well: /^(well|pos(ition)?)$/i,
  sample: /^(sample( ?name)?|name)$/i,
  target: /^(target( ?name)?|detector|gene|assay)$/i,
  ct: /^(c[tq]|ct mean|cq mean|c[tq] value|crt)$/i,
};

export function parseExport(text) {
  const grid = parseDelimited(text).map((r) => r.map((v) => v.trim()));
  // The header is the first row naming a sample, target and Ct column;
  // instrument exports put a few lines of settings above it.
  let headerAt = -1;
  let idx = {};
  for (let i = 0; i < Math.min(grid.length, 60); i++) {
    const found = {};
    grid[i].forEach((h, j) => {
      for (const [key, re] of Object.entries(HEADERS)) if (found[key] === undefined && re.test(h)) found[key] = j;
    });
    if (found.sample !== undefined && found.target !== undefined && found.ct !== undefined) { headerAt = i; idx = found; break; }
  }
  if (headerAt < 0) {
    // No header: assume sample, target, Ct (optionally with the well first).
    return grid.filter((r) => r.length >= 3).map((r) => {
      const offset = r.length >= 4 ? 1 : 0;
      return { well: offset ? r[0] : '', sample: r[offset], target: r[offset + 1], ct: r[offset + 2] };
    }).filter((r) => r.sample && r.target);
  }
  return grid.slice(headerAt + 1).filter((r) => r[idx.sample] && r[idx.target]).map((r) => ({
    well: idx.well !== undefined ? r[idx.well] : '', sample: r[idx.sample], target: r[idx.target],
    ct: isNum(r[idx.ct]) ? r[idx.ct] : '',
  }));
}

export function analyse(data) {
  const rows = (data.rows || []).filter((r) => r.sample && r.target);
  const samples = [...new Set(rows.map((r) => r.sample))];
  const targets = [...new Set(rows.map((r) => r.target))];
  const cell = new Map();
  for (const r of rows) {
    const key = `${r.sample}\u0000${r.target}`;
    if (!cell.has(key)) cell.set(key, []);
    const v = toNumber(r.ct);
    if (Number.isFinite(v)) cell.get(key).push(v);
  }
  const stat = (s, t) => {
    const cts = cell.get(`${s}\u0000${t}`) || [];
    return { cts, mean: mean(cts), sd: cts.length > 1 ? sd(cts) : 0, n: cts.length };
  };
  const ref = data.reference && targets.includes(data.reference) ? data.reference : '';
  const ctrl = data.control && samples.includes(data.control) ? data.control : '';
  const results = [];
  if (ref && ctrl) {
    for (const t of targets) {
      if (t === ref) continue;
      const c = stat(ctrl, t);
      const cr = stat(ctrl, ref);
      const dCtCtrl = c.mean - cr.mean;
      for (const s of samples) {
        const x = stat(s, t);
        const xr = stat(s, ref);
        const dCt = x.mean - xr.mean;
        const ddCt = dCt - dCtCtrl;
        const sdD = Math.sqrt(x.sd ** 2 + xr.sd ** 2);
        // Per replicate, against the mean reference: points for the plot.
        const reps = x.cts.map((ct) => 2 ** -((ct - xr.mean) - dCtCtrl));
        results.push({ sample: s, target: t, ct: x.mean, refCt: xr.mean, dCt, ddCt, fold: 2 ** -ddCt, lo: 2 ** -(ddCt + sdD), hi: 2 ** -(ddCt - sdD), sd: sdD, reps });
      }
    }
  }
  const flags = [];
  for (const s of samples) for (const t of targets) {
    const st = stat(s, t);
    if (st.n > 1 && Math.max(...st.cts) - Math.min(...st.cts) > 0.5) flags.push(`${s} · ${t}: replicates span ${fmt(Math.max(...st.cts) - Math.min(...st.cts), 2)} cycles`);
    if (st.n === 0) flags.push(`${s} · ${t}: no Ct (undetermined)`);
  }
  return { samples, targets, stat, results, ref, ctrl, flags };
}

export function mountQpcr(host, ctx) {
  let data = { ...defaultQpcr(), ...(ctx.data || {}) };
  let editable = ctx.editable;
  const commit = debounce(() => ctx.commit(JSON.parse(JSON.stringify(data))), 300);
  const root = el('div', { class: 'nb-qpcr' });
  host.appendChild(root);
  let showRaw = !(data.rows || []).length;

  function render() {
    if (!data.reference && (data.rows || []).length) {
      const targets = [...new Set(data.rows.map((r) => r.target))];
      data.reference = targets.find((t) => /gapdh|actb|b-?actin|18s|rplp0|hprt|tbp|ubc|ppia|b2m/i.test(t)) || '';
    }
    const a = analyse(data);
    const dis = editable ? '' : ' disabled';
    const opt = (list, sel) => `<option value="">—</option>${list.map((x) => `<option${x === sel ? ' selected' : ''}>${escapeHtml(x)}</option>`).join('')}`;
    const plotTargets = a.targets.filter((t) => t !== a.ref);
    const plotTarget = plotTargets.includes(data.plotTarget) ? data.plotTarget : plotTargets[0];
    root.innerHTML = `
      <div class="nb-sheet-toolbar">
        <input class="nb-sheet-title" data-f="title" value="${escapeHtml(data.title || '')}" placeholder="qPCR run"${dis}>
        <label>Reference gene <select data-f="reference"${dis}>${opt(a.targets, a.ref || data.reference)}</select></label>
        <label>Control sample <select data-f="control"${dis}>${opt(a.samples, a.ctrl)}</select></label>
        <button type="button" class="nb-mini" data-act="raw">${showRaw ? 'Hide' : 'Show'} Ct values (${(data.rows || []).length})</button>
      </div>
      ${showRaw ? `
        ${editable ? `<div class="nb-plate-paste"><textarea rows="3" placeholder="Paste the export from the instrument (with its Sample, Target and Ct/Cq columns), or three columns: sample, target, Ct."></textarea><button type="button" class="nb-mini" data-act="paste">Read</button>${(data.rows || []).length ? '<button type="button" class="nb-mini" data-act="clear">Clear</button>' : ''}</div>` : ''}
        ${(data.rows || []).length ? `<div class="nb-sheet-scroll nb-qpcr-raw"><table class="nb-stats-table"><thead><tr><th>Well</th><th>Sample</th><th>Target</th><th>Ct</th></tr></thead><tbody>${data.rows.map((r, i) => `<tr data-i="${i}"><td>${escapeHtml(r.well || '')}</td><td><input data-r="sample" value="${escapeHtml(r.sample)}"${dis}></td><td><input data-r="target" value="${escapeHtml(r.target)}"${dis}></td><td><input data-r="ct" value="${escapeHtml(r.ct)}" size="6"${dis}></td></tr>`).join('')}</tbody></table></div>` : ''}` : ''}
      ${a.flags.length ? `<ul class="nb-qpcr-flags">${a.flags.slice(0, 8).map((f) => `<li class="nb-warn">${escapeHtml(f)}</li>`).join('')}${a.flags.length > 8 ? `<li class="nb-muted">and ${a.flags.length - 8} more</li>` : ''}</ul>` : ''}
      ${a.results.length ? `
        <div class="nb-sheet-scroll"><table class="nb-stats-table"><thead><tr><th>Target</th><th>Sample</th><th>Ct</th><th>${escapeHtml(a.ref)} Ct</th><th>ΔCt</th><th>ΔΔCt</th><th>Fold change</th><th>range (±SD)</th></tr></thead>
        <tbody>${a.results.map((r) => `<tr><td>${escapeHtml(r.target)}</td><th>${escapeHtml(r.sample)}${r.sample === a.ctrl ? ' <span class="nb-muted">(control)</span>' : ''}</th><td>${fmt(r.ct)}</td><td>${fmt(r.refCt)}</td><td>${fmt(r.dCt)}</td><td>${fmt(r.ddCt)}</td><td><b>${fmt(r.fold)}</b></td><td>${fmt(r.lo)} – ${fmt(r.hi)}</td></tr>`).join('')}</tbody></table></div>
        <div class="nb-sheet-controls"><label>Plot <select data-f="plotTarget">${plotTargets.map((t) => `<option${t === plotTarget ? ' selected' : ''}>${escapeHtml(t)}</option>`).join('')}</select></label></div>
        <div class="nb-plot-host nb-qpcr-plot"></div>`
        : (a.samples.length ? '<p class="nb-muted">Pick the reference gene and the control sample for ΔΔCt.</p>' : '')}`;
    if (a.results.length) {
      const groups = a.results.filter((r) => r.target === plotTarget).map((r) => ({ name: r.sample, values: r.reps, summary: summary(r.reps) }));
      const draw = () => renderPlot(root.querySelector('.nb-qpcr-plot'), {
        kind: 'groups', type: 'bar', groups, error: 'sd', yLabel: `${plotTarget} relative expression (2^−ΔΔCt)`,
        comparisons: compare(groups, 'welch', a.ctrl).comparisons,
      }, { title: plotTarget });
      if (root.isConnected) draw(); else requestAnimationFrame(draw);
    }
  }

  root.addEventListener('change', (event) => {
    const f = event.target.dataset.f;
    if (f && event.target.tagName === 'SELECT') { data[f] = event.target.value; commit(); render(); }
  });
  root.addEventListener('input', (event) => {
    const t = event.target;
    if (t.dataset.f === 'title') { data.title = t.value; commit(); return; }
    if (t.dataset.r) {
      data.rows[Number(t.closest('tr').dataset.i)][t.dataset.r] = t.value;
      commit();
      clearTimeout(root._t);
      root._t = setTimeout(render, 700);
    }
  });
  root.addEventListener('click', async (event) => {
    const b = event.target.closest('button');
    if (!b) return;
    if (b.dataset.act === 'raw') { showRaw = !showRaw; render(); }
    if (b.dataset.act === 'paste') {
      const rows = parseExport(root.querySelector('textarea').value);
      if (!rows.length) { ask.alert('No sample, target and Ct columns found in that text.'); return; }
      data.rows = rows;
      showRaw = false;
      commit(); render();
    }
    if (b.dataset.act === 'clear' && (await ask.confirm('Clear the Ct values?', { danger: true }))) { data.rows = []; commit(); render(); }
  });

  render();
  return {
    update(next) { data = { ...defaultQpcr(), ...(next || {}) }; render(); },
    destroy() { commit.flush(); },
  };
}
