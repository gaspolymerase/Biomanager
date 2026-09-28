/* An experiment's page (templates/experiment.html, app/experiments.py,
   app/experiment_steps.py): the sheet of its animals, switching between the
   treatments each got and the readout (editable in place); the readout over
   the days, the manipulation days dashed and explained on hover; the plan
   day by day; and the dialogs that add animals, plan, record a
   manipulation and record a readout day. Every change answers with the
   whole page's data, and the page is drawn again from it. */
(function () {
  'use strict';
  const dataEl = document.getElementById('xp-data');
  if (!dataEl) return;
  let D = JSON.parse(dataEl.textContent || '{}');
  const API = `/colony/experiments/${D.id}`;      // manipulations (experiment_steps.py)
  const XP = `/experiments/${D.id}`;              // the experiment itself (experiments.py)
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  let view = 'treatment';
  let scale = null;           // raw values, or %: a count starts as % of those at the start
  try { view = sessionStorage.getItem(`xp:view:${D.id}`) || 'treatment'; } catch (_e) { /* no storage */ }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const icon = (name) => `<svg class="icon xp-icon" aria-hidden="true"><use href="/static/icons.svg#${esc(name)}"></use></svg>`;
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const niceDate = (iso, weekday) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined,
    weekday ? { weekday: 'short', day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short' }) : '');
  const num = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(v) ? ''
    : Number(v).toFixed(digits).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, ''));
  const fraction = () => D.readout.kind === 'fraction';
  const STATE = { done: 'Done', today: 'Today', overdue: 'Overdue', upcoming: 'To come', planned: 'Planned' };

  // ---------------------------------------------------------------- talking to the app

  function say(state, text) {
    const el = $('[data-save-status]');
    if (!el) return;
    clearTimeout(el._clear);
    el.dataset.state = state;
    el.textContent = text;
    if (state === 'saved') el._clear = setTimeout(() => { el.textContent = ''; el.dataset.state = ''; }, 2400);
  }

  async function send(url, body, { form = false } = {}) {
    say('saving', 'Saving…');
    const r = await fetch(url, form ? { method: 'POST', body, headers: { 'X-Autosave': '1' } }
      : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Autosave': '1' }, body: JSON.stringify(body || {}) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) {
      const error = new Error(data.error || `The app answered ${r.status}.`);
      error.data = data;
      say('error', `Not saved: ${error.message}`);
      throw error;
    }
    say('saved', 'All changes saved');
    return data;
  }

  async function get(url) {
    const r = await fetch(url);
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) throw new Error(data.error || `The app answered ${r.status}.`);
    return data;
  }

  function apply(data, { sheet = true } = {}) {
    ['subjects', 'groups', 'steps', 'schedule', 'table', 'readout', 'weighs', 'start_date', 'editable', 'kinds',
      'regimens', 'reagents', 'sample_inventories'].forEach((k) => {
      if (data[k] !== undefined) D[k] = data[k];
    });
    if (data.add) refreshAddOptions(data.add);
    const list = $('#xp-groups');
    if (list) list.innerHTML = D.groups.map((g) => `<option value="${esc(g)}">`).join('');
    if (sheet) drawSheet();
    drawChart();
    drawDays();
    drawLabels();
  }

  const confirmAsk = (text, danger) => (window.BioDialog && BioDialog.confirm
    ? BioDialog.confirm(text, { danger: Boolean(danger) }) : Promise.resolve(window.confirm(text)));
  const alertSay = (text) => (window.BioDialog && BioDialog.alert ? BioDialog.alert(text) : window.alert(text));

  // ---------------------------------------------------------------- labels that follow the readout

  function drawLabels() {
    const r = D.readout;
    $$('[data-xp-readout-label]').forEach((el) => { el.textContent = r.label; });
    $$('[data-xp-reading-verb]').forEach((el) => { el.textContent = r.verb || 'Record'; });
    const title = $('[data-xp-chart-title]');
    if (title) title.textContent = `${r.label}${r.unit && !fraction() ? ` (${r.unit})` : ''}`;
    const [raw, pct] = $$('[data-xp-scale]');
    if (raw && pct) {
      raw.textContent = fraction() ? `How many ${r.unit || ''}`.trim() : (r.unit || 'Value');
      pct.textContent = fraction() ? '% of those at the start' : '% of the first';
      raw.setAttribute('aria-pressed', String(scale === 'raw'));
      pct.setAttribute('aria-pressed', String(scale === 'pct'));
    }
    $$('[data-xp-view]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.xpView === view)));
  }

  // ---------------------------------------------------------------- the sheet

  const inGroup = (subject, group) => !group || subject.group.trim().toLowerCase() === group.trim().toLowerCase();
  const treatmentCols = () => D.schedule.filter((r) => !r.reading);

  function drawSheet() {
    const table = $('[data-xp-table]');
    const empty = $('[data-xp-empty]');
    const subs = D.subjects;
    empty.hidden = subs.length > 0;
    if (!subs.length) {
      table.innerHTML = '';
      empty.innerHTML = `No ${esc(D.nouns)} yet.${D.editable ? ` <b>Add ${esc(D.nouns)}</b> to start.` : ''}`;
      return;
    }
    const showSex = subs.some((s) => s.sex);
    const showStart = D.family !== 'mouse';
    const head = [`<th class="sheet-pin sheet-pin-start xp-id">${esc(D.noun.charAt(0).toUpperCase() + D.noun.slice(1))}</th>`];
    if (showSex) head.push('<th>Sex</th>');
    head.push('<th>Genotype</th>', `<th>${esc(D.housing.charAt(0).toUpperCase() + D.housing.slice(1))}</th>`, '<th>Group</th>');
    if (showStart) head.push('<th title="How many at the start, for a count or survival">At start</th>');

    let cols = [];
    if (view === 'treatment') {
      cols = treatmentCols();
      if (!cols.length) head.push(`<th class="xp-note-col">${D.editable ? 'No manipulations yet: <b>Record manipulation</b>, or add them to the <b>Plan</b>.' : 'No manipulations yet.'}</th>`);
      cols.forEach((c) => head.push(`<th class="xp-daycol" data-state="${esc(c.state)}" title="${esc(`Day ${c.day}${c.date ? `, ${niceDate(c.date, true)}` : ''}: ${c.title}${c.group ? ` (${c.group})` : ''}`)}">
        <span class="xp-dayhead">Day ${c.day}</span><span class="xp-daywhat">${esc(c.title)}</span><span class="xp-daydate">${esc(niceDate(c.date))}${c.group ? ` · ${esc(c.group)}` : ''}</span></th>`));
    } else {
      D.table.dates.forEach((d, i) => head.push(`<th class="xp-daycol"><span class="xp-dayhead">${D.table.days[i] !== null ? `Day ${D.table.days[i]}` : ''}</span><span class="xp-daydate">${esc(niceDate(d))}</span></th>`));
      if (D.editable) head.push(`<th class="xp-daycol xp-newday"><span class="xp-dayhead">Another day</span><input type="date" class="xp-newday-date" value="${today()}" max="${today()}" aria-label="The day of the new column"></th>`);
    }
    if (D.editable) head.push('<th class="xp-actions"></th>');

    const rowsByKey = Object.fromEntries(D.table.rows.map((r) => [r.key, r]));
    const body = subs.map((s) => {
      const cells = [`<td class="sheet-pin sheet-pin-start xp-id"><span class="sheet-id"><span class="life-dot${s.alive ? ' is-alive' : ''}"></span><span class="ident">${esc(s.label)}</span></span></td>`];
      if (showSex) cells.push(`<td>${esc(s.sex)}</td>`);
      cells.push(`<td class="xp-geno" title="${esc(s.genotype)}">${esc(s.genotype)}</td>`, `<td>${esc(s.housing)}</td>`);
      cells.push(`<td><input class="xp-cell" data-xp-group="${esc(s.key)}" value="${esc(s.group)}" placeholder="(no group)" list="xp-groups" aria-label="Group of ${esc(s.label)}" ${D.editable ? '' : 'disabled'}></td>`);
      if (showStart) cells.push(`<td><input class="xp-cell xp-num" data-xp-start="${esc(s.key)}" value="${s.start == null ? '' : s.start}" inputmode="numeric" aria-label="How many ${esc(s.label)} started with" ${D.editable ? '' : 'disabled'}></td>`);
      if (view === 'treatment') {
        if (!cols.length) cells.push('<td></td>');
        cols.forEach((c) => cells.push(treatmentCell(s, c)));
      } else {
        const row = rowsByKey[s.key] || { values: [] };
        D.table.dates.forEach((d, i) => cells.push(readingCell(s, d, row.values[i])));
        if (D.editable) cells.push(readingCell(s, '', null, true));
      }
      if (D.editable) cells.push(`<td class="xp-actions"><button type="button" class="xp-link xp-danger" data-xp-remove="${esc(s.key)}" aria-label="Take ${esc(s.label)} out of the experiment" title="Take out of the experiment">×</button></td>`);
      return `<tr>${cells.join('')}</tr>`;
    }).join('');
    table.innerHTML = `<thead><tr>${head.join('')}</tr></thead><tbody>${body}</tbody>`;
  }

  function treatmentCell(subject, col) {
    if (!inGroup(subject, col.group)) return '<td class="xp-t" data-t="none" title="Not in this group">·</td>';
    const rec = col.record;
    if (!rec) {
      const label = { today: 'due', overdue: 'due', upcoming: '', planned: '' }[col.state] || '';
      return `<td class="xp-t" data-t="${esc(col.state)}">${label ? `<span class="xp-due">${label}</span>` : ''}</td>`;
    }
    const entry = rec.subjects.find((e) => e.subject === subject.key);
    const detail = entry ? [entry.amount, entry.volume].filter(Boolean).join(' · ') : '';
    const lot = rec.reagent && rec.reagent.name ? ` · ${rec.reagent.name}${rec.reagent.lot ? ` lot ${rec.reagent.lot}` : ''}` : '';
    const title = entry ? `Given ${niceDate(rec.done_on)} by ${rec.done_by}${detail ? `: ${detail}` : ''}${lot}` : `Not given (recorded ${niceDate(rec.done_on)})`;
    const inner = entry ? `<span class="xp-tick">✓</span>${detail ? `<span class="xp-amount">${esc(detail)}</span>` : ''}` : '<span class="xp-miss">—</span>';
    return D.editable
      ? `<td class="xp-t" data-t="${entry ? 'given' : 'missed'}"><button type="button" class="xp-tbtn" data-xp-toggle="${col.step_id}:${col.day}" data-subject="${esc(subject.key)}" data-given="${entry ? 1 : 0}" title="${esc(title)} (click to change)">${inner}</button></td>`
      : `<td class="xp-t" data-t="${entry ? 'given' : 'missed'}" title="${esc(title)}">${inner}</td>`;
  }

  function readingCell(subject, date, value, fresh = false) {
    const of = fraction() && subject.start != null ? `<span class="xp-of">/ ${subject.start}</span>` : '';
    return `<td class="xp-r"><span class="xp-rwrap"><input class="xp-cell xp-num" data-xp-reading="${esc(subject.key)}" data-date="${esc(date)}" ${fresh ? 'data-fresh="1"' : ''}
      value="${value === null || value === undefined ? '' : num(value, 2)}" inputmode="decimal" aria-label="${esc(D.readout.label)} of ${esc(subject.label)}${date ? ` on ${date}` : ''}" ${D.editable ? '' : 'disabled'}>${of}</span></td>`;
  }

  // Sheet edits
  document.addEventListener('change', async (event) => {
    const t = event.target;
    if (t.matches('[data-xp-group]')) {
      try { apply(await send(`${XP}/subjects/${encodeURIComponent(t.dataset.xpGroup)}/update`, { group: t.value })); } catch (_e) { /* shown */ }
    } else if (t.matches('[data-xp-start]')) {
      try { apply(await send(`${XP}/subjects/${encodeURIComponent(t.dataset.xpStart)}/update`, { start: t.value }), { sheet: false }); } catch (_e) { t.classList.add('is-error'); }
    } else if (t.matches('[data-xp-reading]')) {
      const on = t.dataset.fresh ? ($('.xp-newday-date') || {}).value : t.dataset.date;
      if (!on) return;
      try {
        const data = await send(`${XP}/readings`, { on, values: { [t.dataset.xpReading]: t.value } });
        t.classList.remove('is-error');
        apply(data, { sheet: Boolean(t.dataset.fresh) });       // a new day becomes its own column
      } catch (_e) { t.classList.add('is-error'); }
    }
  });

  document.addEventListener('click', async (event) => {
    const t = event.target.closest('button');
    if (!t) return;
    if (t.dataset.xpView) {
      view = t.dataset.xpView;
      try { sessionStorage.setItem(`xp:view:${D.id}`, view); } catch (_e) { /* no storage */ }
      drawSheet(); drawLabels();
    } else if (t.dataset.xpScale) {
      scale = t.dataset.xpScale; drawChart(); drawLabels();
    } else if (t.dataset.xpToggle) {
      const [stepId, day] = t.dataset.xpToggle.split(':');
      try {
        apply(await send(`${API}/steps/${stepId}/day/${day}/subject`, { subject: t.dataset.subject, given: t.dataset.given !== '1' }));
      } catch (_e) { /* shown */ }
    } else if (t.dataset.xpRemove) {
      const s = D.subjects.find((x) => x.key === t.dataset.xpRemove);
      if (!(await confirmAsk(`Take ${s ? s.label : 'it'} out of this experiment? Its own record is unchanged.`, true))) return;
      try { apply(await send(`${XP}/subjects/${encodeURIComponent(t.dataset.xpRemove)}/remove`, {})); } catch (_e) { /* shown */ }
    } else if (t.dataset.xpOpen) {
      open(t.dataset.xpOpen, t.dataset.on);
    } else if (t.matches('[data-xp-close]')) {
      t.closest('dialog').close();
    } else if (t.dataset.xpDay) {
      open('record', t.dataset.xpDay);
    }
  });

  // ---------------------------------------------------------------- the chart

  const COLORS = ['var(--viz-1, #2a78d6)', 'var(--viz-2, #eb6834)', 'var(--viz-3, #1baf7a)', 'var(--viz-4, #eda100)',
    'var(--viz-5, #e87ba4)', 'var(--viz-7, #4a3aa7)'];

  function drawChart() {
    if (scale === null) scale = fraction() ? 'pct' : 'raw';
    const host = $('[data-xp-chart]');
    const t = D.table;
    const xs = t.days.every((d) => d !== null) ? t.days : t.dates.map((_d, i) => i + 1);
    const pct = scale === 'pct';
    const byGroup = new Map();
    t.rows.forEach((r) => {
      const key = r.group || `All ${D.nouns}`;
      if (!byGroup.has(key)) byGroup.set(key, []);
      byGroup.get(key).push(r);
    });
    const series = [...byGroup.entries()].map(([name, rows], gi) => ({
      name, color: COLORS[gi % COLORS.length],
      points: xs.map((x, i) => {
        const have = rows.filter((r) => r.values[i] !== null && r.values[i] !== undefined);
        if (!have.length) return null;
        if (fraction() && pct) {
          const total = have.reduce((a, r) => a + (r.start || 0), 0);
          if (!total) return null;
          return { x, y: (have.reduce((a, r) => a + r.values[i], 0) / total) * 100, sem: 0, n: have.length };
        }
        const vals = have.map((r) => (pct ? r.pct[i] : r.values[i])).filter((v) => v !== null && v !== undefined);
        if (!vals.length) return null;
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const sd = vals.length > 1 ? Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (vals.length - 1)) : 0;
        return { x, y: mean, sem: vals.length > 1 ? sd / Math.sqrt(vals.length) : 0, n: vals.length };
      }).filter(Boolean),
    }));
    const marks = new Map();
    treatmentCols().forEach((c) => {
      if (!marks.has(c.day)) marks.set(c.day, []);
      marks.get(c.day).push(c);
    });
    const all = series.flatMap((s) => s.points.flatMap((p) => [p.y - p.sem, p.y + p.sem]));
    if (!all.length) {
      host.innerHTML = `<p class="xp-empty">No ${esc(D.readout.label.toLowerCase())} yet. ${D.editable ? `<b>${esc(D.readout.verb || 'Record')}</b> the ${esc(D.nouns)}, or type in the sheet's ${esc(D.readout.label)} view.` : ''}</p>`;
      return;
    }
    const dayList = [...new Set([...xs, ...marks.keys()])].sort((a, b) => a - b);
    const xMin = dayList[0];
    const xMax = dayList[dayList.length - 1];
    let yMin = Math.min(...all);
    let yMax = Math.max(...all);
    const pad = (yMax - yMin || 1) * 0.12;
    yMin -= pad; yMax += pad;
    // A count or a percentage never goes below nothing; a percentage of those at the start tops out at all of them.
    if (fraction() || pct) yMin = Math.max(0, yMin);
    if (fraction() && pct) { yMin = 0; yMax = 105; }
    const W = 760; const H = 260; const L = 48; const R = 14; const T = 14; const B = 34;
    const sx = (x) => L + ((x - xMin) / ((xMax - xMin) || 1)) * (W - L - R);
    const sy = (y) => T + (1 - (y - yMin) / ((yMax - yMin) || 1)) * (H - T - B);
    let svg = `<svg viewBox="0 0 ${W} ${H}" class="xp-svg" role="img" aria-label="${esc(D.readout.label)} by group over the days">`;
    for (let i = 0; i <= 4; i += 1) {
      const y = yMin + ((yMax - yMin) * i) / 4;
      svg += `<line x1="${L}" x2="${W - R}" y1="${sy(y)}" y2="${sy(y)}" class="xp-grid"/><text x="${L - 6}" y="${sy(y) + 4}" text-anchor="end" class="xp-axis">${num(y, pct ? 0 : 1)}</text>`;
    }
    dayList.forEach((d) => { svg += `<text x="${sx(d)}" y="${H - B + 17}" text-anchor="middle" class="xp-axis">${d}</text>`; });
    svg += `<text x="${(L + W - R) / 2}" y="${H - 3}" text-anchor="middle" class="xp-axis">day</text>`;
    marks.forEach((_items, d) => {
      svg += `<line x1="${sx(d)}" x2="${sx(d)}" y1="${T}" y2="${H - B}" class="xp-mark"/>`;
    });
    series.forEach((s) => {
      const path = s.points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(' ');
      svg += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.2"/>`;
      s.points.forEach((p) => {
        if (p.sem) svg += `<line x1="${sx(p.x)}" x2="${sx(p.x)}" y1="${sy(p.y - p.sem)}" y2="${sy(p.y + p.sem)}" stroke="${s.color}" stroke-width="1.5"/>`;
        svg += `<circle cx="${sx(p.x)}" cy="${sy(p.y)}" r="4" fill="${s.color}" class="xp-dot" data-tip="${esc(`${s.name}, day ${p.x}: ${num(p.y, pct ? 0 : 1)}${pct ? '%' : (D.readout.unit && !fraction() ? ` ${D.readout.unit}` : '')}${p.sem ? ` ± ${num(p.sem, pct ? 0 : 1)}` : ''} (n = ${p.n})`)}"/>`;
      });
    });
    // Wide, invisible bands on the dashed lines: pointing at one says what was done that day.
    marks.forEach((items, d) => {
      const text = items.map((c) => `${c.title}${c.group ? ` · ${c.group}` : ''} — ${c.record ? `done ${niceDate(c.record.done_on)} by ${c.record.done_by}` : STATE[c.state].toLowerCase()}`);
      svg += `<rect x="${sx(d) - 8}" y="${T}" width="16" height="${H - T - B}" class="xp-hit" data-tip-title="${esc(`Day ${d}${items[0].date ? ` · ${niceDate(items[0].date, true)}` : ''}`)}" data-tip="${esc(text.join('\n'))}"/>`;
    });
    // Stars over the days where the groups differ (the table below has each test).
    const stats = (D.table.stats || {})[pct && !fraction() ? 'pct' : 'raw'] || [];
    stats.forEach((st, i) => {
      if (!st.stars || st.stars === 'ns') return;
      const x = xs[i];
      if (x === undefined) return;
      svg += `<text x="${sx(x)}" y="${T + 10}" text-anchor="middle" class="xp-star" data-tip="${esc(`Day ${x}: ${st.test}, p = ${st.p < 0.001 ? st.p.toExponential(1) : st.p.toFixed(3)}`)}">${st.stars}</text>`;
    });
    svg += '</svg>';
    drawStats(stats);
    const legend = series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('');
    host.innerHTML = `${svg}<div class="xp-tip" hidden></div><div class="xp-legend">${legend}<span class="xp-muted">${fraction() && pct ? '% of those at the start' : 'mean ± SEM'}${marks.size ? ' · dashed: manipulation days (point at one)' : ''}</span></div>`;
  }

  function drawStats(stats) {
    const box = $('[data-xp-stats]');
    const tested = stats.filter((st) => st.test);
    box.hidden = !tested.length;
    if (!tested.length) return;
    const unit = scale === 'pct' || fraction() ? '%' : (D.readout.unit ? ` ${D.readout.unit}` : '');
    $('[data-xp-stats-table]').innerHTML = `<table class="dense-table fit-table"><thead><tr><th>Day</th><th>Groups</th><th>Test</th><th>p</th><th></th></tr></thead><tbody>${
      stats.map((st) => `<tr><td>${st.day !== null ? `Day ${st.day}` : ''} <span class="xp-muted">${esc(niceDate(st.date))}</span></td>
        <td>${st.groups.map((g) => `${esc(g.group)}: ${num(g.value, 2)}${unit}${g.sem != null ? ` ± ${num(g.sem, 2)}` : ''} <span class="xp-muted">n=${g.n}</span>`).join('<br>')}</td>
        <td>${esc(st.test || '—')}</td><td>${st.p == null ? '' : (st.p < 0.001 ? st.p.toExponential(1) : st.p.toFixed(3))}</td><td><b>${esc(st.stars)}</b></td></tr>`).join('')}</tbody></table>`;
  }

  const chartHost = $('[data-xp-chart]');
  chartHost.addEventListener('mousemove', (event) => {
    const target = event.target.closest('[data-tip]');
    const tip = $('.xp-tip', chartHost);
    if (!tip) return;
    if (!target) { tip.hidden = true; return; }
    const title = target.dataset.tipTitle;
    tip.innerHTML = `${title ? `<b>${esc(title)}</b>` : ''}${esc(target.dataset.tip).replace(/\n/g, '<br>')}`;
    tip.hidden = false;
    const box = chartHost.getBoundingClientRect();
    const x = Math.min(event.clientX - box.left + 12, box.width - tip.offsetWidth - 4);
    tip.style.left = `${Math.max(4, x)}px`;
    tip.style.top = `${event.clientY - box.top + 12}px`;
  });
  chartHost.addEventListener('mouseleave', () => { const tip = $('.xp-tip', chartHost); if (tip) tip.hidden = true; });

  // ---------------------------------------------------------------- day by day

  function drawDays() {
    const list = $('[data-xp-days]');
    const done = D.schedule.filter((r) => r.record).length;
    $('[data-xp-days-count]').textContent = D.schedule.length ? `${done} of ${D.schedule.length} done` : '';
    if (!D.schedule.length) {
      list.innerHTML = `<li class="xp-empty">Nothing planned yet.${D.editable ? ' <b>Plan</b> the manipulations and readout days, or <b>Record manipulation</b> as you go.' : ''}</li>`;
      return;
    }
    const byDay = new Map();
    D.schedule.forEach((r) => { if (!byDay.has(r.day)) byDay.set(r.day, []); byDay.get(r.day).push(r); });
    list.innerHTML = [...byDay.entries()].map(([day, rows]) => `
      <li class="xp-day" id="day-${day}"><div class="xp-day-head"><b>Day ${day}</b><span>${esc(niceDate(rows[0].date, true))}</span></div>
      <ul class="xp-items">${rows.map((r) => {
        const rec = r.record;
        const extra = rec ? [rec.reagent && rec.reagent.name ? `${rec.reagent.name}${rec.reagent.lot ? ` lot ${rec.reagent.lot}` : ''}` : '',
          rec.samples && rec.samples.length ? `${rec.samples.length} sample${rec.samples.length === 1 ? '' : 's'} in ${rec.samples[0].inventory}` : ''].filter(Boolean).map(esc).join(' · ') : '';
        const status = rec ? `Done ${esc(niceDate(rec.done_on))} by ${esc(rec.done_by)} · ${rec.count} of ${r.group_size}${extra ? ` · ${extra}` : ''}` : STATE[r.state];
        const action = r.reading
          ? (D.editable ? `<button type="button" class="xp-link" data-xp-open="reading" data-on="${esc(r.date)}">${esc(D.readout.verb || 'Record')}</button>` : '')
          : `<button type="button" class="${rec || !D.editable ? 'xp-link' : 'btn xp-record-btn'}" data-xp-day="${r.step_id}:${r.day}">${rec || !D.editable ? 'Details' : 'Record'}</button>`;
        return `<li class="xp-item" data-state="${esc(r.state)}"><span class="xp-item-icon">${icon(r.icon)}</span>
          <span class="xp-item-body"><b>${esc(r.title)}</b>${r.group ? ` <span class="xp-muted">· ${esc(r.group)}</span>` : ''}
          <span class="xp-status">${status}</span>${rec && rec.note ? `<span class="xp-note">${esc(rec.note)}</span>` : ''}</span>${action}</li>`;
      }).join('')}</ul></li>`).join('');
    const target = window.location.hash && document.getElementById(window.location.hash.slice(1));
    if (target && target.classList.contains('xp-day')) target.classList.add('is-target');
  }

  // ---------------------------------------------------------------- dialogs

  function showError(dialog, text) {
    const el = $('[data-xp-error]', dialog);
    if (el) { el.textContent = text || ''; el.hidden = !text; }
  }

  function fillKinds(select, chosen) {
    select.innerHTML = D.kinds.map((k) => `<option value="${esc(k.key)}" ${k.key === chosen ? 'selected' : ''}>${esc(k.key === 'reading' ? `${D.readout.label} day` : k.label)}</option>`).join('');
  }
  function fillGroups(select, chosen) {
    select.innerHTML = [`<option value="">Every ${esc(D.noun)}</option>`, ...D.groups.map((g) => `<option value="${esc(g)}" ${g === chosen ? 'selected' : ''}>${esc(g)}</option>`)].join('');
  }

  function fillReagents(select, chosen) {
    select.innerHTML = '<option value="">None recorded</option>' + (D.reagents || []).map((r) => `<option value="${r.id}" ${Number(chosen) === r.id ? 'selected' : ''}>${esc(r.label)}${r.expires && r.expires < today() ? ' (expired)' : ''}</option>`).join('');
  }

  function open(which, arg) {
    const dialog = $(`#xp-${which}`);
    if (!dialog) return;
    showError(dialog, '');
    if (which === 'plan') openPlan(dialog);
    if (which === 'record') openRecord(dialog, arg);
    if (which === 'reading') openReading(dialog, arg || '');
    if (!dialog.open) dialog.showModal();
  }

  // Add animals
  function refreshAddOptions(add) {
    const groups = $('[data-xp-add-groups]');
    const single = $('[data-xp-add-single]');
    if (!groups || !single) return;
    groups.innerHTML = '<option value="">—</option>' + add.groups.map(([v, l, n]) => `<option value="${esc(v)}">${esc(l)} (${n})</option>`).join('');
    single.innerHTML = '<option value="">—</option>' + add.single.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
  }
  const addForm = $('[data-xp-form="add"]');
  if (addForm) addForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const dialog = addForm.closest('dialog');
    const f = addForm.elements;
    const body = f.group_value.value ? { how: 'group', value: f.group_value.value } : { how: 'one', value: f.one_value.value };
    if (!body.value) return showError(dialog, `Pick a ${D.housing}, or one.`);
    body.group = f.group.value;
    try {
      const data = await send(`${XP}/subjects/add`, body);
      apply(data);
      addForm.reset();
      say('saved', data.message || 'Added');
      dialog.close();
    } catch (error) { showError(dialog, error.message); }
    return undefined;
  });

  // The plan
  let editing = null;
  function openPlan(dialog) {
    const saved = D.regimens || [];
    $('[data-xp-regimens]', dialog).innerHTML = saved.length ? `<label class="xp-regimen-pick">Start from a saved regimen
      <span class="xp-row"><select data-xp-regimen>${saved.map((r) => `<option value="${r.id}">${esc(r.name)} — ${esc(r.summary)}${r.mine ? '' : ` (${esc(r.owner)})`}</option>`).join('')}</select>
      <button type="button" class="dt-bottom-action" data-xp-regimen-apply>Plan it</button>
      <button type="button" class="xp-link xp-danger" data-xp-regimen-delete aria-label="Delete this saved regimen" title="Delete this saved regimen">×</button></span></label>
      <p class="xp-sub">Planning one adds its days here; each is still recorded as it is done.</p>` : '';
    const list = $('[data-xp-plan-list]', dialog);
    list.innerHTML = D.steps.length ? `<table class="dense-table fit-table xp-plan"><thead><tr><th>Days</th><th>Kind</th><th>What</th><th>Dose</th><th>Route</th><th>Group</th><th></th></tr></thead><tbody>${D.steps.map((s) => `
      <tr><td class="xp-days-cell">Day ${esc(s.days_label)}</td><td><span class="xp-kind">${icon(s.icon)}${esc(s.reading ? `${D.readout.label} day` : s.kind_label)}</span></td>
      <td><b>${esc(s.agent)}</b>${s.notes ? `<div class="xp-muted">${esc(s.notes)}</div>` : ''}</td><td>${esc(s.dose)}${s.concentration ? `<div class="xp-muted">${esc(s.concentration)}</div>` : ''}</td>
      <td>${esc(s.route)}</td><td>${s.group ? esc(s.group) : `<span class="xp-muted">every ${esc(D.noun)}</span>`}</td>
      <td class="xp-actions"><button type="button" class="xp-link" data-xp-edit="${s.id}">Edit</button><button type="button" class="xp-link xp-danger" data-xp-delete="${s.id}" aria-label="Delete">×</button></td></tr>`).join('')}</tbody></table>`
      : '<p class="xp-empty">Nothing planned yet.</p>';
    resetStepForm(dialog, editing && D.steps.find((s) => s.id === editing));
  }
  function resetStepForm(dialog, step) {
    const f = $('[data-xp-form="plan"]').elements;
    fillKinds(f.kind, step ? step.kind : D.kinds[0].key);
    fillGroups(f.group, step ? step.group : '');
    ['id', 'agent', 'days', 'dose', 'route', 'concentration', 'notes'].forEach((n) => { f[n].value = step ? (step[n] || '') : ''; });
    fillReagents(f.reagent_id, step ? step.reagent_id : '');
    $('[data-xp-plan-form-title]', dialog).textContent = step ? 'Change this line' : 'Add to the regimen';
    $('[data-xp-plan-save]', dialog).textContent = step ? 'Save' : 'Add to the regimen';
    $('[data-xp-plan-new]', dialog).hidden = !step;
    editing = step ? step.id : null;
  }
  const planForm = $('[data-xp-form="plan"]');
  if (planForm) {
    planForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const dialog = planForm.closest('dialog');
      const f = planForm.elements;
      const body = Object.fromEntries(['id', 'kind', 'agent', 'days', 'dose', 'route', 'concentration', 'group', 'notes', 'reagent_id'].map((n) => [n, f[n].value]));
      try {
        apply(await send(`${API}/steps/save`, body));
        editing = null;
        showError(dialog, '');
        openPlan(dialog);
      } catch (error) { showError(dialog, error.message); }
    });
    planForm.addEventListener('click', async (event) => {
      const t = event.target.closest('button');
      if (!t) return;
      const dialog = planForm.closest('dialog');
      if (t.dataset.xpEdit) { resetStepForm(dialog, D.steps.find((s) => s.id === Number(t.dataset.xpEdit))); }
      if (t.matches('[data-xp-plan-new]')) resetStepForm(dialog, null);
      if (t.matches('[data-xp-regimen-save]')) {
        if (!D.steps.length) return showError(dialog, 'Plan something first: this experiment has nothing to save yet.');
        const name = await (window.BioDialog ? BioDialog.prompt('Name this regimen', '') : Promise.resolve(window.prompt('Name this regimen')));
        if (!name) return undefined;
        try { const data = await send(`${API}/regimens/save`, { name }); apply(data); openPlan(dialog); say('saved', data.message); } catch (error) { showError(dialog, error.message); }
      }
      if (t.matches('[data-xp-regimen-apply]')) {
        const id = $('[data-xp-regimen]', dialog).value;
        try { const data = await send(`${API}/regimens/${id}/apply`, {}); apply(data); openPlan(dialog); say('saved', data.message); } catch (error) { showError(dialog, error.message); }
      }
      if (t.matches('[data-xp-regimen-delete]')) {
        const r = (D.regimens || []).find((x) => String(x.id) === $('[data-xp-regimen]', dialog).value);
        if (!r || !(await confirmAsk(`Delete the saved regimen ${r.name}? Experiments planned from it keep their days.`, true))) return undefined;
        try { apply(await send(`${API}/regimens/${r.id}/delete`, {})); openPlan(dialog); } catch (error) { showError(dialog, error.message); }
      }
      if (t.dataset.xpDelete) {
        const step = D.steps.find((s) => s.id === Number(t.dataset.xpDelete));
        if (!(await confirmAsk(`Delete ${step.agent || step.kind_label} (day ${step.days_label}) from the plan?`, true))) return;
        try {
          apply(await send(`${API}/steps/${step.id}/delete`, {}));
        } catch (error) {
          if (error.data && error.data.needs_confirm && await confirmAsk(`${error.message} Delete it and those records too?`, true)) {
            apply(await send(`${API}/steps/${step.id}/delete`, { confirm: '1' }));
          }
        }
        openPlan(dialog);
      }
    });
  }

  // Record a manipulation
  let recordCtx = null;
  function openRecord(dialog, preset) {
    const f = $('[data-xp-form="record"]').elements;
    $('[data-xp-form="record"]').reset();
    const rows = treatmentCols();
    const group = (label, list) => (list.length ? `<optgroup label="${label}">${list.map((r) => `<option value="${r.step_id}:${r.day}">Day ${r.day}${r.date ? ` (${niceDate(r.date)})` : ''} · ${esc(r.title)}${r.group ? ` · ${esc(r.group)}` : ''}${r.record ? ' ✓' : ''}</option>`).join('')}</optgroup>` : '');
    const due = rows.filter((r) => !r.record && (r.state === 'today' || r.state === 'overdue'));
    const later = rows.filter((r) => !r.record && (r.state === 'upcoming' || r.state === 'planned'));
    const done = rows.filter((r) => r.record);
    f.which.innerHTML = group('Due', due) + '<option value="adhoc">Something not in the plan…</option>' + group('To come', later) + group('Done: change it', done);
    f.which.value = preset || (due[0] ? `${due[0].step_id}:${due[0].day}` : 'adhoc');
    fillKinds(f.kind, D.kinds[0].key);
    fillGroups(f.group, '');
    f.done_on.value = today();
    f.done_on.max = today();
    const inventories = D.sample_inventories || [];
    $('[data-xp-samples]', dialog).hidden = !inventories.length;
    $('[data-xp-sample-inventories]', dialog).innerHTML = inventories.map((i) => `<option value="${esc(i.key)}">${esc(i.label)}</option>`).join('');
    $('[data-xp-sample-fields]', dialog).hidden = true;
    chooseRecord(dialog);
  }

  async function chooseRecord(dialog, on) {
    const form = $('[data-xp-form="record"]');
    const f = form.elements;
    const adhoc = f.which.value === 'adhoc';
    $('[data-xp-adhoc]', dialog).hidden = !adhoc;
    let data;
    try {
      if (adhoc) {
        const q = new URLSearchParams({ dose: f.dose.value, concentration: f.concentration.value, group: f.group.value, on: f.done_on.value || today(), kind: f.kind.value });
        data = await get(`${API}/preview?${q}`);
        recordCtx = { adhoc: true, data };
      } else {
        const [stepId, day] = f.which.value.split(':');
        data = await get(`${API}/steps/${stepId}/day/${day}${on ? `?on=${encodeURIComponent(on)}` : ''}`);
        recordCtx = { adhoc: false, stepId, day, data };
        if (!on) f.done_on.value = data.on;
        if (!on && data.record) f.note.value = data.record.note || '';
      }
    } catch (error) { showError(dialog, error.message); return; }
    const step = data.step || { dose: f.dose.value, per_weight: /\/\s*(k?g)\s*$/i.test(f.dose.value) };
    $('[data-xp-record-sub]', dialog).textContent = adhoc
      ? (D.start_date ? `Day ${dayOf(f.done_on.value)} of the experiment. It joins the plan, done.` : 'The experiment has no start date yet: this day becomes day 1.')
      : [data.planned ? `Planned for ${niceDate(data.planned, true)}` : '', data.record ? `recorded by ${data.record.done_by}` : ''].filter(Boolean).join(' · ');
    $('[data-xp-dose-note]', dialog).textContent = D.weighs && step.per_weight
      ? `${step.dose} from each ${D.noun}'s latest weight on or before that day${step.concentration ? `, as ${step.concentration}` : ''}.` : '';
    const weighs = D.weighs;
    $('[data-xp-animals-head]', dialog).innerHTML = `<tr><th><input type="checkbox" data-xp-all checked aria-label="All"></th><th>${esc(D.noun.charAt(0).toUpperCase() + D.noun.slice(1))}</th><th>Group</th>${weighs ? '<th>Weight</th>' : (D.family !== 'mouse' ? '<th>At start</th>' : '')}<th>Amount</th><th>Volume</th></tr>`;
    const animals = data.animals || data.mice || [];
    $('[data-xp-animals]', dialog).innerHTML = animals.length ? animals.map((a) => `<tr>
      <td><input type="checkbox" data-xp-animal="${esc(a.subject)}" ${a.given ? 'checked' : ''} aria-label="${esc(a.label)}"></td>
      <td>${esc(a.label)} <span class="xp-muted">${esc(a.sex || '')}</span></td><td>${esc(a.group)}</td>
      ${weighs ? `<td>${a.grams != null ? `${num(a.grams)} g <span class="xp-muted">${esc(niceDate(a.weighed_on))}</span>` : '<span class="xp-muted">no weight</span>'}</td>` : (D.family !== 'mouse' ? `<td>${a.start == null ? '' : a.start}</td>` : '')}
      <td>${a.needs ? '<span class="xp-warn">needs a weight</span>' : esc(a.amount || '')}</td><td>${esc(a.volume || '')}</td></tr>`).join('')
      : `<tr><td colspan="6" class="xp-muted">No ${esc(D.nouns)} in this group.</td></tr>`;
    if (!on) fillReagents(f.reagent_id, adhoc ? '' : ((data.record && data.record.reagent && data.record.reagent.id) || (data.step && data.step.reagent_id) || ''));
    const made = (data.record && data.record.samples) || [];
    $('[data-xp-samples-made]', dialog).textContent = made.length ? `Sample records made: ${made.map((m) => `#${m.number}`).join(', ')} in ${made[0].inventory}.` : '';
    $('.xp-check', dialog).hidden = made.length > 0;
    const kind = adhoc ? f.kind.value : (data.step && data.step.kind);
    if (kind === 'sample' && !made.length && !f.sample_name.value) f.sample_name.value = adhoc ? f.agent.value : (data.step.agent || '');
    $('[data-xp-undo]', dialog).hidden = !(recordCtx.data.record);
    $('[data-xp-record-save]', dialog).textContent = recordCtx.data.record ? 'Save' : 'Record as done';
  }

  const dayOf = (iso) => (D.start_date && iso ? Math.round((new Date(`${iso}T12:00:00`) - new Date(`${D.start_date}T12:00:00`)) / 86400000) + 1 : '');

  const recordForm = $('[data-xp-form="record"]');
  if (recordForm) {
    let timer = null;
    recordForm.addEventListener('change', (event) => {
      const dialog = recordForm.closest('dialog');
      const t = event.target;
      if (t.matches('[data-xp-all]')) { $$('[data-xp-animal]', dialog).forEach((b) => { b.checked = t.checked; }); return; }
      if (t.name === 'make_samples') { $('[data-xp-sample-fields]', dialog).hidden = !t.checked; return; }
      if (['reagent_id', 'sample_inventory', 'sample_name', 'note'].includes(t.name)) return;
      if (t.name === 'which') {
        if (t.value === 'adhoc') recordForm.elements.done_on.value = today();   // something done now, usually
        chooseRecord(dialog);
      }
      else if (t.name === 'done_on') chooseRecord(dialog, recordCtx && !recordCtx.adhoc ? t.value : undefined);
      else if (['dose', 'concentration', 'group', 'kind'].includes(t.name)) chooseRecord(dialog);
    });
    recordForm.addEventListener('input', (event) => {
      if (!['dose', 'concentration'].includes(event.target.name)) return;
      clearTimeout(timer);
      timer = setTimeout(() => chooseRecord(recordForm.closest('dialog')), 400);
    });
    recordForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const dialog = recordForm.closest('dialog');
      const f = recordForm.elements;
      const subjects = $$('[data-xp-animal]:checked', dialog).map((b) => b.dataset.xpAnimal);
      const common = { done_on: f.done_on.value, subjects, note: f.note.value, reagent_id: f.reagent_id.value,
        make_samples: Boolean(f.make_samples && f.make_samples.checked), sample_inventory: f.sample_inventory ? f.sample_inventory.value : '',
        sample_name: f.sample_name ? f.sample_name.value : '' };
      try {
        const data = recordCtx.adhoc
          ? await send(`${API}/record-now`, { ...common, kind: f.kind.value, agent: f.agent.value, dose: f.dose.value, route: f.route.value, concentration: f.concentration.value, group: f.group.value })
          : await send(`${API}/steps/${recordCtx.stepId}/day/${recordCtx.day}/record`, common);
        apply(data);
        dialog.close();
        const notes = [data.message, ...(data.problems || [])].filter(Boolean);
        if (notes.length) alertSay(notes.join('\n'));
      } catch (error) { showError(dialog, error.message); }
    });
    $('[data-xp-undo]').addEventListener('click', async () => {
      if (!recordCtx || recordCtx.adhoc) return;
      if (!(await confirmAsk('Mark this day as not done?'))) return;
      try {
        apply(await send(`${API}/steps/${recordCtx.stepId}/day/${recordCtx.day}/undo`, {}));
        recordForm.closest('dialog').close();
      } catch (error) { showError(recordForm.closest('dialog'), error.message); }
    });
  }

  // A readout day
  function openReading(dialog, on) {
    const form = $('[data-xp-form="reading"]');
    const day = on && on <= today() ? on : today();
    form.elements.on.value = day;
    form.elements.on.max = today();
    $('#xp-reading-title').textContent = `${D.readout.verb || 'Record'}: ${D.readout.label}`;
    $('[data-xp-reading-sub]', dialog).textContent = fraction()
      ? `How many ${D.readout.unit || ''} of those each started with.`.replace('  ', ' ')
      : `${D.readout.label}${D.readout.unit ? ` in ${D.readout.unit}` : ''}; leave one blank to skip it.`;
    drawReadingRows(dialog, day);
  }
  function drawReadingRows(dialog, day) {
    const idx = D.table.dates.indexOf(day);
    const rows = Object.fromEntries(D.table.rows.map((r) => [r.key, r]));
    $('[data-xp-reading-rows]', dialog).innerHTML = D.subjects.map((s) => {
      const r = rows[s.key] || { values: [] };
      const current = idx >= 0 ? r.values[idx] : null;
      const before = [...D.table.dates.keys()].filter((i) => D.table.dates[i] < day && r.values[i] != null).pop();
      return `<tr><td>${esc(s.label)} <span class="xp-muted">${esc(s.group)}</span></td>
        <td><input class="xp-cell xp-num" name="v-${esc(s.key)}" data-key="${esc(s.key)}" inputmode="decimal" value="${current == null ? '' : num(current, 2)}" aria-label="${esc(s.label)}">${fraction() && s.start != null ? ` <span class="xp-of">/ ${s.start}</span>` : ''}</td>
        <td class="xp-muted">${before !== undefined ? `before: ${num(r.values[before], 2)} (${esc(niceDate(D.table.dates[before]))})` : ''}</td></tr>`;
    }).join('') || `<tr><td class="xp-muted">No ${esc(D.nouns)} yet.</td></tr>`;
  }
  const readingForm = $('[data-xp-form="reading"]');
  if (readingForm) {
    readingForm.elements.on.addEventListener('change', (e) => drawReadingRows(readingForm.closest('dialog'), e.target.value));
    readingForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const dialog = readingForm.closest('dialog');
      const values = {};
      $$('[data-key]', dialog).forEach((i) => { if (i.value.trim() !== '' || D.table.dates.includes(readingForm.elements.on.value)) values[i.dataset.key] = i.value; });
      try {
        const data = await send(`${XP}/readings`, { on: readingForm.elements.on.value, values });
        apply(data);
        dialog.close();
        if (data.problems && data.problems.length) alertSay(`Saved, except:\n${data.problems.join('\n')}`);
      } catch (error) { showError(dialog, error.message); }
    });
  }

  // ---------------------------------------------------------------- the details, autosaved

  const info = $('[data-xp-info]');
  if (info) {
    let timer = null;
    const save = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        try { apply(await send(info.action, new FormData(info), { form: true })); } catch (_e) { /* shown */ }
      }, 350);
    };
    $$('[data-autosave]', info).forEach((el) => {
      el.addEventListener('input', () => { if (el.tagName !== 'SELECT') save(); });
      el.addEventListener('change', save);
    });
    const readout = $('[data-xp-readout]', info);
    if (readout) readout.addEventListener('change', () => { $('[data-xp-custom]', info).hidden = readout.value !== 'custom'; });
  }

  drawSheet();
  drawChart();
  drawDays();
  drawLabels();
  if (window.location.hash.startsWith('#day-')) {
    const target = document.getElementById(window.location.hash.slice(1));
    if (target) target.scrollIntoView({ block: 'center' });
  }
})();
