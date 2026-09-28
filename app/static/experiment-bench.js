/* Bench mode (templates/experiment_bench.html): pick what you are doing
   now — the readout (weigh, count) or a manipulation due — then go through
   the animals one at a time, with big numbers and big buttons. A readout
   is saved animal by animal; a manipulation is recorded at the end, with
   the animals you ticked as given. */
(function () {
  'use strict';
  const el = document.getElementById('xb-data');
  if (!el) return;
  const D = JSON.parse(el.textContent || '{}');
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const nice = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '');
  const fraction = D.readout.kind === 'fraction';
  let task = null;      // {kind: 'reading'} | {kind: 'step', stepId, day, title, animals}
  let at = 0;
  const given = new Map();

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) throw new Error(data.error || `The app answered ${r.status}.`);
    return data;
  }

  function pick() {
    const due = D.schedule.filter((r) => !r.record && !r.reading && (r.state === 'today' || r.state === 'overdue'));
    const later = D.schedule.filter((r) => !r.record && !r.reading && r.state !== 'today' && r.state !== 'overdue');
    const button = (r) => `<button type="button" class="xb-choice" data-step="${r.step_id}:${r.day}"><b>${esc(r.title)}</b>
      <span>Day ${r.day}${r.date ? ` · ${esc(nice(r.date))}` : ''}${r.group ? ` · ${esc(r.group)}` : ''} · ${r.state === 'overdue' ? 'overdue' : r.state === 'today' ? 'due today' : 'to come'}</span></button>`;
    $('[data-xb-pick]').innerHTML = `
      <h2>What are you doing now?</h2>
      ${D.editable ? `<button type="button" class="xb-choice xb-main" data-reading><b>${esc(D.readout.verb || 'Record')}: ${esc(D.readout.label)}</b><span>Today, ${D.subjects.length} ${esc(D.nouns)}, one at a time</span></button>
      ${due.map(button).join('')}
      ${later.length ? `<details class="xb-later"><summary>Planned for other days (${later.length})</summary>${later.map(button).join('')}</details>` : ''}`
        : '<p class="xp-empty">This experiment is read only for you.</p>'}`;
  }

  async function start(which) {
    at = 0;
    given.clear();
    if (which === 'reading') {
      task = { kind: 'reading', animals: D.subjects };
    } else {
      const [stepId, day] = which.split(':');
      const r = await fetch(`/colony/experiments/${D.id}/steps/${stepId}/day/${day}?on=${today()}`);
      const data = await r.json();
      task = { kind: 'step', stepId, day, title: (D.schedule.find((x) => `${x.step_id}:${x.day}` === which) || {}).title, animals: data.animals || [] };
      task.animals.forEach((a) => given.set(a.subject, true));
    }
    $('[data-xb-pick]').hidden = true;
    $('[data-xb-done]').hidden = true;
    $('[data-xb-run]').hidden = false;
    show();
  }

  function previous(key) {
    const row = D.table.rows.find((r) => r.key === key);
    if (!row) return null;
    for (let i = D.table.dates.length - 1; i >= 0; i -= 1) {
      if (row.values[i] != null) return { value: row.values[i], date: D.table.dates[i], today: D.table.dates[i] === today() };
    }
    return null;
  }

  function show() {
    const list = task.animals;
    if (at >= list.length) return finish();
    const a = list[at];
    const key = a.key || a.subject;
    $('[data-xb-count]').textContent = `${at + 1} of ${list.length}`;
    $('[data-xb-bar]').style.width = `${(at / list.length) * 100}%`;
    const head = `<div class="xb-who"><span class="xb-label">${esc(a.label)}</span><span>${esc([a.group, a.housing, a.sex].filter(Boolean).join(' · '))}</span></div>`;
    if (task.kind === 'reading') {
      const prev = previous(key);
      $('[data-xb-card]').innerHTML = `${head}
        <label class="xb-input"><span>${fraction && D.readout.unit ? esc(D.readout.unit.charAt(0).toUpperCase() + D.readout.unit.slice(1)) : esc(D.readout.label)}${D.readout.unit && !fraction ? ` (${esc(D.readout.unit)})` : ''}</span>
          <input type="text" inputmode="decimal" autocomplete="off" data-xb-value value="${prev && prev.today ? prev.value : ''}">
          ${fraction && a.start != null ? `<em>of ${a.start}</em>` : ''}</label>
        <p class="xb-prev">${prev && !prev.today ? `Last: ${prev.value}${D.readout.unit && !fraction ? ` ${esc(D.readout.unit)}` : ''} on ${esc(nice(prev.date))}` : prev ? 'Already recorded today: change it or go on.' : 'No readout yet.'}</p>
        <p class="xp-error" data-xb-error hidden></p>
        <div class="xb-buttons"><button type="button" class="btn" data-xb-back ${at ? '' : 'disabled'}>Back</button>
          <button type="button" class="btn" data-xb-skip>Skip</button>
          <button type="button" class="btn btn-primary" data-xb-save>Save and next</button></div>`;
      const input = $('[data-xb-value]');
      input.focus();
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); saveReading(); } });
    } else {
      const dose = [a.amount, a.volume].filter(Boolean).join(' · ');
      $('[data-xb-card]').innerHTML = `${head}
        <p class="xb-what">${esc(task.title || '')}</p>
        <p class="xb-dose">${a.needs ? '<span class="xp-warn">needs a weight first</span>' : esc(dose || '—')}</p>
        <p class="xb-prev">${a.grams != null ? `From ${a.grams} g on ${esc(nice(a.weighed_on))}` : ''}</p>
        <div class="xb-buttons"><button type="button" class="btn" data-xb-back ${at ? '' : 'disabled'}>Back</button>
          <button type="button" class="btn" data-xb-miss>Not given</button>
          <button type="button" class="btn btn-primary" data-xb-give>Given ✓</button></div>`;
    }
    $('[data-xb-jump]').innerHTML = list.map((x, i) => {
      const k = x.key || x.subject;
      const state = task.kind === 'step' ? (given.get(k) ? 'given' : 'missed') : (previous(k) && previous(k).today ? 'given' : '');
      return `<button type="button" class="xb-chip${i === at ? ' is-now' : ''}" data-xb-go="${i}" data-state="${state}">${esc(x.label)}</button>`;
    }).join('');
  }

  async function saveReading() {
    const a = task.animals[at];
    const input = $('[data-xb-value]');
    const value = input.value.trim();
    if (value) {
      try {
        const data = await post(`/experiments/${D.id}/readings`, { on: today(), values: { [a.key]: value } });
        D.table = data.table;
      } catch (error) {
        const box = $('[data-xb-error]');
        box.textContent = error.message;
        box.hidden = false;
        return;
      }
    }
    at += 1;
    show();
  }

  async function finish() {
    $('[data-xb-bar]').style.width = '100%';
    const done = $('[data-xb-done]');
    if (task.kind === 'reading') {
      $('[data-xb-run]').hidden = true;
      done.hidden = false;
      done.innerHTML = `<h2>Done</h2><p>${esc(D.readout.label)} saved for today.</p><div class="xb-buttons"><a class="btn" href="/experiments/${D.id}">The experiment</a><button type="button" class="btn btn-primary" data-xb-again>Something else</button></div>`;
      return;
    }
    const yes = task.animals.filter((a) => given.get(a.subject));
    $('[data-xb-run]').hidden = true;
    done.hidden = false;
    done.innerHTML = `<h2>${esc(task.title || 'Done')}</h2><p>${yes.length} of ${task.animals.length} ${esc(D.nouns)} given.</p>
      <label class="xb-note">Note <textarea rows="3" data-xb-note placeholder="Anything that differed"></textarea></label>
      <p class="xp-error" data-xb-error hidden></p>
      <div class="xb-buttons"><button type="button" class="btn" data-xb-review>Back</button><button type="button" class="btn btn-primary" data-xb-record>Record as done</button></div>`;
  }

  document.addEventListener('click', async (event) => {
    const t = event.target.closest('button');
    if (!t) return;
    if (t.matches('[data-reading]')) start('reading');
    else if (t.dataset.step) start(t.dataset.step);
    else if (t.matches('[data-xb-save]')) saveReading();
    else if (t.matches('[data-xb-skip]')) { at += 1; show(); }
    else if (t.matches('[data-xb-back]')) { at = Math.max(0, at - 1); show(); }
    else if (t.matches('[data-xb-give], [data-xb-miss]')) { given.set(task.animals[at].subject, t.matches('[data-xb-give]')); at += 1; show(); }
    else if (t.dataset.xbGo) { at = Number(t.dataset.xbGo); show(); }
    else if (t.matches('[data-xb-review]')) { at = task.animals.length - 1; $('[data-xb-done]').hidden = true; $('[data-xb-run]').hidden = false; show(); }
    else if (t.matches('[data-xb-again]')) { $('[data-xb-done]').hidden = true; $('[data-xb-pick]').hidden = false; pick(); }
    else if (t.matches('[data-xb-record]')) {
      const subjects = task.animals.filter((a) => given.get(a.subject)).map((a) => a.subject);
      try {
        const data = await post(`/colony/experiments/${D.id}/steps/${task.stepId}/day/${task.day}/record`,
          { done_on: today(), subjects, note: ($('[data-xb-note]') || {}).value || '' });
        D.schedule = data.schedule;
        $('[data-xb-done]').innerHTML = `<h2>Recorded</h2><p>${esc(task.title || '')}: ${subjects.length} ${esc(D.nouns)}.</p>${(data.problems || []).map((p) => `<p class="xp-warn">${esc(p)}</p>`).join('')}
          <div class="xb-buttons"><a class="btn" href="/experiments/${D.id}">The experiment</a><button type="button" class="btn btn-primary" data-xb-again>Something else</button></div>`;
      } catch (error) {
        const box = $('[data-xb-error]');
        box.textContent = error.message;
        box.hidden = false;
      }
    }
  });

  pick();
})();
