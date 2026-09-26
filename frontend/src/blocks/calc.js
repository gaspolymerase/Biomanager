// Bench calculators, one block each, kept in the page with the numbers
// used: dilution (C1V1 = C2V2), molarity, master mix, serial dilution,
// ligation insert amount, cell counting and seeding, agarose gel, and
// nucleic acid concentration and copy number. Leave one field of a
// dilution or molarity blank and it is worked out.

import { debounce, el, escapeHtml, fmt, toNumber } from '../util.js';
import { concOptions, family, fromBase, litres, showMass, showVolume, toBase, unitOptions, MASS_UNITS, VOLUME_UNITS } from './units.js';

export const CALC_TYPES = {
  dilution: 'Dilution (C₁V₁ = C₂V₂)',
  molarity: 'Molarity / mass',
  mastermix: 'Master mix',
  serial: 'Serial dilution',
  ligation: 'Ligation insert',
  cells: 'Cell count & seeding',
  gel: 'Agarose gel',
  nucleic: 'DNA / RNA',
};

const DEFAULTS = {
  dilution: { c1: '', c1Unit: 'mM', v1: '', v1Unit: 'µL', c2: '', c2Unit: 'µM', v2: '', v2Unit: 'mL' },
  molarity: { mass: '', massUnit: 'g', volume: '', volumeUnit: 'mL', conc: '', concUnit: 'mM', mw: '' },
  mastermix: { reactions: 8, overage: 10, template: 2, components: [{ name: '2× master mix', perRxn: 10 }, { name: 'Forward primer (10 µM)', perRxn: 1 }, { name: 'Reverse primer (10 µM)', perRxn: 1 }, { name: 'Water', perRxn: 6 }] },
  serial: { start: 10, unit: 'µM', factor: 10, steps: 6, volume: 100, volumeUnit: 'µL' },
  ligation: { vectorNg: 50, vectorBp: 5000, insertBp: 1000, ratio: 3 },
  cells: { counted: '', squares: 4, dilution: 2, target: 100000, wells: 6, perWell: 2, perWellUnit: 'mL', overage: 10 },
  gel: { percent: 1, volume: 50 },
  nucleic: { a260: '', kind: 'dsDNA', dilution: 1, ng: '', bp: '' },
};

export function defaultCalc(type = 'dilution') {
  return { type, ...JSON.parse(JSON.stringify(DEFAULTS[type] || DEFAULTS.dilution)) };
}

const n = toNumber;
const ok = (v) => Number.isFinite(v);

function solveDilution(d) {
  // Work in base units: concentrations of one family, volumes in litres.
  const fam = family(d.c1Unit);
  if (fam !== family(d.c2Unit)) return { error: 'C₁ and C₂ must be the same kind of unit' };
  const vals = { c1: toBase(n(d.c1), d.c1Unit), v1: litres(n(d.v1), d.v1Unit), c2: toBase(n(d.c2), d.c2Unit), v2: litres(n(d.v2), d.v2Unit) };
  const blank = Object.keys(vals).filter((k) => !ok(vals[k]));
  if (blank.length !== 1) return { hint: 'Fill in three of the four; the blank one is worked out.' };
  const k = blank[0];
  let v;
  if (k === 'c1') v = vals.c2 * vals.v2 / vals.v1;
  if (k === 'v1') v = vals.c2 * vals.v2 / vals.c1;
  if (k === 'c2') v = vals.c1 * vals.v1 / vals.v2;
  if (k === 'v2') v = vals.c1 * vals.v1 / vals.c2;
  const shown = k === 'c1' ? `${fmt(fromBase(v, d.c1Unit))} ${d.c1Unit}` : k === 'c2' ? `${fmt(fromBase(v, d.c2Unit))} ${d.c2Unit}` : showVolume(v);
  const v1 = k === 'v1' ? v : vals.v1;
  const v2 = k === 'v2' ? v : vals.v2;
  const extra = ok(v1) && ok(v2) && v2 >= v1 ? `Add ${showVolume(v1)} of stock to ${showVolume(v2 - v1)} of diluent (1 : ${fmt(v2 / v1, 3)}).` : '';
  const warn = (k === 'c2' || k === 'c1') ? '' : ((k === 'v1' && v > vals.v2) ? 'The stock is weaker than the final concentration.' : '');
  return { key: k, value: v, shown, extra, warn };
}

