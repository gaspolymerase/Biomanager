// Units for recipes and calculators. Concentrations fall in families that
// convert within themselves: molar (to mol/L), mass per volume (to g/L,
// with % w/v = g per 100 mL), % v/v, and fold (×) strengths.

import { fmt } from '../util.js';

export const CONC_UNITS = {
  M: ['molar', 1], mM: ['molar', 1e-3], 'µM': ['molar', 1e-6], nM: ['molar', 1e-9], pM: ['molar', 1e-12],
  'g/L': ['mass', 1], 'mg/mL': ['mass', 1], 'mg/L': ['mass', 1e-3], 'µg/mL': ['mass', 1e-3],
  'ng/µL': ['mass', 1e-3], 'ng/mL': ['mass', 1e-6], '% w/v': ['mass', 10],
  '% v/v': ['vol', 0.01],
  X: ['fold', 1],
  'U/mL': ['units', 1], 'U/µL': ['units', 1e3],
};

export const VOLUME_UNITS = { L: 1, mL: 1e-3, 'µL': 1e-6 };
export const MASS_UNITS = { kg: 1e3, g: 1, mg: 1e-3, 'µg': 1e-6, ng: 1e-9 };

export function family(unit) {
  return (CONC_UNITS[unit] || [''])[0];
}

export function toBase(value, unit) {
  const u = CONC_UNITS[unit];
  return u ? value * u[1] : NaN;
}

export function fromBase(value, unit) {
  const u = CONC_UNITS[unit];
  return u ? value / u[1] : NaN;
}

export function litres(value, unit) {
  return value * (VOLUME_UNITS[unit] ?? NaN);
}

export function fromLitres(l, unit) {
  return l / (VOLUME_UNITS[unit] ?? NaN);
}

// A volume in litres as the handiest unit: "12.5 mL", "250 µL".
export function showVolume(l) {
  if (!Number.isFinite(l)) return '—';
  const a = Math.abs(l);
  if (a >= 1) return `${fmt(l, 4)} L`;
  if (a >= 1e-3) return `${fmt(l * 1e3, 4)} mL`;
  return `${fmt(l * 1e6, 4)} µL`;
}

export function showMass(g) {
  if (!Number.isFinite(g)) return '—';
  const a = Math.abs(g);
  if (a >= 1000) return `${fmt(g / 1000, 4)} kg`;
  if (a >= 1) return `${fmt(g, 4)} g`;
  if (a >= 1e-3) return `${fmt(g * 1e3, 4)} mg`;
  if (a >= 1e-6) return `${fmt(g * 1e6, 4)} µg`;
  return `${fmt(g * 1e9, 4)} ng`;
}

export function unitOptions(units, selected) {
  return Object.keys(units).map((u) => `<option${u === selected ? ' selected' : ''}>${u}</option>`).join('');
}

export const CONC_GROUPS = [
  ['Molar', ['M', 'mM', 'µM', 'nM', 'pM']],
  ['Mass / volume', ['g/L', 'mg/mL', 'mg/L', 'µg/mL', 'ng/µL', 'ng/mL', '% w/v']],
  ['Other', ['% v/v', 'X', 'U/mL', 'U/µL']],
];

export function concOptions(selected, only) {
  return CONC_GROUPS.map(([label, units]) => {
    const list = units.filter((u) => !only || only.includes(family(u)));
    if (!list.length) return '';
    return `<optgroup label="${label}">${list.map((u) => `<option${u === selected ? ' selected' : ''}>${u}</option>`).join('')}</optgroup>`;
  }).join('');
}
