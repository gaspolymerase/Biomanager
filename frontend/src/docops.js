// Edits the notebook makes on its own: a timestamped line under a heading
// ("## Log" in a daily page, "## Deviations" in an experiment), a time
// stamp at the caret, a tick with the time on a protocol step.

import { clock } from './util.js';

function textNodes(parts) {
  return parts.filter((p) => p.text).map((p) => ({ type: 'text', text: p.text, ...(p.bold ? { marks: [{ type: 'bold' }] } : {}) }));
}

// Where the section under the first heading matching `re` ends, and
// whether it ends in a bullet list (to add to that list rather than start
// a new one). null when there is no such heading.
function sectionEnd(doc, re) {
  let heading = null;
  let end = null;
  let lastChild = null;
  doc.forEach((node, offset) => {
    if (end !== null) return;
    if (node.type.name === 'heading') {
      if (heading && node.attrs.level <= heading.level) { end = offset; return; }
      if (!heading && re.test(node.textContent)) { heading = { level: node.attrs.level }; lastChild = null; return; }
    }
    if (heading) lastChild = { node, offset };
  });
  if (!heading) return null;
  if (end === null) end = doc.content.size;
  // Trailing empty paragraphs belong to the gap before the next heading.
  let list = null;
  if (lastChild && lastChild.node.type.name === 'bulletList') list = lastChild;
  return { end, list };
}

// Add "**HH:MM** text" as a bullet under the heading (made at the end of
// the page if missing).
export function appendLogLine(editor, headingRe, headingText, text, { level = 2, time = clock() } = {}) {
  const { state } = editor;
  const item = {
    type: 'listItem',
    content: [{ type: 'paragraph', content: textNodes([{ text: time, bold: true }, { text: ` ${text}` }]) }],
  };
  const where = sectionEnd(state.doc, headingRe);
  if (where && where.list) {
    const insertAt = where.list.offset + where.list.node.nodeSize - 1;
    editor.chain().insertContentAt(insertAt, item).run();
    return;
  }
  const list = { type: 'bulletList', content: [item] };
  if (where) {
    editor.chain().insertContentAt(where.end, list).run();
    return;
  }
  editor.chain().insertContentAt(state.doc.content.size, [
    { type: 'heading', attrs: { level }, content: [{ type: 'text', text: headingText }] },
    list,
  ]).run();
}

export function stampTime(editor) {
  const now = new Date();
  editor.chain().focus().insertContent([{ type: 'text', text: clock(now), marks: [{ type: 'bold' }] }, { type: 'text', text: ' ' }]).run();
}

// Protocol steps: every task item in the page, in order.
export function taskItems(doc) {
  const items = [];
  doc.descendants((node, pos) => {
    if (node.type.name === 'taskItem') {
      const para = node.firstChild;
      items.push({ pos, checked: !!node.attrs.checked, text: para ? para.textContent : node.textContent, node });
      return false;
    }
    return true;
  });
  return items;
}

export function checkStep(editor, pos, checked, { stamp = true } = {}) {
  const { state } = editor;
  const node = state.doc.nodeAt(pos);
  if (!node || node.type.name !== 'taskItem') return;
  let tr = state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, checked });
  const para = node.firstChild;
  if (checked && stamp && para && para.isTextblock) {
    const end = pos + 1 + para.nodeSize - 1;
    const mark = state.schema.marks.italic;
    const text = state.schema.text(` — ✓ ${clock()}`, mark ? [mark.create()] : []);
    tr = tr.insert(end, text);
  }
  editor.view.dispatch(tr);
}