function solveMolarity(d) {
  const mass = n(d.mass) * (MASS_UNITS[d.massUnit] ?? NaN);
  const vol = litres(n(d.volume), d.volumeUnit);
  const conc = toBase(n(d.conc), d.concUnit);
  const mw = n(d.mw);
  const vals = { mass, volume: vol, conc, mw };
  const blank = Object.keys(vals).filter((k) => !ok(vals[k]));
  if (blank.length !== 1) return { hint: 'Fill in three of mass, volume, concentration and molecular weight.' };
  const k = blank[0];
  let v;
  if (k === 'mass') v = conc * vol * mw;
  if (k === 'volume') v = mass / (conc * mw);
  if (k === 'conc') v = mass / (vol * mw);
  if (k === 'mw') v = mass / (conc * vol);
  const shown = k === 'mass' ? showMass(v) : k === 'volume' ? showVolume(v) : k === 'conc' ? `${fmt(fromBase(v, d.concUnit))} ${d.concUnit}` : `${fmt(v)} g/mol`;
  return { key: k, value: v, shown };
}

function field(key, value, label, { unit, units, conc, wide, placeholder, dis, solved } = {}) {
  const unitSel = unit !== undefined
    ? `<select data-k="${key}Unit"${dis}>${conc ? concOptions(unit, conc === true ? null : conc) : unitOptions(units, unit)}</select>` : '';
  return `<label class="nb-calc-field${wide ? ' is-wide' : ''}${solved ? ' is-solved' : ''}"><span>${label}</span><span class="nb-calc-input"><input data-k="${key}" inputmode="decimal" value="${escapeHtml(value ?? '')}" placeholder="${escapeHtml(placeholder || '')}"${dis}>${unitSel}</span></label>`;
}

