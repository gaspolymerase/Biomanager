// A small SVG plotter for data sheets: scatter and line plots (optionally
// with a fitted line), bar charts of group means with error bars and the
// points on top, and box plots; significance brackets from the sheet's
// statistics. Marks follow one set of specs (2px lines, 8px dots with a
// surface ring, bars no thicker than 24px with a rounded end), colours come
// from the --viz-* tokens in styles.css (a validated categorical order, with
// its own dark-mode steps), and text uses the ink tokens, never a series
// colour. Every mark has a hover tooltip.

import { escapeHtml, fmt, stars } from '../util.js';

const NS = 'http://www.w3.org/2000/svg';
const SHAPES = ['circle', 'square', 'triangle', 'diamond'];

function niceStep(range, count) {
  const raw = range / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return step * mag;
}

export function niceTicks(lo, hi, count = 5) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
  if (lo === hi) { lo -= 1; hi += 1; }
  const step = niceStep(hi - lo, count);
  const start = Math.floor(lo / step) * step;
  const end = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

function logTicks(lo, hi) {
  const ticks = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) ticks.push(10 ** e);
  return ticks;
}

// Read from the document root: a block drawn before it is attached to the
// page has no computed styles of its own.
function tokens() {
  const cs = getComputedStyle(document.documentElement);
  const get = (name, fallback) => (cs.getPropertyValue(name) || '').trim() || fallback;
  return {
    series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => get(`--viz-${i}`, '#2a78d6')),
    surface: get('--viz-surface', '#ffffff'),
    grid: get('--viz-grid', '#e5e5ea'),
    axis: get('--viz-axis', '#c7c7cc'),
    ink: get('--viz-ink', '#1d1d1f'),
    muted: get('--viz-muted', '#6e6e73'),
  };
}

function node(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}

function marker(shape, x, y, r, fill, ring) {
  const common = { fill, stroke: ring, 'stroke-width': 2 };
  if (shape === 'square') return node('rect', { ...common, x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: 1.5 });
  if (shape === 'triangle') {
    const h = r * 1.15;
    return node('path', { ...common, d: `M${x},${y - h} L${x + h},${y + h * 0.8} L${x - h},${y + h * 0.8} Z` });
  }
  if (shape === 'diamond') {
    const h = r * 1.25;
    return node('path', { ...common, d: `M${x},${y - h} L${x + h},${y} L${x},${y + h} L${x - h},${y} Z` });
  }
  return node('circle', { ...common, cx: x, cy: y, r });
}

// Rounded data end, square at the baseline.
function barPath(x, w, yTop, yBase) {
  const r = Math.min(4, w / 2, Math.abs(yBase - yTop));
  if (yTop <= yBase) {
    return `M${x},${yBase} L${x},${yTop + r} Q${x},${yTop} ${x + r},${yTop} L${x + w - r},${yTop} Q${x + w},${yTop} ${x + w},${yTop + r} L${x + w},${yBase} Z`;
  }
  return `M${x},${yBase} L${x},${yTop - r} Q${x},${yTop} ${x + r},${yTop} L${x + w - r},${yTop} Q${x + w},${yTop} ${x + w},${yTop - r} L${x + w},${yBase} Z`;
}

function jitter(i, n) {
  // Deterministic spread, so the plot does not jump on every render.
  const golden = 0.6180339887;
  return ((i * golden) % 1) - 0.5 + (n < 2 ? 0.5 : 0);
}

