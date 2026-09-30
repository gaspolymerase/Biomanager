// Step timers. Any duration written in a page — "incubate 30 min",
// "spin 10 min", "heat shock 45 s", "block 1 h" — gets a small ⏱ button;
// pressing it starts a countdown named after the step. Timers sit in a tray
// in the corner, keep running across reloads and pages (they live in this
// browser's storage), and when one ends it rings, vibrates the phone and
// shows a notification.

import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import { ask, el, escapeHtml } from './util.js';
import { findDurations, timerLabel } from './durations.js';

const KEY = 'bm-nb-timers';
export { DURATION_RE, durationSeconds, findDurations } from './durations.js';

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (_e) { return []; }
}

function save(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (_e) { /* private window */ }
}

function left(t) {
  if (t.pausedLeft !== undefined && t.pausedLeft !== null) return t.pausedLeft;
  return Math.max(0, Math.round((t.endsAt - Date.now()) / 1000));
}

function show(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`;
}

let audio = null;
function ring() {
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    const now = audio.currentTime;
    for (let i = 0; i < 6; i++) {
      const o = audio.createOscillator();
      const g = audio.createGain();
      o.frequency.value = i % 2 ? 660 : 880;
      g.gain.setValueAtTime(0.0001, now + i * 0.35);
      g.gain.exponentialRampToValueAtTime(0.25, now + i * 0.35 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.35 + 0.3);
      o.connect(g).connect(audio.destination);
      o.start(now + i * 0.35);
      o.stop(now + i * 0.35 + 0.32);
    }
  } catch (_e) { /* no audio */ }
  try { navigator.vibrate && navigator.vibrate([300, 150, 300, 150, 600]); } catch (_e) { /* no vibration */ }
}

class TimerTray {
  constructor() {
    this.el = el('div', { class: 'nb-timers', 'aria-live': 'polite' });
    document.body.appendChild(this.el);
    this.titleBase = document.title;
    this.tick = this.tick.bind(this);
    window.addEventListener('storage', (event) => { if (event.key === KEY) this.render(); });
    this.el.addEventListener('click', (event) => this.onClick(event));
    this.render();
    setInterval(this.tick, 500);
  }

  start(label, seconds) {
    const list = load();
    list.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, label: (label || 'Timer').slice(0, 80), total: seconds, endsAt: Date.now() + seconds * 1000, page: location.pathname + location.search });
    save(list);
    if ('Notification' in window && Notification.permission === 'default') {
      try { Notification.requestPermission(); } catch (_e) { /* ignored */ }
    }
    try { (audio = audio || new (window.AudioContext || window.webkitAudioContext)()).resume(); } catch (_e) { /* ignored */ }
    this.render();
  }

  onClick(event) {
    const b = event.target.closest('button[data-act]');
    if (!b) return;
    const id = b.closest('[data-id]')?.dataset.id;
    const list = load();
    const t = list.find((x) => x.id === id);
    if (b.dataset.act === 'new') { this.ask(); return; }
    if (!t) return;
    if (b.dataset.act === 'pause') {
      if (t.pausedLeft !== undefined && t.pausedLeft !== null) { t.endsAt = Date.now() + t.pausedLeft * 1000; t.pausedLeft = null; }
      else t.pausedLeft = left(t);
    } else if (b.dataset.act === 'plus') {
      if (t.pausedLeft !== undefined && t.pausedLeft !== null) t.pausedLeft += 60;
      else t.endsAt = Math.max(t.endsAt, Date.now()) + 60000;
      t.fired = false;
    } else if (b.dataset.act === 'stop') {
      list.splice(list.indexOf(t), 1);
    }
    save(list);
    this.render();
  }

  tick() {
    const list = load();
    let changed = false;
    let ringing = false;
    for (const t of list) {
      if (left(t) === 0 && !t.fired && (t.pausedLeft === undefined || t.pausedLeft === null)) {
        t.fired = true;
        changed = true;
        ring();
        try {
          if ('Notification' in window && Notification.permission === 'granted') new Notification(`⏱ ${t.label}`, { body: 'Time is up.', tag: t.id });
        } catch (_e) { /* ignored */ }
      }
      if (t.fired && left(t) === 0) ringing = true;
    }
    if (changed) save(list);
    document.title = ringing ? `⏱ Time is up — ${this.titleBase}` : this.titleBase;
    for (const row of this.el.querySelectorAll('[data-id]')) {
      const t = list.find((x) => x.id === row.dataset.id);
      if (!t) continue;
      row.querySelector('.nb-timer-left').textContent = left(t) === 0 ? 'Done' : show(left(t));
      row.classList.toggle('is-done', left(t) === 0);
      const bar = row.querySelector('.nb-timer-bar i');
      if (bar) bar.style.width = `${Math.min(100, 100 * (1 - left(t) / (t.total || 1)))}%`;
    }
    if (list.length !== this.el.querySelectorAll('[data-id]').length) this.render();
  }

  render() {
    const list = load();
    this.el.hidden = !list.length && !this.showAdd;
    this.el.innerHTML = list.map((t) => {
      const paused = t.pausedLeft !== undefined && t.pausedLeft !== null;
      return `<div class="nb-timer${left(t) === 0 ? ' is-done' : ''}" data-id="${escapeHtml(t.id)}">
        <div class="nb-timer-main"><span class="nb-timer-label" title="${escapeHtml(t.label)}">${escapeHtml(t.label)}</span><span class="nb-timer-left">${left(t) === 0 ? 'Done' : show(left(t))}</span></div>
        <div class="nb-timer-bar"><i></i></div>
        <div class="nb-timer-actions">
          ${left(t) > 0 ? `<button type="button" data-act="pause">${paused ? 'Resume' : 'Pause'}</button>` : ''}
          <button type="button" data-act="plus">+1 min</button>
          <button type="button" data-act="stop">${left(t) === 0 ? 'Dismiss' : 'Cancel'}</button>
        </div>
      </div>`;
    }).join('') + (list.length ? '<button type="button" class="nb-timer-new" data-act="new">+ Timer</button>' : '');
    this.tick();
  }

  // A timer of any length, from the toolbar or the tray.
  async ask() {
    const raw = await ask.prompt('Timer — how many minutes?', '5', { placeholder: '5, 1.5, or 1:30 for 1 h 30 min', okLabel: 'Next' });
    if (!raw) return;
    const parts = raw.split(':').map(Number);
    const minutes = parts.length === 2 ? parts[0] * 60 + parts[1] : parts[0];
    if (!(minutes > 0)) return;
    const label = (await ask.prompt('What for?', 'Timer', { okLabel: 'Start timer' })) || 'Timer';
    this.start(label, minutes * 60);
  }
}

let tray = null;
export function timers() {
  if (!tray) tray = new TimerTray();
  return tray;
}


export const StepTimers = Extension.create({
  name: 'stepTimers',
  addProseMirrorPlugins() {
    const build = (doc) => {
      const decos = [];
      doc.descendants((node, pos) => {
        if (!node.isTextblock || node.type.name === 'codeBlock') return true;
        const text = node.textContent;
        for (const d of findDurations(text)) {
          // Map the offset in the block's text to a document position.
          let offset = 0;
          let at = null;
          node.forEach((child, childOffset) => {
            if (at !== null) return;
            const len = child.isText ? child.text.length : (child.textContent || '').length;
            if (d.index + d.length <= offset + len) at = pos + 1 + childOffset + (d.index + d.length - offset);
            offset += len;
          });
          if (at === null) continue;
          const label = timerLabel(text, d.index, d.index + d.length);
          decos.push(Decoration.widget(at, () => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'nb-timer-chip';
            b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M10 2h4"/></svg>';
            b.title = `Start a ${d.text} timer`;
            b.setAttribute('aria-label', `Start a ${d.text} timer`);
            b.addEventListener('mousedown', (e) => e.preventDefault());
            b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); timers().start(label, d.seconds); });
            return b;
          }, { side: 1, key: `timer-${at}-${d.seconds}`, ignoreSelection: true }));
        }
        return false;
      });
      return DecorationSet.create(doc, decos);
    };
    return [new Plugin({
      key: new PluginKey('stepTimers'),
      state: {
        init: (_c, state) => build(state.doc),
        apply: (tr, old) => (tr.docChanged ? build(tr.doc) : old),
      },
      props: { decorations(state) { return this.getState(state); } },
    })];
  },
});