export function mountCalc(host, ctx) {
  let data = { ...defaultCalc(ctx.data && ctx.data.type), ...(ctx.data || {}) };
  let editable = ctx.editable;
  const commit = debounce(() => ctx.commit(JSON.parse(JSON.stringify(data))), 350);
  const root = el('div', { class: 'nb-calc' });
  host.appendChild(root);

  function results() {
    const d = data;
    if (d.type === 'dilution') {
      const r = solveDilution(d);
      if (r.error || r.hint) return `<p class="${r.error ? 'nb-warn' : 'nb-muted'}">${escapeHtml(r.error || r.hint)}</p>`;
      return `<p class="nb-calc-answer">${{ c1: 'C₁', v1: 'V₁', c2: 'C₂', v2: 'V₂' }[r.key]} = <b>${r.shown}</b></p>${r.extra ? `<p>${r.extra}</p>` : ''}${r.warn ? `<p class="nb-warn">${r.warn}</p>` : ''}`;
    }
    if (d.type === 'molarity') {
      const r = solveMolarity(d);
      if (r.hint) return `<p class="nb-muted">${r.hint}</p>`;
      return `<p class="nb-calc-answer">${{ mass: 'Mass', volume: 'Volume', conc: 'Concentration', mw: 'Molecular weight' }[r.key]} = <b>${r.shown}</b></p>`;
    }
    if (d.type === 'mastermix') {
      const reactions = n(d.reactions);
      const factor = reactions * (1 + (n(d.overage) || 0) / 100);
      let perRxn = 0;
      const rows = (d.components || []).map((c) => {
        const per = n(c.perRxn);
        if (ok(per)) perRxn += per;
        return `<tr><td>${escapeHtml(c.name || '')}</td><td class="is-num">${ok(per) ? fmt(per) : ''}</td><td class="is-num"><b>${ok(per) && ok(factor) ? fmt(per * factor) : ''}</b></td></tr>`;
      }).join('');
      const tmpl = n(d.template);
      return `<table class="nb-stats-table"><thead><tr><th>Component</th><th>per reaction (µL)</th><th>for ${ok(factor) ? fmt(factor, 3) : '—'} (µL)</th></tr></thead><tbody>${rows}
        <tr class="is-total"><th>Mix</th><td class="is-num">${fmt(perRxn)}</td><td class="is-num"><b>${ok(factor) ? fmt(perRxn * factor) : ''}</b></td></tr></tbody></table>
        <p>Put <b>${fmt(perRxn)} µL</b> of mix in each well${ok(tmpl) && tmpl > 0 ? `, then <b>${fmt(tmpl)} µL</b> template: <b>${fmt(perRxn + tmpl)} µL</b> per reaction` : ''}.</p>`;
    }
    if (d.type === 'serial') {
      const start = n(d.start);
      const f = n(d.factor);
      const steps = Math.min(30, Math.max(1, Math.round(n(d.steps)) || 1));
      const v = litres(n(d.volume), d.volumeUnit);
      if (!ok(start) || !ok(f) || f <= 1 || !ok(v)) return '<p class="nb-muted">Starting concentration, a factor above 1, and the volume in each tube.</p>';
      const transfer = v / (f - 1);
      const rows = [];
      for (let i = 0; i <= steps; i++) rows.push(`<tr><td>${i === 0 ? 'Stock' : `Tube ${i}`}</td><td class="is-num">${fmt(start / f ** i)} ${escapeHtml(d.unit)}</td></tr>`);
      return `<p>Put <b>${showVolume(v)}</b> of diluent in each tube, then carry <b>${showVolume(transfer)}</b> from one to the next, mixing each time (every tube ends with ${showVolume(v + transfer)} before its transfer out).</p>
        <table class="nb-stats-table"><thead><tr><th></th><th>Concentration</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
    }
    if (d.type === 'ligation') {
      const ins = n(d.vectorNg) * n(d.insertBp) / n(d.vectorBp) * n(d.ratio);
      const pmolV = n(d.vectorNg) / (n(d.vectorBp) * 650) * 1000;
      return ok(ins) ? `<p class="nb-calc-answer">Insert: <b>${fmt(ins)} ng</b> for ${fmt(n(d.ratio))} : 1 insert : vector</p><p class="nb-muted">Vector ${fmt(pmolV * 1000)} fmol; insert ${fmt(pmolV * n(d.ratio) * 1000)} fmol (650 g/mol per bp).</p>` : '<p class="nb-muted">Vector amount and both lengths.</p>';
    }
    if (d.type === 'cells') {
      const perSquare = n(d.counted) / n(d.squares);
      const perMl = perSquare * n(d.dilution) * 1e4;
      const needed = n(d.target) * n(d.wells) * (1 + (n(d.overage) || 0) / 100);
      const suspL = needed / perMl / 1000;
      const totalL = litres(n(d.perWell), d.perWellUnit) * n(d.wells) * (1 + (n(d.overage) || 0) / 100);
      if (!ok(perMl)) return '<p class="nb-muted">Cells counted over the large squares of a haemocytometer.</p>';
      return `<p class="nb-calc-answer"><b>${fmt(perMl, 3)}</b> cells/mL</p>${ok(suspL) ? `<p>For ${fmt(n(d.target), 3)} cells in each of ${fmt(n(d.wells))} wells (+${fmt(n(d.overage) || 0)}%): <b>${showVolume(suspL)}</b> of cells${ok(totalL) ? ` in <b>${showVolume(totalL)}</b> total (add ${showVolume(totalL - suspL)} medium); ${showVolume(totalL / (n(d.wells) * (1 + (n(d.overage) || 0) / 100)))} per well` : ''}.</p>${ok(totalL) && suspL > totalL ? '<p class="nb-warn">The cells alone are more than the volume: concentrate them first.</p>' : ''}` : ''}`;
    }
    if (d.type === 'gel') {
      const g = n(d.percent) / 100 * n(d.volume);
      return ok(g) ? `<p class="nb-calc-answer">Agarose: <b>${fmt(g)} g</b> in ${fmt(n(d.volume))} mL of 1× buffer</p>` : '<p class="nb-muted">Gel percentage and volume.</p>';
    }
    if (d.type === 'nucleic') {
      const factor = { dsDNA: 50, ssDNA: 33, RNA: 40, oligo: 20 }[d.kind] || 50;
      const conc = n(d.a260) * factor * (n(d.dilution) || 1);
      const copies = n(d.ng) * 1e-9 * 6.02214076e23 / (n(d.bp) * (d.kind === 'dsDNA' ? 650 : 330));
      return `${ok(conc) ? `<p class="nb-calc-answer"><b>${fmt(conc)} ng/µL</b> (${d.kind}, A₂₆₀ × ${factor} × dilution)</p>` : ''}
        ${ok(copies) ? `<p><b>${fmt(copies, 3)}</b> copies in ${fmt(n(d.ng))} ng of ${fmt(n(d.bp))} ${d.kind === 'dsDNA' ? 'bp' : 'nt'}</p>` : ''}
        ${!ok(conc) && !ok(copies) ? '<p class="nb-muted">An A₂₆₀ reading for concentration; mass and length for copy number.</p>' : ''}`;
    }
    return '';
  }

  function render() {
    const d = data;
    const dis = editable ? '' : ' disabled';
    const typeSel = `<select class="nb-calc-type" data-k="type"${dis}>${Object.entries(CALC_TYPES).map(([k, v]) => `<option value="${k}"${d.type === k ? ' selected' : ''}>${v}</option>`).join('')}</select>`;
    let fields = '';
    if (d.type === 'dilution') {
      const solved = solveDilution(d).key;
      fields = field('c1', d.c1, 'Stock C₁', { unit: d.c1Unit, conc: true, dis, solved: solved === 'c1' })
        + field('v1', d.v1, 'Volume V₁', { unit: d.v1Unit, units: VOLUME_UNITS, dis, solved: solved === 'v1' })
        + field('c2', d.c2, 'Final C₂', { unit: d.c2Unit, conc: [family(d.c1Unit)], dis, solved: solved === 'c2' })
        + field('v2', d.v2, 'Final volume V₂', { unit: d.v2Unit, units: VOLUME_UNITS, dis, solved: solved === 'v2' });
    } else if (d.type === 'molarity') {
      const solved = solveMolarity(d).key;
      fields = field('mass', d.mass, 'Mass', { unit: d.massUnit, units: MASS_UNITS, dis, solved: solved === 'mass' })
        + field('volume', d.volume, 'Volume', { unit: d.volumeUnit, units: VOLUME_UNITS, dis, solved: solved === 'volume' })
        + field('conc', d.conc, 'Concentration', { unit: d.concUnit, conc: ['molar'], dis, solved: solved === 'conc' })
        + field('mw', d.mw, 'MW (g/mol)', { dis, solved: solved === 'mw' });
    } else if (d.type === 'mastermix') {
      fields = field('reactions', d.reactions, 'Reactions', { dis }) + field('overage', d.overage, 'Extra %', { dis }) + field('template', d.template, 'Template µL / rxn', { dis })
        + `<div class="nb-calc-list">${(d.components || []).map((c, i) => `<div class="nb-calc-row" data-i="${i}"><input data-m="name" value="${escapeHtml(c.name || '')}" placeholder="Component"${dis}><input data-m="perRxn" inputmode="decimal" value="${escapeHtml(c.perRxn ?? '')}" placeholder="µL"${dis}>${editable ? `<button type="button" class="nb-icon-btn" data-remove="${i}" aria-label="Remove">×</button>` : ''}</div>`).join('')}${editable ? '<button type="button" class="nb-mini" data-act="add">+ Component</button>' : ''}</div>`;
    } else if (d.type === 'serial') {
      fields = field('start', d.start, 'Start', { unit: d.unit, conc: true, dis }).replace('data-k="startUnit"', 'data-k="unit"')
        + field('factor', d.factor, 'Fold per step', { dis }) + field('steps', d.steps, 'Steps', { dis })
        + field('volume', d.volume, 'Diluent per tube', { unit: d.volumeUnit, units: VOLUME_UNITS, dis });
    } else if (d.type === 'ligation') {
      fields = field('vectorNg', d.vectorNg, 'Vector (ng)', { dis }) + field('vectorBp', d.vectorBp, 'Vector length (bp)', { dis })
        + field('insertBp', d.insertBp, 'Insert length (bp)', { dis }) + field('ratio', d.ratio, 'Insert : vector', { dis });
    } else if (d.type === 'cells') {
      fields = field('counted', d.counted, 'Cells counted', { dis }) + field('squares', d.squares, 'Squares', { dis }) + field('dilution', d.dilution, 'Dilution (trypan = 2)', { dis })
        + field('target', d.target, 'Cells per well', { dis }) + field('wells', d.wells, 'Wells', { dis })
        + field('perWell', d.perWell, 'Volume per well', { unit: d.perWellUnit, units: VOLUME_UNITS, dis }) + field('overage', d.overage, 'Extra %', { dis });
    } else if (d.type === 'gel') {
      fields = field('percent', d.percent, 'Agarose %', { dis }) + field('volume', d.volume, 'Volume (mL)', { dis });
    } else if (d.type === 'nucleic') {
      fields = `<label class="nb-calc-field"><span>Kind</span><span class="nb-calc-input"><select data-k="kind"${dis}>${['dsDNA', 'ssDNA', 'RNA', 'oligo'].map((k) => `<option${d.kind === k ? ' selected' : ''}>${k}</option>`).join('')}</select></span></label>`
        + field('a260', d.a260, 'A₂₆₀', { dis }) + field('dilution', d.dilution, 'Dilution', { dis })
        + field('ng', d.ng, 'Mass (ng)', { dis }) + field('bp', d.bp, 'Length (bp or nt)', { dis });
    }
    root.innerHTML = `<div class="nb-calc-head">${typeSel}</div><div class="nb-calc-fields">${fields}</div><div class="nb-calc-results">${results()}</div>`;
  }

  function refresh() {
    const out = root.querySelector('.nb-calc-results');
    if (out) out.innerHTML = results();
    if (data.type === 'dilution' || data.type === 'molarity') {
      const key = (data.type === 'dilution' ? solveDilution(data) : solveMolarity(data)).key;
      root.querySelectorAll('.nb-calc-field').forEach((f) => {
        f.classList.toggle('is-solved', f.querySelector('input')?.dataset.k === key);
      });
    }
  }

  root.addEventListener('input', (event) => {
    const t = event.target;
    if (t.dataset.k && t.tagName === 'INPUT') data[t.dataset.k] = t.value;
    else if (t.dataset.m) data.components[Number(t.closest('[data-i]').dataset.i)][t.dataset.m] = t.value;
    else return;
    commit(); refresh();
  });
  root.addEventListener('change', (event) => {
    const t = event.target;
    if (t.tagName !== 'SELECT' || !t.dataset.k) return;
    if (t.dataset.k === 'type') {
      data = defaultCalc(t.value);
      commit(); render();
      return;
    }
    data[t.dataset.k] = t.value;
    commit();
    if (t.dataset.k === 'c1Unit' && family(data.c2Unit) !== family(t.value)) { data.c2Unit = t.value; render(); } else refresh();
  });
  root.addEventListener('click', (event) => {
    const b = event.target.closest('button');
    if (!b) return;
    if (b.dataset.act === 'add') { data.components.push({ name: '', perRxn: '' }); commit(); render(); }
    if (b.dataset.remove !== undefined) { data.components.splice(Number(b.dataset.remove), 1); commit(); render(); }
  });

  render();
  return {
    update(next) { data = { ...defaultCalc(next && next.type), ...(next || {}) }; render(); },
    destroy() { commit.flush(); },
  };
}

