/* Sheet autosave: inline editing for every database sheet, the way the
 * mouse sheet works.
 *
 * Opt in on the card:  <section class="data-table-card sheet" data-autosave-sheet>
 *
 * Each row's cells point at a hidden per-row form (form="row-12"); the
 * form's action takes the POST. Cells marked data-autosave="1" save 450 ms
 * after typing stops, or at once on change. The request carries
 * X-Autosave: 1 and expects JSON:
 *
 *   { "ok": true,
 *     "row": { "active": false,               // availability dot
 *              "values": { "position": "D7" } } }  // server's view of cells
 *   { "ok": false, "error": "…" }              // shown in the toolbar
 *
 * values also refresh hidden "<name>_was" copies in the form (the stale-
 * form guard, app/formutil.py).
 *
 * Live availability dot, before the server answers: give the field that
 * decides it one of
 *   data-alive-values="in stock,low"        alive only for these values
 *   data-dead-values="discarded,used up"    alive except for these
 *   data-dead-if-set                        alive only while empty (a date of death)
 * and the row's .life-dot follows it.
 *
 * Events for page-specific rules: "sheet:change" (before saving; detail
 * {input, form, previous}) and "sheet:saved" (detail {form, body}).
 */
(function () {
  'use strict';

  const timers = new Map();

  function statusEl(card) {
    return (card && card.querySelector('[data-save-status]')) || document.querySelector('[data-save-status]');
  }
  function say(card, state, text) {
    const el = statusEl(card);
    if (!el) return;
    clearTimeout(el._clear);
    el.dataset.state = state;
    el.textContent = text;
    if (state === 'saved') el._clear = setTimeout(() => { el.textContent = ''; el.dataset.state = ''; }, 2400);
  }

  const cellsOf = (form) => document.querySelectorAll(`[form="${form.id}"]`);

  /* The availability dot of a row, from the fields that decide it. */
  function refreshDot(row, activeFromServer) {
    const dot = row && row.querySelector('.life-dot');
    if (!dot) return;
    let alive = true;
    if (typeof activeFromServer === 'boolean') {
      alive = activeFromServer;
    } else {
      row.querySelectorAll('[data-alive-values], [data-dead-values], [data-dead-if-set]').forEach((el) => {
        const value = String(el.value || '').trim().toLowerCase();
        if (el.hasAttribute('data-dead-if-set') && value) alive = false;
        if (el.dataset.aliveValues !== undefined) {
          const ok = el.dataset.aliveValues.toLowerCase().split(',').map((v) => v.trim());
          if (!ok.includes(value)) alive = false;
        }
        if (el.dataset.deadValues !== undefined) {
          const dead = el.dataset.deadValues.toLowerCase().split(',').map((v) => v.trim());
          if (dead.includes(value)) alive = false;
        }
      });
    }
    dot.classList.toggle('is-alive', alive);
    dot.title = alive ? (dot.dataset.aliveTitle || 'Available') : (dot.dataset.deadTitle || 'Not available');
    row.dataset.active = alive ? 'true' : 'false';
    row.classList.toggle('is-inactive', !alive);
  }

  async function save(form, card) {
    say(card, 'saving', 'Saving…');
    const label = form.dataset.recordLabel || 'this change';
    try {
      const response = await fetch(form.action, {
        method: 'POST', body: new FormData(form), headers: { 'X-Autosave': '1' },
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body.ok === false) throw new Error(body.error || `The server answered ${response.status}.`);
      const row = body.row || {};
      // What was just saved is what the row now shows (the server's own
      // values below correct it where it changed them).
      cellsOf(form).forEach((el) => {
        const was = el.name && el.type !== 'checkbox' && form.querySelector(`[name="${el.name}_was"]`);
        if (was) was.value = el.value;
      });
      Object.entries(row.values || {}).forEach(([name, value]) => {
        const was = form.querySelector(`[name="${name}_was"]`);
        if (was) was.value = value == null ? '' : value;
        document.querySelectorAll(`[form="${form.id}"][name="${name}"]`).forEach((el) => {
          if (el !== document.activeElement && el.type !== 'checkbox') el.value = value == null ? '' : value;
          if (el.type === 'date') el.dataset.empty = el.value ? '0' : '1';
        });
      });
      const anyCell = cellsOf(form)[0];
      const tr = anyCell && anyCell.closest('tr');
      if (tr && 'active' in row) refreshDot(tr, row.active);
      cellsOf(form).forEach((el) => el.closest('td') && el.closest('td').classList.remove('has-error'));
      form.dispatchEvent(new CustomEvent('sheet:saved', { bubbles: true, detail: { form, body } }));
      say(card, 'saved', 'All changes saved');
    } catch (error) {
      cellsOf(form).forEach((el) => {
        if (el.dataset.dirty === '1' && el.closest('td')) el.closest('td').classList.add('has-error');
      });
      say(card, 'error', `Couldn’t save ${label}: ${error.message}`);
    }
  }

  function queue(input, delay) {
    const form = document.getElementById(input.getAttribute('form'));
    if (!form) return;
    const card = input.closest('[data-autosave-sheet]');
    clearTimeout(timers.get(form.id));
    timers.set(form.id, setTimeout(() => save(form, card), delay));
  }

  function wire(card) {
    card.querySelectorAll('[data-autosave="1"][form]').forEach((input) => {
      input.dataset.previous = input.value;
      input.addEventListener('input', () => {
        input.dataset.dirty = '1';
        if (input.tagName !== 'SELECT' && input.type !== 'date') queue(input, 450);
      });
      input.addEventListener('change', () => {
        input.dataset.dirty = '1';
        const previous = input.dataset.previous || '';
        if (input.classList.contains('status-pill')) input.dataset.status = input.value.toLowerCase();
        if (input.classList.contains('sex-pill')) input.dataset.sex = input.value;
        if (input.dataset.scopePill !== undefined || input.classList.contains('scope-pill')) {
          input.dataset.scope = input.value === '1' ? 'lab' : 'mine';
        }
        const detail = { input, form: document.getElementById(input.getAttribute('form')), previous };
        const go = input.dispatchEvent(new CustomEvent('sheet:change', { bubbles: true, cancelable: true, detail }));
        input.dataset.previous = input.value;
        if (input.type === 'date') input.dataset.empty = input.value ? '0' : '1';
        refreshDot(input.closest('tr'));
        if (go) queue(input, 0);
      });
    });
  }

  window.BioSheet = { refreshDot, save };

  function init() { document.querySelectorAll('[data-autosave-sheet]').forEach(wire); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