// spec:
//   { kind: 'xy', type: 'scatter'|'line', series: [{ name, points: [{x, y, label}] }],
//     xLabel, yLabel, xCategories?: [..], fit: bool, logY }
//   { kind: 'groups', type: 'bar'|'box'|'dots', groups: [{ name, values, summary }],
//     error: 'sem'|'sd'|'none', yLabel, comparisons: [{a, b, padj}], logY }
export function renderPlot(host, spec, { title = '' } = {}) {
  host.innerHTML = '';
  const t = tokens();
  const width = Math.max(320, Math.min(host.clientWidth || 640, 900));
  const height = 300;
  const margin = { top: 20, right: 20, bottom: 46, left: 58 };
  const multi = spec.kind === 'xy' ? spec.series.length > 1 : false;
  const svg = node('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img',
    'aria-label': title || 'Plot', class: 'nb-plot-svg', 'font-family': 'inherit', 'font-size': 11 });
  svg.appendChild(node('rect', { x: 0, y: 0, width, height, fill: t.surface }));
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const g = node('g', { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(g);

  // ---- y range
  let ys = [];
  if (spec.kind === 'xy') ys = spec.series.flatMap((s) => s.points.map((p) => p.y));
  else {
    for (const grp of spec.groups) {
      ys.push(...grp.values);
      const s = grp.summary;
      if (spec.type === 'bar' && s && Number.isFinite(s.mean)) {
        const e = spec.error === 'sd' ? s.sd : spec.error === 'sem' ? s.sem : 0;
        ys.push(s.mean + (Number.isFinite(e) ? e : 0), s.mean - (Number.isFinite(e) ? e : 0));
      }
    }
  }
  ys = ys.filter(Number.isFinite);
  if (spec.logY) ys = ys.filter((v) => v > 0);
  if (!ys.length) {
    host.appendChild(Object.assign(document.createElement('div'), { className: 'nb-plot-empty', textContent: 'Nothing to plot yet: add numbers to the value column.' }));
    return null;
  }
  let yLo = Math.min(...ys);
  let yHi = Math.max(...ys);
  if (spec.kind === 'groups' && spec.type === 'bar' && !spec.logY) { yLo = Math.min(0, yLo); yHi = Math.max(0, yHi); }
  const bracketRoom = spec.kind === 'groups' ? (spec.comparisons || []).filter((c) => c.padj < 0.05 || spec.showNs).length : 0;
  let yTicks;
  let yScale;
  if (spec.logY) {
    yTicks = logTicks(yLo, yHi);
    const lo = Math.log10(yTicks[0]);
    const hi = Math.log10(yTicks[yTicks.length - 1]);
    yScale = (v) => plotH - ((Math.log10(v) - lo) / (hi - lo || 1)) * plotH * (1 - 0.07 * bracketRoom);
  } else {
    yTicks = niceTicks(yLo, yHi, 5);
    const lo = yTicks[0];
    const hi = yTicks[yTicks.length - 1];
    const span = (hi - lo) || 1;
    const room = 1 - Math.min(0.4, 0.08 * bracketRoom);
    yScale = (v) => plotH - ((v - lo) / span) * plotH * room;
  }

  // ---- gridlines + y axis
  const grid = node('g', { class: 'nb-plot-grid' });
  for (const tick of yTicks) {
    const y = yScale(tick);
    grid.appendChild(node('line', { x1: 0, x2: plotW, y1: y, y2: y, stroke: t.grid, 'stroke-width': 1 }));
    grid.appendChild(node('text', { x: -8, y: y + 3.5, 'text-anchor': 'end', fill: t.muted }, fmt(tick, 3)));
  }
  g.appendChild(grid);
  if (spec.yLabel) {
    g.appendChild(node('text', { transform: `translate(${-44},${plotH / 2}) rotate(-90)`, 'text-anchor': 'middle', fill: t.muted, 'font-size': 11.5 }, spec.yLabel));
  }

  const marks = node('g');
  g.appendChild(marks);
  const legend = [];

  if (spec.kind === 'xy') {
    const categorical = !!spec.xCategories;
    let xScale;
    let xTicks;
    if (categorical) {
      const n = spec.xCategories.length;
      const band = plotW / Math.max(1, n);
      xScale = (v) => band * (spec.xCategories.indexOf(v) + 0.5);
      xTicks = spec.xCategories.map((c) => ({ v: c, x: xScale(c), label: String(c) }));
    } else {
      const xs = spec.series.flatMap((s) => s.points.map((p) => p.x)).filter(Number.isFinite);
      const ticks = niceTicks(Math.min(...xs), Math.max(...xs), 6);
      const lo = ticks[0];
      const hi = ticks[ticks.length - 1];
      xScale = (v) => ((v - lo) / ((hi - lo) || 1)) * plotW;
      xTicks = ticks.map((v) => ({ v, x: xScale(v), label: fmt(v, 3) }));
    }
    const axis = node('g');
    axis.appendChild(node('line', { x1: 0, x2: plotW, y1: plotH, y2: plotH, stroke: t.axis, 'stroke-width': 1 }));
    const every = Math.ceil(xTicks.length / Math.max(1, Math.floor(plotW / 56)));
    xTicks.forEach((tick, i) => {
      if (i % every) return;
      axis.appendChild(node('text', { x: tick.x, y: plotH + 16, 'text-anchor': 'middle', fill: t.muted }, tick.label.length > 12 ? tick.label.slice(0, 11) + '…' : tick.label));
    });
    if (spec.xLabel) axis.appendChild(node('text', { x: plotW / 2, y: plotH + 36, 'text-anchor': 'middle', fill: t.muted, 'font-size': 11.5 }, spec.xLabel));
    g.appendChild(axis);

    spec.series.forEach((series, si) => {
      const color = t.series[si % t.series.length];
      const shape = SHAPES[si % SHAPES.length];
      const pts = series.points.filter((p) => Number.isFinite(p.y) && (categorical || Number.isFinite(p.x)) && (!spec.logY || p.y > 0));
      if (spec.type === 'line' && pts.length > 1) {
        const sorted = categorical ? pts : [...pts].sort((a, b) => a.x - b.x);
        const d = sorted.map((p, i) => `${i ? 'L' : 'M'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ');
        marks.appendChild(node('path', { d, fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
      }
      if (spec.fit && series.fit && !categorical) {
        const xs = pts.map((p) => p.x);
        const x0 = Math.min(...xs);
        const x1 = Math.max(...xs);
        const f = series.fit;
        const y0 = f.slope * x0 + f.intercept;
        const y1v = f.slope * x1 + f.intercept;
        if (!spec.logY || (y0 > 0 && y1v > 0)) {
          marks.appendChild(node('line', { x1: xScale(x0), y1: yScale(y0), x2: xScale(x1), y2: yScale(y1v), stroke: color, 'stroke-width': 2, 'stroke-opacity': 0.55, 'stroke-linecap': 'round' }));
        }
      }
      for (const p of pts) {
        const m = marker(multi ? shape : 'circle', xScale(p.x), yScale(p.y), 4.5, color, t.surface);
        m.setAttribute('data-tip', `${series.name ? escapeHtml(series.name) + '<br>' : ''}${p.label ? escapeHtml(p.label) + '<br>' : ''}${escapeHtml(spec.xLabel || 'x')}: <b>${escapeHtml(categorical ? p.x : fmt(p.x))}</b><br>${escapeHtml(spec.yLabel || 'y')}: <b>${fmt(p.y)}</b>`);
        marks.appendChild(m);
      }
      legend.push({ name: series.name || spec.yLabel || 'Series', color, shape: multi ? shape : 'circle', fit: series.fit });
    });
  } else {
    const n = spec.groups.length;
    const band = plotW / Math.max(1, n);
    const barW = Math.min(24 * 2, band * 0.55);
    const axis = node('g');
    axis.appendChild(node('line', { x1: 0, x2: plotW, y1: plotH, y2: plotH, stroke: t.axis, 'stroke-width': 1 }));
    const centers = {};
    spec.groups.forEach((grp, gi) => {
      const cx = band * (gi + 0.5);
      centers[grp.name] = cx;
      const color = t.series[gi % t.series.length];
      const s = grp.summary;
      axis.appendChild(node('text', { x: cx, y: plotH + 16, 'text-anchor': 'middle', fill: t.ink }, String(grp.name).length > 14 ? String(grp.name).slice(0, 13) + '…' : String(grp.name)));
      axis.appendChild(node('text', { x: cx, y: plotH + 30, 'text-anchor': 'middle', fill: t.muted, 'font-size': 10 }, `n = ${s.n}`));
      const tip = `<b>${escapeHtml(grp.name)}</b><br>n = ${s.n}<br>mean ${fmt(s.mean)}<br>SD ${fmt(s.sd)} · SEM ${fmt(s.sem)}<br>median ${fmt(s.median)}`;
      if (spec.type === 'bar' && Number.isFinite(s.mean)) {
        const w = Math.min(24, barW);
        const base = spec.logY ? plotH : yScale(Math.max(0, yTicks[0]));
        const top = yScale(spec.logY ? Math.max(s.mean, yTicks[0]) : s.mean);
        const bar = node('path', { d: barPath(cx - w / 2, w, top, base), fill: color, 'fill-opacity': 0.9 });
        bar.setAttribute('data-tip', tip);
        marks.appendChild(bar);
        const e = spec.error === 'sd' ? s.sd : spec.error === 'sem' ? s.sem : NaN;
        if (Number.isFinite(e) && e > 0) {
          const yTop = yScale(s.mean + e);
          const yBot = spec.logY && s.mean - e <= 0 ? plotH : yScale(s.mean - e);
          const cap = 7;
          marks.appendChild(node('path', { d: `M${cx},${yTop} L${cx},${yBot} M${cx - cap},${yTop} L${cx + cap},${yTop} M${cx - cap},${yBot} L${cx + cap},${yBot}`, stroke: t.ink, 'stroke-width': 1.5, fill: 'none', 'stroke-linecap': 'round' }));
        }
      }
      if (spec.type === 'box' && s.n) {
        const w = Math.min(40, band * 0.5);
        const iqr = s.q3 - s.q1;
        const vals = [...grp.values].sort((a, b) => a - b);
        const loW = vals.find((v) => v >= s.q1 - 1.5 * iqr);
        const hiW = [...vals].reverse().find((v) => v <= s.q3 + 1.5 * iqr);
        marks.appendChild(node('path', { d: `M${cx},${yScale(hiW)} L${cx},${yScale(s.q3)} M${cx},${yScale(s.q1)} L${cx},${yScale(loW)} M${cx - w / 4},${yScale(hiW)} L${cx + w / 4},${yScale(hiW)} M${cx - w / 4},${yScale(loW)} L${cx + w / 4},${yScale(loW)}`, stroke: color, 'stroke-width': 2, fill: 'none', 'stroke-linecap': 'round' }));
        const box = node('rect', { x: cx - w / 2, y: yScale(s.q3), width: w, height: Math.max(1, yScale(s.q1) - yScale(s.q3)), rx: 4, fill: color, 'fill-opacity': 0.14, stroke: color, 'stroke-width': 2 });
        box.setAttribute('data-tip', `${tip}<br>IQR ${fmt(s.q1)} – ${fmt(s.q3)}`);
        marks.appendChild(box);
        marks.appendChild(node('line', { x1: cx - w / 2, x2: cx + w / 2, y1: yScale(s.median), y2: yScale(s.median), stroke: color, 'stroke-width': 2.5 }));
      }
      if (spec.showPoints !== false || spec.type === 'dots') {
        const spread = Math.min(18, band * 0.25);
        grp.values.forEach((v, i) => {
          if (spec.logY && v <= 0) return;
          const px = cx + jitter(i + 1, grp.values.length) * spread;
          const m = marker('circle', px, yScale(v), spec.type === 'dots' ? 4.5 : 3.5, spec.type === 'bar' ? t.ink : color, t.surface);
          if (spec.type === 'bar') m.setAttribute('fill-opacity', '0.75');
          m.setAttribute('data-tip', `${escapeHtml(grp.name)}: <b>${fmt(v)}</b>`);
          marks.appendChild(m);
        });
        if (spec.type === 'dots' && Number.isFinite(s.mean)) {
          marks.appendChild(node('line', { x1: cx - 14, x2: cx + 14, y1: yScale(s.mean), y2: yScale(s.mean), stroke: t.ink, 'stroke-width': 2, 'stroke-linecap': 'round' }));
        }
      }
    });
    g.appendChild(axis);

    // ---- significance brackets
    const shown = (spec.comparisons || []).filter((c) => c.padj < 0.05 || spec.showNs);
    let level = 0;
    const top = yScale(yTicks[yTicks.length - 1]);
    for (const c of shown) {
      if (!(c.a in centers) || !(c.b in centers)) continue;
      const x1 = centers[c.a];
      const x2 = centers[c.b];
      // Stacked upwards into the room left above the highest tick.
      const yy = Math.max(12, top - 10 - level * 16);
      const b = node('path', { d: `M${x1},${yy + 5} L${x1},${yy} L${x2},${yy} L${x2},${yy + 5}`, stroke: t.ink, 'stroke-width': 1.2, fill: 'none' });
      b.setAttribute('data-tip', `${escapeHtml(c.a)} vs ${escapeHtml(c.b)}<br>p = ${fmt(c.padj, 3)}`);
      marks.appendChild(b);
      marks.appendChild(node('text', { x: (x1 + x2) / 2, y: yy - 3, 'text-anchor': 'middle', fill: t.ink, 'font-size': 12 }, stars(c.padj)));
      level++;
    }
  }

  host.appendChild(svg);

  // Legend for more than one series; one series is named by the title.
  if (legend.length > 1) {
    const box = document.createElement('div');
    box.className = 'nb-plot-legend';
    box.innerHTML = legend.map((l) => {
      const swatch = `<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">${marker(l.shape, 7, 7, 4, l.color, 'transparent').outerHTML}</svg>`;
      const fit = l.fit ? ` <span class="nb-plot-legend-fit">y = ${fmt(l.fit.slope)}x ${l.fit.intercept < 0 ? '−' : '+'} ${fmt(Math.abs(l.fit.intercept))}, R² = ${l.fit.r2.toFixed(3)}</span>` : '';
      return `<span class="nb-plot-legend-item">${swatch}${escapeHtml(l.name)}${fit}</span>`;
    }).join('');
    host.appendChild(box);
  } else if (legend.length === 1 && legend[0].fit) {
    const f = legend[0].fit;
    const box = document.createElement('div');
    box.className = 'nb-plot-legend';
    box.innerHTML = `<span class="nb-plot-legend-fit">Fit: y = ${fmt(f.slope)}x ${f.intercept < 0 ? '−' : '+'} ${fmt(Math.abs(f.intercept))} · R² = ${f.r2.toFixed(4)} · n = ${f.n}</span>`;
    host.appendChild(box);
  }

  attachTooltip(host, svg);
  return svg;
}

let tipEl = null;
function attachTooltip(host, svg) {
  if (!tipEl) {
    tipEl = document.createElement('div');
    tipEl.className = 'nb-plot-tooltip';
    tipEl.hidden = true;
    document.body.appendChild(tipEl);
  }
  svg.addEventListener('mousemove', (event) => {
    // Hit targets are bigger than the marks: the nearest mark within 14px.
    let target = event.target.closest && event.target.closest('[data-tip]');
    if (!target) {
      let best = null;
      let bestD = 14 * 14;
      for (const m of svg.querySelectorAll('[data-tip]')) {
        const r = m.getBoundingClientRect();
        const dx = Math.max(r.left - event.clientX, 0, event.clientX - r.right);
        const dy = Math.max(r.top - event.clientY, 0, event.clientY - r.bottom);
        const d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = m; }
      }
      target = best;
    }
    if (!target) { tipEl.hidden = true; return; }
    tipEl.innerHTML = target.getAttribute('data-tip');
    tipEl.hidden = false;
    const x = Math.min(window.innerWidth - tipEl.offsetWidth - 8, event.clientX + 14);
    const y = Math.max(8, event.clientY - tipEl.offsetHeight - 10);
    tipEl.style.left = `${x}px`;
    tipEl.style.top = `${y}px`;
  });
  svg.addEventListener('mouseleave', () => { tipEl.hidden = true; });
}

export function svgText(svg) {
  const clone = svg.cloneNode(true);
  clone.setAttribute('xmlns', NS);
  clone.querySelectorAll('[data-tip]').forEach((n) => n.removeAttribute('data-tip'));
  clone.setAttribute('font-family', '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif');
  return new XMLSerializer().serializeToString(clone);
}

export function svgToPng(svg, scale = 2) {
  return new Promise((resolve, reject) => {
    const text = svgText(svg);
    const w = Number(svg.getAttribute('width'));
    const h = Number(svg.getAttribute('height'));
    const img = new Image();
    const url = URL.createObjectURL(new Blob([text], { type: 'image/svg+xml' }));
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = w * scale;
      canvas.height = h * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('png failed'))), 'image/png');
    };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}
