/* An experiment's manipulations (templates/_experiment_steps.html,
   app/experiment_steps.py): the plan, the day-by-day schedule, and the
   dialogs that add a manipulation and record a day as done. */
(function () {
  'use strict';
  const dataEl = document.getElementById('xs-data');
  if (!dataEl) return;
  const DATA = JSON.parse(dataEl.textContent || '{}');
  const base = `/colony/experiments/${DATA.experiment}`;
  const planEl = document.querySelector('[data-xs-plan]');
  const schedEl = document.querySelector('[data-xs-schedule]');
  const stepDialog = document.getElementById('xs-step-dialog');
  const recordDialog = document.getElementById('xs-record-dialog');
  let state = { steps: DATA.steps || [], schedule: DATA.schedule || [] };
  let current = null;       // the day open in the record dialog

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const icon = (name) => `<svg class="icon xs-icon" aria-hidden="true"><use href="/static/icons.svg#${esc(name)}"></use></svg>`;
  const STATE_LABEL = { done: 'Done', today: 'Today', overdue: 'Overdue', upcoming: 'To come', planned: 'Planned' };

  function niceDate(iso) {
    if (!iso) return '';
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  }

  async function send(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) {
      const error = new Error(data.error || `The server answered ${r.status}.`);
      error.data = data;
      throw error;
    }
    return data;
  }

  function showError(dialog, text) {
    const el = dialog.querySelector('[data-xs-error]');
    el.textContent = text || '';
    el.hidden = !text;
  }

  // ---------------------------------------------------------------- drawing

  function drawPlan() {
    if (!state.steps.length) {
      planEl.innerHTML = `<p class="xs-empty">No manipulations yet.${DATA.editable ? ' <b>Add manipulation</b>: an injection, a challenge, a treatment, a body-weight day…' : ''}</p>`;
      return;
    }
    const rows = state.steps.map((s) => `
      <tr>
        <td class="xs-days">Day ${esc(s.days_label)}</td>
        <td><span class="xs-kind" data-kind="${esc(s.kind)}">${icon(s.icon)}${esc(s.kind_label)}</span></td>
        <td class="xs-what">${esc(s.agent)}</td>
        <td>${esc(s.dose)}${s.concentration ? `<span class="xs-muted"> · ${esc(s.concentration)}</span>` : ''}</td>
        <td>${esc(s.route)}</td>
        <td>${s.group ? esc(s.group) : '<span class="xs-muted">every mouse</span>'}</td>
        <td class="xs-notes">${esc(s.notes)}</td>
        <td class="xs-actions">${DATA.editable ? `
          <button type="button" class="xs-link" data-xs-edit="${s.id}">Edit</button>
          <button type="button" class="xs-link xs-danger" data-xs-delete="${s.id}" aria-label="Delete ${esc(s.agent || s.kind_label)}">×</button>` : ''}</td>
      </tr>`).join('');
    planEl.innerHTML = `<div class="table-wrap"><table class="dense-table fit-table xs-plan-table">
      <thead><tr><th>Days</th><th>Kind</th><th>What</th><th>Dose</th><th>Route</th><th>Group</th><th>Notes</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }

  function drawSchedule() {
    if (!state.schedule.length) { schedEl.innerHTML = ''; return; }
    const byDay = new Map();
    state.schedule.forEach((row) => {
      if (!byDay.has(row.day)) byDay.set(row.day, []);
      byDay.get(row.day).push(row);
    });
    const days = [...byDay.entries()].map(([day, rows]) => {
      const date = rows[0].date;
      const items = rows.map((row) => {
        const rec = row.record;
        const status = rec
          ? `Done ${esc(niceDate(rec.done_on))} by ${esc(rec.done_by)} · ${rec.count} of ${row.group_size}`
          : STATE_LABEL[row.state];
        return `<li class="xs-item" data-state="${esc(row.state)}">
          <span class="xs-item-icon">${icon(row.icon)}</span>
          <span class="xs-item-body"><b>${esc(row.title)}</b>${row.group ? ` <span class="xs-muted">· ${esc(row.group)}</span>` : ''}
            <span class="xs-status">${status}</span>${rec && rec.note ? `<span class="xs-note">${esc(rec.note)}</span>` : ''}</span>
          <button type="button" class="${rec ? 'xs-link' : 'btn xs-record-btn'}" data-xs-open="${row.step_id}" data-day="${row.day}">
            ${rec ? 'Details' : (DATA.editable ? 'Record' : 'Details')}</button>
        </li>`;
      }).join('');
      return `<li class="xs-day" id="day-${day}">
        <div class="xs-day-head"><span class="xs-day-n">Day ${day}</span><span class="xs-day-date">${esc(niceDate(date))}</span></div>
        <ul class="xs-items">${items}</ul></li>`;
    }).join('');
    const done = state.schedule.filter((r) => r.record).length;
    schedEl.innerHTML = `<h3 class="xs-h3">Day by day <span class="xs-muted">${done} of ${state.schedule.length} done</span></h3><ol class="xs-days-list">${days}</ol>`;
    const target = window.location.hash && document.querySelector(window.location.hash);
    if (target && target.classList.contains('xs-day')) target.classList.add('is-target');
  }

  function draw() { drawPlan(); drawSchedule(); }

  function apply(data) {
    if (data.steps) state.steps = data.steps;
    if (data.schedule) state.schedule = data.schedule;
    draw();
  }

  // ---------------------------------------------------------------- the plan

  function openStep(step) {
    const form = stepDialog.querySelector('form');
    form.reset();
    showError(stepDialog, '');
    document.getElementById('xs-step-title').textContent = step ? 'Change the manipulation' : 'Add a manipulation';
    const values = step || { kind: 'injection' };
    ['id', 'kind', 'agent', 'days', 'dose', 'route', 'concentration', 'group', 'notes'].forEach((name) => {
      const field = form.elements[name];
      if (field) field.value = values[name] == null ? '' : values[name];
    });
    stepDialog.showModal();
    form.elements.agent.focus();
  }

  stepDialog.querySelector('form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      apply(await send(`${base}/steps/save`, body));
      stepDialog.close();
    } catch (error) {
      showError(stepDialog, error.message);
    }
  });

  document.addEventListener('click', async (event) => {
    const t = event.target.closest('button');
    if (!t) return;
    if (t.matches('[data-xs-add]')) return openStep(null);
    if (t.matches('[data-xs-close]')) return t.closest('dialog').close();
    if (t.dataset.xsEdit) return openStep(state.steps.find((s) => s.id === Number(t.dataset.xsEdit)));
    if (t.dataset.xsDelete) {
      const step = state.steps.find((s) => s.id === Number(t.dataset.xsDelete));
      const ok = await confirmAsk(`Delete ${step.agent || step.kind_label} (day ${step.days_label}) from the plan?`, true);
      if (!ok) return undefined;
      try {
        apply(await send(`${base}/steps/${step.id}/delete`, {}));
      } catch (error) {
        if (error.data && error.data.needs_confirm) {
          if (await confirmAsk(`${error.message} Delete it and those records too?`)) {
            apply(await send(`${base}/steps/${step.id}/delete`, { confirm: '1' }));
          }
        } else alertSay(error.message);
      }
      return undefined;
    }
    if (t.dataset.xsOpen) return openRecord(Number(t.dataset.xsOpen), Number(t.dataset.day));
    return undefined;
  });

  function confirmAsk(text, danger) {
    return window.BioDialog && BioDialog.confirm ? BioDialog.confirm(text, { danger: Boolean(danger) }) : Promise.resolve(window.confirm(text));
  }
  function alertSay(text) {
    if (window.BioDialog && BioDialog.alert) BioDialog.alert(text); else window.alert(text);
  }

  // ---------------------------------------------------------------- recording a day

  async function openRecord(stepId, day, on) {
    // A new date re-reads the weights; the mice ticked and weights typed stay.
    const kept = on ? {
      unticked: new Set([...recordDialog.querySelectorAll('[data-xs-mouse]:not(:checked)')].map((b) => b.dataset.xsMouse)),
      grams: Object.fromEntries([...recordDialog.querySelectorAll('.xs-grams')].map((i) => [i.name, i.value])),
    } : null;
    const url = `${base}/steps/${stepId}/day/${day}` + (on ? `?on=${encodeURIComponent(on)}` : '');
    let data;
    try {
      data = await (await fetch(url)).json();
    } catch (_e) {
      return alertSay('The day could not be loaded.');
    }
    current = { stepId, day, data };
    const form = recordDialog.querySelector('form');
    if (!on) form.reset();
    showError(recordDialog, '');
    const step = data.step;
    const weigh = step.kind === 'weigh';
    document.getElementById('xs-record-title').textContent = `${[step.agent || step.kind_label, step.dose, step.route].filter(Boolean).join(' ')} · Day ${day}`;
    recordDialog.querySelector('[data-xs-record-sub]').textContent = [
      data.planned ? `Planned for ${niceDate(data.planned)}` : 'The experiment has no start date, so the day has no date',
      step.group ? `group ${step.group}` : 'every mouse',
      data.record ? `recorded by ${data.record.done_by}` : '',
    ].filter(Boolean).join(' · ');
    form.elements.done_on.value = data.on;
    form.elements.done_on.max = new Date().toISOString().slice(0, 10);
    if (!on) form.elements.note.value = data.record ? data.record.note : '';
    const doseNote = recordDialog.querySelector('[data-xs-dose-note]');
    doseNote.textContent = weigh ? 'Type each weight in grams; they go into the body-weight table.'
      : step.per_weight ? `${step.dose} from each mouse's latest weight on or before that day${step.concentration ? `, as ${step.concentration}` : ''}.` : '';
    recordDialog.querySelector('[data-xs-mice-head]').innerHTML = `<tr><th><input type="checkbox" data-xs-all checked aria-label="Every mouse"></th>
      <th>Mouse</th><th>Group</th><th>${weigh ? 'Weight (g)' : 'Weight'}</th>${weigh ? '<th>Before</th>' : '<th>Amount</th><th>Volume</th>'}</tr>`;
    const rows = data.mice.map((m) => {
      const weight = m.grams != null ? `${m.grams.toFixed(1)} g <span class="xs-muted">${esc(niceDate(m.weighed_on))}</span>` : '<span class="xs-muted">no weight</span>';
      const cells = weigh
        ? `<td><input class="xs-grams" name="g-${m.mouse}" inputmode="decimal" value="${m.today_grams != null ? m.today_grams : ''}" ${m.can_weigh && data.editable ? '' : 'disabled'} aria-label="Weight of mouse ${m.mouse_id} in grams"></td><td>${weight}</td>`
        : `<td>${weight}</td><td>${m.needs ? '<span class="xs-warn">needs a weight</span>' : esc(m.amount || '')}</td><td>${esc(m.volume || '')}</td>`;
      return `<tr><td><input type="checkbox" data-xs-mouse="${m.mouse}" ${m.given ? 'checked' : ''} ${data.editable ? '' : 'disabled'} aria-label="Mouse ${m.mouse_id}"></td>
        <td>#${esc(m.mouse_id)} <span class="xs-muted">${esc(m.sex)}</span></td><td>${esc(m.group)}</td>${cells}</tr>`;
    }).join('');
    recordDialog.querySelector('[data-xs-mice]').innerHTML = rows || '<tr><td colspan="6" class="xs-muted">No mice in this group yet.</td></tr>';
    if (kept) {
      recordDialog.querySelectorAll('[data-xs-mouse]').forEach((b) => { if (kept.unticked.has(b.dataset.xsMouse)) b.checked = false; });
      recordDialog.querySelectorAll('.xs-grams').forEach((i) => { if (kept.grams[i.name]) i.value = kept.grams[i.name]; });
    }
    recordDialog.querySelector('[data-xs-undo]').hidden = !(data.record && data.editable);
    recordDialog.querySelector('[data-xs-save]').hidden = !data.editable;
    recordDialog.querySelector('[data-xs-save]').textContent = data.record ? 'Save' : 'Record as done';
    form.elements.done_on.disabled = !data.editable;
    form.elements.note.disabled = !data.editable;
    if (!recordDialog.open) recordDialog.showModal();
    return undefined;
  }

  recordDialog.addEventListener('change', (event) => {
    const t = event.target;
    if (t.matches('[data-xs-all]')) {
      recordDialog.querySelectorAll('[data-xs-mouse]:not(:disabled)').forEach((box) => { box.checked = t.checked; });
    }
    // Another date: the weights, and so the amounts, are those of that day.
    if (t.name === 'done_on' && t.value && current) openRecord(current.stepId, current.day, t.value);
  });

  recordDialog.querySelector('form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!current) return;
    const form = event.target;
    const mice = [...recordDialog.querySelectorAll('[data-xs-mouse]:checked')].map((b) => Number(b.dataset.xsMouse));
    const grams = {};
    recordDialog.querySelectorAll('.xs-grams').forEach((input) => { grams[input.name.slice(2)] = input.value; });
    try {
      const data = await send(`${base}/steps/${current.stepId}/day/${current.day}/record`, {
        done_on: form.elements.done_on.value, mice, grams, note: form.elements.note.value,
      });
      apply(data);
      recordDialog.close();
      if (data.problems && data.problems.length) alertSay(`Recorded, but some weights were not saved:\n${data.problems.join('\n')}`);
      else if (current.data.step.kind === 'weigh') window.location.reload();   // the body-weight table below
    } catch (error) {
      showError(recordDialog, error.message);
    }
  });

  recordDialog.querySelector('[data-xs-undo]').addEventListener('click', async () => {
    if (!current) return;
    if (!(await confirmAsk('Mark this day as not done? Weights recorded with it stay in the body-weight table.'))) return;
    try {
      apply(await send(`${base}/steps/${current.stepId}/day/${current.day}/undo`, {}));
      recordDialog.close();
    } catch (error) {
      showError(recordDialog, error.message);
    }
  });

  draw();
})();
