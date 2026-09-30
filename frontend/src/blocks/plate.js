// Plate reader block: a 6- to 384-well plate as a heatmap of readings, a
// layout (blanks, standards with their concentrations, samples with a
// dilution factor), and the analysis — blank-subtracted means, a standard
// curve fitted by least squares (linear, or on log–log axes), and each
// sample's concentration read off the curve.
//
// data = { format, values: { A1: '0.52', ... }, roles: { A1: { t: 'blank'|'std'|'sample', name, conc, df } },
//          fit: 'linear'|'loglog', unit, title }

import { ask, debounce, el, escapeHtml, fmt, isNum, parseDelimited, toNumber } from '../util.js';
import { linearFit, mean, sd } from './stats.js';
import { renderPlot } from './plot.js';

export const FORMATS = { 6: [2, 3], 12: [3, 4], 24: [4, 6], 48: [6, 8], 96: [8, 12], 384: [16, 24] };
const LETTERS = 'ABCDEFGHIJKLMNOP';

export function defaultPlate() {
  return { title: '', format: 96, values: {}, roles: {}, fit: 'linear', unit: 'µg/mL' };
}

export function wellName(r, c) { return `${LETTERS[r]}${c + 1}`; }

function wellPos(name) {
  const m = /^([A-P])(\d{1,2})$/i.exec(String(name).trim());
  return m ? [LETTERS.indexOf(m[1].toUpperCase()), Number(m[2]) - 1] : null;
}

// Light to dark blue: magnitude on one hue.
const RAMP = [[205, 226, 251], [134, 182, 239], [57, 135, 229], [37, 106, 191], [13, 54, 107]];
function rampColor(t) {
  const x = Math.max(0, Math.min(1, t)) * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(x));
  const f = x - i;
  const c = RAMP[i].map((v, k) => Math.round(v + (RAMP[i + 1][k] - v) * f));
  const lum = (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
  return { bg: `rgb(${c.join(',')})`, fg: lum > 0.55 ? '#1d1d1f' : '#ffffff' };
}

/* The series runs along the selection's longer side, its replicates
   across the shorter one: A9:G10 is seven standards down the rows in
   side-by-side duplicates (A9 = A10, then B9 = B10…); A1:H2 is eight
   across the columns in stacked duplicates. */
export function seriesOrder(wells) {
  const pos = wells.map(wellPos);
  const rows = new Set(pos.map(([r]) => r)).size;
  const cols = new Set(pos.map(([, c]) => c)).size;
  return wells.map((w, i) => [w, pos[i]]).sort(([, [ra, ca]], [, [rb, cb]]) => (
    cols <= rows ? ra - rb || ca - cb : ca - cb || ra - rb)).map(([w]) => w);
}

// Readings pasted from a plate reader: a grid (optionally with row letters
// and column numbers) or a list of "well  value" lines.
export function parseReadings(text, format) {
  const [rows, cols] = FORMATS[format] || FORMATS[96];
  const grid = parseDelimited(text).map((r) => r.map((v) => v.trim()));
  const values = {};
  const listLike = grid.filter((r) => r.length >= 2 && wellPos(r[0]) && isNum(r[r.length - 1]));
  if (listLike.length >= Math.min(3, grid.length)) {
    for (const r of listLike) values[r[0].toUpperCase()] = r[r.length - 1];
    return values;
  }
  // Find the grid: drop a leading header row of column numbers, and a
  // leading column of row letters.
  const isHeader = (r) => {
    const nums = r.filter((v) => v !== '');
    return nums.length > 1 && nums.every((v, i) => v === String(i + 1));
  };
  let body = grid.filter((r) => r.some(isNum) && !isHeader(r));
  body = body.map((r) => (r.length && /^[A-P]$/i.test(r[0]) ? r.slice(1) : r));
  body = body.map((r) => r.filter((v, i) => !(i === 0 && v === '')));
  body.slice(0, rows).forEach((r, ri) => {
    r.slice(0, cols).forEach((v, ci) => { if (isNum(v)) values[wellName(ri, ci)] = v; });
  });
  return values;
}

