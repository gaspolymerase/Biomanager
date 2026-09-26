// Text-drawn blocks: Mermaid diagrams (flowcharts, sequence, Gantt,
// timelines…), mind maps written as an indented list, and display math in
// LaTeX. The source is the block's content; it renders as you type, and
// clicking the drawing opens the source again.

import { debounce, el, escapeHtml } from '../util.js';
import { katex, mermaid } from '../vendor.js';

let counter = 0;

// "- Root\n  - Child\n    - Grandchild" → Mermaid mindmap syntax. Node
// text goes in quotes so brackets and punctuation cannot break the parser.
export function listToMindmap(src) {
  const lines = String(src || '').split('\n').filter((l) => l.trim());
  if (!lines.length) return '';
  const items = lines.map((line) => {
    const indent = line.match(/^\s*/)[0].replace(/\t/g, '  ').length;
    const text = line.trim().replace(/^([-*+]|\d+[.)])\s+/, '').replace(/"/g, "'").replace(/[`]/g, "'");
    return { indent, text };
  });
  const levels = [...new Set(items.map((i) => i.indent))].sort((a, b) => a - b);
  const out = ['mindmap'];
  items.forEach((item, i) => {
    const depth = i === 0 ? 0 : Math.max(1, levels.indexOf(item.indent));
    const shape = depth === 0 ? `root(("${item.text}"))` : `n${i}["${item.text}"]`;
    out.push('  '.repeat(depth + 1) + shape);
  });
  return out.join('\n');
}

const SAMPLES = {
  mermaid: 'flowchart LR\n  A[Transfect] --> B{GFP+?}\n  B -- yes --> C[Sort]\n  B -- no --> D[Discard]\n  C --> E[Expand]',
  mindmap: '- Project\n  - Aim 1\n    - Experiment A\n    - Experiment B\n  - Aim 2\n    - Collaborators\n  - Open questions',
  math: 'C_1 V_1 = C_2 V_2',
};

export function defaultDiagram(kind) {
  return SAMPLES[kind] || '';
}

export function mountDiagram(host, ctx) {
  const kind = ctx.kind;
  let source = typeof ctx.data === 'string' ? ctx.data : '';
  let editing = ctx.editable && !source.trim();
  const commit = debounce(() => ctx.commit(source), 400);
  const root = el('div', { class: `nb-diagram nb-diagram-${kind}` });
  host.appendChild(root);
  const view = el('div', { class: 'nb-diagram-view', title: ctx.editable ? 'Click to edit' : '' });
  const editor = el('div', { class: 'nb-diagram-editor' });
  const textarea = el('textarea', { spellcheck: 'false', rows: kind === 'math' ? 2 : 6 });
  const help = el('div', { class: 'nb-muted nb-diagram-help', html: kind === 'mermaid'
    ? 'Mermaid: <code>flowchart</code>, <code>sequenceDiagram</code>, <code>gantt</code>, <code>timeline</code>, <code>pie</code>…'
    : kind === 'mindmap' ? 'One idea per line; indent to branch.' : 'LaTeX, e.g. <code>\\frac{a}{b}</code>, <code>\\Delta\\Delta C_t</code>, <code>\\pm</code>' });
  const done = el('button', { type: 'button', class: 'nb-mini', text: 'Done' });
  editor.append(textarea, el('div', { class: 'nb-diagram-foot' }, [help, done]));
  root.append(view, editor);

  const draw = debounce(async () => {
    const src = source.trim();
    if (!src) {
      view.innerHTML = `<div class="nb-muted nb-diagram-empty">${kind === 'math' ? 'Empty equation' : 'Empty diagram'}${ctx.editable ? ' — click to write it' : ''}</div>`;
      return;
    }
    try {
      if (kind === 'math') {
        const k = await katex();
        view.innerHTML = k.renderToString(src, { displayMode: true, throwOnError: false, strict: 'ignore', trust: false });
      } else {
        const m = await mermaid();
        const text = kind === 'mindmap' ? listToMindmap(src) : src;
        const id = `nb-mermaid-${Date.now()}-${counter++}`;
        const { svg } = await m.render(id, text);
        view.innerHTML = svg; // mermaid removes its own scratch element
      }
      view.classList.remove('has-error');
    } catch (e) {
      view.classList.add('has-error');
      view.innerHTML = `<div class="nb-warn">${escapeHtml(String(e && e.message ? e.message : e).split('\n')[0].slice(0, 240))}</div><pre class="nb-diagram-src">${escapeHtml(src)}</pre>`;
    }
  }, 250);

  function sync() {
    editor.hidden = !editing;
    root.classList.toggle('is-editing', editing);
    if (editing && textarea.value !== source) textarea.value = source;
  }

  view.addEventListener('click', () => {
    if (!ctx.editable || editing) return;
    editing = true;
    sync();
    textarea.focus();
  });
  done.addEventListener('click', () => { editing = false; commit.flush(); sync(); });
  textarea.addEventListener('input', () => { source = textarea.value; commit(); draw(); });
  textarea.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' || ((event.metaKey || event.ctrlKey) && event.key === 'Enter')) {
      event.preventDefault();
      editing = false;
      commit.flush();
      sync();
    }
  });

  sync();
  draw.now();
  return {
    update(next) {
      source = typeof next === 'string' ? next : '';
      if (document.activeElement !== textarea) textarea.value = source;
      draw();
    },
    focus() { if (ctx.editable) { editing = true; sync(); textarea.focus(); } },
    destroy() { commit.flush(); },
  };
}
