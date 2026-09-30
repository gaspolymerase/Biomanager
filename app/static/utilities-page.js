/* Utilities: the list of calculators, the one open, and the reference
   tables (templates/utilities.html). The arithmetic is static/bench-calcs.js;
   this draws a calculator's fields from its description, runs it on every
   keystroke and shows the answer. The open calculator is in the address
   (#dilution), so a link opens it; what was typed in each is kept in this
   browser. */
(function () {
  'use strict';

  const B = window.BenchCalc;
  const root = document.querySelector('[data-util]');
  if (!B || !root) return;

  const list = root.querySelector('[data-util-list]');
  const card = root.querySelector('[data-util-card]');
  const search = root.querySelector('[data-util-search]');
  const refs = root.querySelector('[data-util-refs]');
  const KEY = 'biomanager:util:';

  // The lab's own chemicals (Utilities' reference list) come first in the
  // chemical picker, then the built-in ones.
  let labChemicals = [];
  try { labChemicals = JSON.parse(document.getElementById('util-lab-chemicals').textContent || '[]'); } catch (_) {}
  const chemicals = new Map();
  labChemicals.forEach((c) => { if (c.name && c.mw > 0) chemicals.set(c.name, c.mw); });
  B.CHEMICALS.forEach(([name, mw]) => { if (!chemicals.has(name)) chemicals.set(name, mw); });
  const datalist = document.getElementById('util-chemicals');
  chemicals.forEach((mw, name) => {
    const o = document.createElement('option');
    o.value = name;
    o.label = `${mw} g/mol`;
    datalist.appendChild(o);
  });

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const load = (id) => { try { return JSON.parse(localStorage.getItem(KEY + id) || 'null'); } catch (_) { return null; } };
  const save = (id, data) => { try { localStorage.setItem(KEY + id, JSON.stringify(data)); } catch (_) {} };
  const forget = (id) => { try { localStorage.removeItem(KEY + id); } catch (_) {} };

  /* ------------------------------------------------------------- the list */

  const groups = [];
  B.CALCS.forEach((c) => {
    let g = groups.find((x) => x.name === c.group);
    if (!g) { g = { name: c.group, calcs: [] }; groups.push(g); }
    g.calcs.push(c);
  });
  list.innerHTML = groups.map((g) => `
    <div class="util-group" data-util-group>
      <div class="util-group-label">${esc(g.name)}</div>
      ${g.calcs.map((c) => `<a class="util-link" href="#${c.id}" data-util-link="${c.id}"
          data-search="${esc(`${c.title} ${c.blurb} ${g.name}`.toLowerCase())}">${esc(c.title)}</a>`).join('')}
    </div>`).join('') + '<a class="util-link util-link-ref" href="#reference" data-search="reference tables buffers antibiotics vessels plates isotopes gels chemicals molecular weight">Reference tables</a>';

  search.addEventListener('input', () => {
    const q = search.value.trim().toLowerCase();
    list.querySelectorAll('[data-search]').forEach((a) => { a.hidden = q && !a.dataset.search.includes(q); });
    list.querySelectorAll('[data-util-group]').forEach((g) => { g.hidden = ![...g.querySelectorAll('[data-util-link]')].some((a) => !a.hidden); });
  });
  search.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const first = [...list.querySelectorAll('[data-util-link]')].find((a) => !a.hidden);
    if (first) { e.preventDefault(); location.hash = first.dataset.utilLink; }
  });

  /* ------------------------------------------------------ one calculator */

  function unitSelect(inp, chosen) {
    const opts = B.UNITS[inp.units] || [];
    return `<select data-unit="${inp.key}" aria-label="${esc(inp.label)} unit">${opts.map(([u]) =>
      `<option${u === chosen ? ' selected' : ''}>${esc(u)}</option>`).join('')}</select>`;
  }

  function field(inp, saved) {
    const value = saved && saved[inp.key] != null ? saved[inp.key] : (inp.value || '');
    const hint = inp.hint ? `<small class="util-hint">${esc(inp.hint)}</small>` : '';
    if (inp.type === 'select') {
      return `<label class="util-field"><span>${esc(inp.label)}</span><select data-key="${inp.key}">${inp.options.map(([val, label]) =>
        `<option value="${esc(val)}"${String(value || inp.options[0][0]) === String(val) ? ' selected' : ''}>${esc(label)}</option>`).join('')}</select>${hint}</label>`;
    }
    if (inp.type === 'textarea') {
      return `<label class="util-field is-wide"><span>${esc(inp.label)}</span><textarea data-key="${inp.key}" rows="5" spellcheck="false"
        placeholder="${esc(inp.placeholder || '')}">${esc(value)}</textarea>${hint}</label>`;
    }
    if (inp.type === 'chemical') {
      return `<label class="util-field is-wide"><span>${esc(inp.label)}</span><input data-key="${inp.key}" list="util-chemicals" autocomplete="off"
        placeholder="Type a name to fill the molecular weight" value="${esc(value)}">${hint}</label>`;
    }
    const wide = inp.type === 'text' ? ' is-wide' : '';
    const unit = inp.units ? unitSelect(inp, (saved && saved[`${inp.key}_unit`]) || inp.unit) : '';
    return `<label class="util-field${wide}" data-field="${inp.key}"><span>${esc(inp.label)}</span>
      <span class="util-input"><input data-key="${inp.key}" ${inp.type === 'text' ? 'spellcheck="false" class="font-mono"' : 'inputmode="decimal"'}
        autocomplete="off" value="${esc(value)}" placeholder="${esc(inp.placeholder || '')}">${unit}</span>${hint}</label>`;
  }

  function results(out) {
    if (out.error) return `<p class="util-error">${esc(out.error)}</p>`;
    if (out.hint && !(out.lines || []).length && !out.table) return `<p class="util-muted">${esc(out.hint)}</p>`;
    let html = '';
    if ((out.lines || []).length) {
      html += `<dl class="util-answers">${out.lines.map((l) => `<div class="${l.main ? 'is-main' : ''}"><dt>${esc(l.label)}</dt><dd>${esc(l.value)}</dd></div>`).join('')}</dl>`;
    }
    if (out.table) {
      html += `<div class="util-table-wrap"><table class="util-table"><thead><tr>${out.table.head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
        <tbody>${out.table.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    (out.warnings || []).forEach((w) => { html += `<p class="util-warn">${esc(w)}</p>`; });
    (out.notes || []).forEach((w) => { html += `<p class="util-note">${esc(w)}</p>`; });
    if (out.hint) html += `<p class="util-muted">${esc(out.hint)}</p>`;
    return html;
  }

  function open(id) {
    const calc = B.CALCS.find((c) => c.id === id) || B.CALCS[0];
    list.querySelectorAll('[data-util-link]').forEach((a) => a.classList.toggle('is-active', a.dataset.utilLink === calc.id));
    const saved = load(calc.id);
    card.innerHTML = `
      <header class="card-head util-head">
        <div><h2>${esc(calc.title)}</h2><p class="util-blurb">${esc(calc.blurb || '')}</p></div>
        <button type="button" class="btn btn-sm btn-ghost" data-util-reset title="Back to the example values">Reset</button>
      </header>
      <form class="util-form" autocomplete="off">${calc.inputs.map((inp) => field(inp, saved)).join('')}</form>
      <div class="util-results" data-util-results></div>`;
    const form = card.querySelector('form');
    const out = card.querySelector('[data-util-results]');
    form.addEventListener('submit', (e) => e.preventDefault());
    const read = () => {
      const raw = {};
      form.querySelectorAll('[data-key]').forEach((el) => { raw[el.dataset.key] = el.value; });
      form.querySelectorAll('[data-unit]').forEach((el) => { raw[`${el.dataset.unit}_unit`] = el.value; });
      return raw;
    };
    const update = () => {
      const raw = read();
      const answer = B.run(calc.id, raw);
      out.innerHTML = results(answer);
      form.querySelectorAll('[data-field]').forEach((f) => f.classList.toggle('is-solved', f.dataset.field === answer.solved));
      save(calc.id, raw);
    };
    form.addEventListener('input', (e) => {
      // A chemical picked from the list fills its molecular weight.
      if (e.target.dataset.key === 'chem' && chemicals.has(e.target.value)) {
        const mw = form.querySelector('[data-key="mw"]');
        if (mw) mw.value = chemicals.get(e.target.value);
      }
      update();
    });
    form.addEventListener('change', update);
    card.querySelector('[data-util-reset]').addEventListener('click', () => { forget(calc.id); open(calc.id); });
    update();
    document.title = `${calc.title} · Utilities`;
  }

  /* ---------------------------------------------------- reference tables */

  const chemRows = [...chemicals.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([name, mw]) => [name, B.fmt(mw, 6)]);
  refs.innerHTML = [...B.REFERENCES, { id: 'ref-chemicals', title: 'Molecular weights', head: ['Chemical', 'g/mol'], rows: chemRows }]
    .map((r) => `<section class="util-ref" id="${r.id}"><h3>${esc(r.title)}</h3><div class="util-table-wrap"><table class="util-table">
      <thead><tr>${r.head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${r.rows.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`).join('');

  const fromHash = () => {
    const id = decodeURIComponent(location.hash.slice(1));
    if (id === 'reference') { root.querySelector('#reference').open = true; return; }
    if (B.CALCS.some((c) => c.id === id)) open(id);
  };
  window.addEventListener('hashchange', fromHash);
  let last = null;
  try { last = localStorage.getItem(`${KEY}last`); } catch (_) {}
  const first = decodeURIComponent(location.hash.slice(1));
  open(B.CALCS.some((c) => c.id === first) ? first : (last || B.CALCS[0].id));
  if (first === 'reference') fromHash();
  window.addEventListener('hashchange', () => {
    try { localStorage.setItem(`${KEY}last`, location.hash.slice(1)); } catch (_) {}
  });
})();