export function analysePlate(data) {
  const values = data.values || {};
  const roles = data.roles || {};
  const v = (w) => toNumber(values[w]);
  const blanks = Object.keys(roles).filter((w) => roles[w].t === 'blank').map(v).filter(Number.isFinite);
  const blank = blanks.length ? mean(blanks) : 0;
  const stdMap = new Map();
  const samples = new Map();
  for (const [w, role] of Object.entries(roles)) {
    const x = v(w);
    if (!Number.isFinite(x)) continue;
    if (role.t === 'std' && isNum(role.conc)) {
      const key = toNumber(role.conc);
      if (!stdMap.has(key)) stdMap.set(key, []);
      stdMap.get(key).push(x - blank);
    } else if (role.t === 'sample') {
      const key = role.name || 'Sample';
      if (!samples.has(key)) samples.set(key, { values: [], df: toNumber(role.df) || 1, wells: [] });
      samples.get(key).values.push(x - blank);
      samples.get(key).wells.push(w);
    }
  }
  const standards = [...stdMap.entries()].sort((a, b) => a[0] - b[0]).map(([conc, reads]) => ({ conc, mean: mean(reads), sd: sd(reads), n: reads.length, reads }));
  const loglog = data.fit === 'loglog';
  const pts = standards.flatMap((s) => s.reads.map((r) => [s.conc, r])).filter(([c, r]) => !loglog || (c > 0 && r > 0));
  const fit = pts.length >= 2 ? linearFit(pts.map((p) => (loglog ? Math.log10(p[0]) : p[0])), pts.map((p) => (loglog ? Math.log10(p[1]) : p[1]))) : null;
  const lo = standards.length ? standards[0].mean : NaN;
  const hi = standards.length ? standards[standards.length - 1].mean : NaN;
  const invert = (signal) => {
    if (!fit || fit.slope === 0) return NaN;
    if (loglog) return signal > 0 ? 10 ** ((Math.log10(signal) - fit.intercept) / fit.slope) : NaN;
    return (signal - fit.intercept) / fit.slope;
  };
  const sampleRows = [...samples.entries()].map(([name, s]) => {
    const m = mean(s.values);
    const conc = invert(m);
    return {
      name, n: s.values.length, mean: m, cv: s.values.length > 1 ? (sd(s.values) / m) * 100 : NaN,
      conc, df: s.df, final: conc * s.df, outside: Number.isFinite(lo) && (m < Math.min(lo, hi) || m > Math.max(lo, hi)),
      wells: s.wells,
    };
  });
  return { blank, nBlank: blanks.length, standards, fit, samples: sampleRows, loglog };
}

