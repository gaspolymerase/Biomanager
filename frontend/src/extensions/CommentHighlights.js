// Highlights the passages comments were made on. Comments keep the quoted
// text rather than a position, so they survive any edit elsewhere: the
// first place the quote appears is marked, and clicking it opens its
// thread. Set the list with editor.commands.setCommentQuotes([{ id, quote }]).

import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

const key = new PluginKey('commentHighlights');

function findQuote(doc, quote) {
  const needle = quote.trim();
  if (!needle) return null;
  let found = null;
  doc.descendants((node, pos) => {
    if (found) return false;
    if (!node.isTextblock) return true;
    const text = node.textContent;
    const at = text.indexOf(needle);
    if (at < 0) return false;
    // Offsets in the text → positions, walking the block's children.
    let offset = 0;
    let from = null;
    let to = null;
    node.forEach((child, childOffset) => {
      const len = child.isText ? child.text.length : 0;
      const start = pos + 1 + childOffset;
      if (from === null && at < offset + len) from = start + (at - offset);
      if (to === null && at + needle.length <= offset + len) to = start + (at + needle.length - offset);
      offset += child.isText ? len : 0;
    });
    if (from !== null && to !== null) found = { from, to };
    return false;
  });
  return found;
}

export const CommentHighlights = Extension.create({
  name: 'commentHighlights',

  addOptions() {
    return { onOpen: null };
  },

  addCommands() {
    return {
      setCommentQuotes: (quotes) => ({ tr, dispatch }) => {
        if (dispatch) tr.setMeta(key, quotes || []);
        tr.setMeta('addToHistory', false);
        return true;
      },
    };
  },

  addProseMirrorPlugins() {
    const onOpen = this.options.onOpen;
    const build = (doc, quotes) => DecorationSet.create(doc, quotes.map((q) => {
      const range = findQuote(doc, q.quote || '');
      return range ? Decoration.inline(range.from, range.to, { class: 'nb-comment-mark', 'data-comment': String(q.id) }) : null;
    }).filter(Boolean));
    return [new Plugin({
      key,
      state: {
        init: () => ({ quotes: [], decos: DecorationSet.empty }),
        apply(tr, value) {
          const quotes = tr.getMeta(key);
          if (quotes) return { quotes, decos: build(tr.doc, quotes) };
          if (tr.docChanged) return { quotes: value.quotes, decos: build(tr.doc, value.quotes) };
          return value;
        },
      },
      props: {
        decorations(state) { return key.getState(state).decos; },
        handleClick(_view, _pos, event) {
          const mark = event.target && event.target.closest && event.target.closest('.nb-comment-mark');
          if (mark && onOpen) { onOpen(Number(mark.dataset.comment)); return false; }
          return false;
        },
      },
    })];
  },
});