export function mountPlate(host, ctx) {
  let data = { ...defaultPlate(), ...(ctx.data || {}) };
  let editable = ctx.editable;
  let mode = Object.keys(data.values || {}).length ? 'results' : 'readings';
  const selected = new Set();
  let anchor = null;
  const commit = debounce(() => ctx.commit(JSON.parse(JSON.stringify(data))), 300);
  const root = el('div', { class: 'nb-plate' });
  host.appendChild(root);

  function grid() {
    const [rows, cols] = FORMATS[data.format] || FORMATS[96];
    const nums = Object.values(data.values || {}).map(toNumber).filter(Number.isFinite);
    const lo = nums.length ? Math.min(...nums) : 0;
    const hi = nums.length ? Math.max(...nums) : 1;
    const small = cols > 12;
    let html = `<table class="nb-plate-grid${small ? ' is-small' : ''}"><thead><tr><th></th>${Array.from({ length: cols }, (_, c) => `<th>${c + 1}</th>`).join('')}</tr></thead><tbody>`;
    for (let r = 0; r < rows; r++) {
      html += `<tr><th>${LETTERS[r]}</th>`;
      for (let c = 0; c < cols; c++) {
        const w = wellName(r, c);
        const raw = data.values?.[w];
        const x = toNumber(raw);
        const role = data.roles?.[w];
        const color = Number.isFinite(x) ? rampColor(hi > lo ? (x - lo) / (hi - lo) : 0.5) : null;
        const tag = role ? (role.t === 'blank' ? 'B' : role.t === 'std' ? `S ${fmt(toNumber(role.conc), 3)}` : escapeHtml(role.name || 'S')) : '';
        html += `<td data-w="${w}" class="${selected.has(w) ? 'is-sel' : ''} ${role ? `role-${role.t}` : ''}" style="${color ? `background:${color.bg};color:${color.fg}` : ''}" title="${w}${raw !== undefined ? `: ${escapeHtml(raw)}` : ''}${role ? ` · ${role.t}${role.name ? ` ${escapeHtml(role.name)}` : ''}${role.conc ? ` ${escapeHtml(role.conc)}` : ''}` : ''}">
          <span class="nb-plate-val">${Number.isFinite(x) ? fmt(x, 3) : ''}</span>${tag ? `<span class="nb-plate-tag">${tag}</span>` : ''}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
  }

  function layoutTools() {
    if (!editable) return '';
    return `<div class="nb-sheet-controls nb-plate-tools">
      <span class="nb-muted">${selected.size ? `${selected.size} well${selected.size > 1 ? 's' : ''} selected` : 'Click or drag across wells, shift-click for a range'}</span>
      <label>As <select data-t="role"><option value="sample">Sample</option><option value="std">Standard</option><option value="blank">Blank</option><option value="">Clear</option></select></label>
      <label>Name / conc <input data-t="label" placeholder="S1 or 100" size="8"></label>
      <label>Dilution <input data-t="df" placeholder="1" size="4"></label>
      <button type="button" class="nb-mini" data-act="apply">Apply</button>
      <button type="button" class="nb-mini" data-act="series" title="Standards on the selected wells, highest first, divided by the factor each step">Standard series…</button>
    </div>`;
  }

  function results() {
    const a = analysePlate(data);
    if (!a.standards.length && !a.samples.length) {
      return '<p class="nb-muted">Mark blanks, standards (with their concentrations) and samples in the Layout tab to get a standard curve and concentrations.</p>';
    }
    const fitText = a.fit ? (a.loglog
      ? `log(signal) = ${fmt(a.fit.slope)} · log(conc) ${a.fit.intercept < 0 ? '−' : '+'} ${fmt(Math.abs(a.fit.intercept))}`
      : `signal = ${fmt(a.fit.slope)} · conc ${a.fit.intercept < 0 ? '−' : '+'} ${fmt(Math.abs(a.fit.intercept))}`) + ` · R² = ${a.fit.r2.toFixed(4)}` : 'Two or more standards are needed for a curve.';
    return `<p class="nb-muted">Blank ${a.nBlank ? `${fmt(a.blank)} (mean of ${a.nBlank})` : 'none marked: readings used as they are'} · ${fitText}</p>
      <div class="nb-plate-results">
        <div class="nb-plot-host nb-plate-curve"></div>
        <div>
          ${a.samples.length ? `<table class="nb-stats-table"><thead><tr><th>Sample</th><th>n</th><th>Signal</th><th>CV %</th><th>Conc</th><th>× dilution</th></tr></thead><tbody>${a.samples.map((s) => `<tr><th>${escapeHtml(s.name)}</th><td>${s.n}</td><td>${fmt(s.mean)}</td><td class="${s.cv > 15 ? 'nb-warn' : ''}">${Number.isFinite(s.cv) ? fmt(s.cv, 3) : '—'}</td><td>${fmt(s.conc)}${s.outside ? ' <span class="nb-warn" title="Outside the standard curve">⚠</span>' : ''}</td><td><b>${fmt(s.final)}</b> ${escapeHtml(data.unit || '')}</td></tr>`).join('')}</tbody></table>` : ''}
        </div>
      </div>`;
  }

  function drawCurve() {
    const host2 = root.querySelector('.nb-plate-curve');
    if (!host2) return;
    const a = analysePlate(data);
    if (!a.standards.length) { host2.remove(); return; }
    const pts = a.standards.flatMap((s) => s.reads.map((r) => ({ x: a.loglog ? Math.log10(s.conc) : s.conc, y: a.loglog ? Math.log10(r) : r, label: `standard ${fmt(s.conc)}` })));
    renderPlot(host2, {
      kind: 'xy', type: 'scatter', fit: true,
      series: [{ name: 'Standards', points: pts, fit: a.fit }],
      xLabel: a.loglog ? `log₁₀ concentration (${data.unit || ''})` : `Concentration (${data.unit || ''})`,
      yLabel: a.loglog ? 'log₁₀ signal' : 'Signal (blank-subtracted)',
    }, { title: 'Standard curve' });
  }

  function render() {
    const dis = editable ? '' : ' disabled';
    root.innerHTML = `
      <div class="nb-sheet-toolbar">
        <input class="nb-sheet-title" data-f="title" value="${escapeHtml(data.title || '')}" placeholder="Plate title, e.g. BCA assay"${dis}>
        <span class="nb-seg">${['readings', 'layout', 'results'].map((m) => `<button type="button" data-mode="${m}" class="${mode === m ? 'is-on' : ''}">${m[0].toUpperCase() + m.slice(1)}</button>`).join('')}</span>
        <label>Plate <select data-f="format"${dis}>${Object.keys(FORMATS).map((f) => `<option value="${f}"${Number(data.format) === Number(f) ? ' selected' : ''}>${f}-well</option>`).join('')}</select></label>
        ${mode === 'results' ? `<label>Fit <select data-f="fit"${dis}><option value="linear"${data.fit !== 'loglog' ? ' selected' : ''}>Linear</option><option value="loglog"${data.fit === 'loglog' ? ' selected' : ''}>Log–log</option></select></label>
        <label>Unit <input data-f="unit" value="${escapeHtml(data.unit || '')}" size="6"${dis}></label>` : ''}
      </div>
      ${mode === 'readings' && editable ? `<div class="nb-plate-paste"><textarea rows="3" placeholder="Paste readings from the plate reader: the grid (with or without the A–H and 1–12 labels), or lines of “well  value”."></textarea><button type="button" class="nb-mini" data-act="paste">Fill the plate</button><button type="button" class="nb-mini" data-act="clear">Clear readings</button></div>` : ''}
      ${mode === 'layout' ? layoutTools() : ''}
      <div class="nb-sheet-scroll">${grid()}</div>
      ${mode === 'results' ? results() : ''}`;
    if (mode === 'results') {
      if (root.isConnected) drawCurve(); else requestAnimationFrame(drawCurve);
    }
  }

  function applyRole() {
    const role = root.querySelector('[data-t="role"]').value;
    const label = root.querySelector('[data-t="label"]').value.trim();
    const df = root.querySelector('[data-t="df"]').value.trim();
    data.roles = data.roles || {};
    for (const w of selected) {
      if (!role) delete data.roles[w];
      else if (role === 'blank') data.roles[w] = { t: 'blank' };
      else if (role === 'std') data.roles[w] = { t: 'std', conc: label };
      else data.roles[w] = { t: 'sample', name: label || 'Sample', ...(df ? { df } : {}) };
    }
    commit(); render();
  }

  async function standardSeries() {
    if (!selected.size) { ask.alert('Select the standard wells first, in the order of the series.'); return; }
    const top = toNumber(await ask.prompt('Highest standard concentration', '2000', { okLabel: 'Next' }));
    if (!Number.isFinite(top)) return;
    const factor = toNumber(await ask.prompt('Divide by this at each step', '2', { okLabel: 'Next' }));
    if (!Number.isFinite(factor) || factor <= 1) return;
    const reps = Math.max(1, Math.round(toNumber(await ask.prompt('Replicates of each standard (next to each other in the selection)', '2', { okLabel: 'Make the series' })) || 1));
    const wells = seriesOrder([...selected]);
    data.roles = data.roles || {};
    wells.forEach((w, i) => { data.roles[w] = { t: 'std', conc: String(Number((top / factor ** Math.floor(i / reps)).toPrecision(6))) }; });
    commit(); render();
  }

  let dragging = false;
  root.addEventListener('mousedown', (event) => {
    const td = event.target.closest('td[data-w]');
    if (!td || mode !== 'layout' || !editable) return;
    event.preventDefault();
    const w = td.dataset.w;
    if (event.shiftKey && anchor) {
      const [r1, c1] = wellPos(anchor);
      const [r2, c2] = wellPos(w);
      for (let r = Math.min(r1, r2); r <= Math.max(r1, r2); r++) for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c++) selected.add(wellName(r, c));
    } else {
      if (!(event.metaKey || event.ctrlKey)) selected.clear();
      selected.has(w) ? selected.delete(w) : selected.add(w);
      anchor = w;
    }
    dragging = true;
    render();
  });
  root.addEventListener('mouseover', (event) => {
    if (!dragging) return;
    const td = event.target.closest('td[data-w]');
    if (td && !selected.has(td.dataset.w)) { selected.add(td.dataset.w); td.classList.add('is-sel'); }
  });
  const onMouseUp = () => {
    if (dragging) { dragging = false; render(); }
  };
  window.addEventListener('mouseup', onMouseUp);
  root.addEventListener('click', async (event) => {
    const b = event.target.closest('button');
    if (!b) return;
    if (b.dataset.mode) { mode = b.dataset.mode; render(); return; }
    if (b.dataset.act === 'paste') {
      const text = root.querySelector('.nb-plate-paste textarea').value;
      const values = parseReadings(text, data.format);
      if (!Object.keys(values).length) { ask.alert('No readings found in that text.'); return; }
      data.values = { ...(data.values || {}), ...values };
      mode = 'layout';
      commit(); render();
    } else if (b.dataset.act === 'clear') {
      if (!(await ask.confirm('Clear all readings?', { danger: true }))) return;
      data.values = {};
      commit(); render();
    } else if (b.dataset.act === 'apply') applyRole();
    else if (b.dataset.act === 'series') standardSeries();
  });
  root.addEventListener('input', (event) => {
    const f = event.target.dataset.f;
    if (!f || event.target.tagName !== 'INPUT') return;
    data[f] = event.target.value;
    commit();
    if (f === 'unit' && mode === 'results') {
      clearTimeout(root._t);
      root._t = setTimeout(render, 500);
    }
  });
  root.addEventListener('change', (event) => {
    const f = event.target.dataset.f;
    if (!f || event.target.tagName !== 'SELECT') return;
    data[f] = f === 'format' ? Number(event.target.value) : event.target.value;
    commit(); render();
  });

  render();
  return {
    update(next) { data = { ...defaultPlate(), ...(next || {}) }; render(); },
    destroy() { commit.flush(); window.removeEventListener('mouseup', onMouseUp); },
  };
}
