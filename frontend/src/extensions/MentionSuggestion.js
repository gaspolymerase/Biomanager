// `@` trigger for entity suggestions. Two modes:
//
//   1. Typed:   "@mouse 123" / "@plasmid kan" / "@order 5" / "@antibodies gfp"
//                — fetches /notebook/search/<type>?q=<q> and shows results
//                  for just that type. Picker keeps the explicit type.
//
//   2. Unified: "@" / "@123" / "@DBH-Cre"
//                — fetches /notebook/search/all?q=<q> which merges mouse +
//                  plasmid + order results (and, once something is typed,
//                  every inventory's). Each item carries its own
//                  `type`. Picker inserts `@<type> <id>` so the
//                  MentionDecoration plugin still styles the chip.
//
// The decoration plugin's regex (in MentionDecoration.js) only highlights
// `@<type> <id>` strings, so picking from either mode produces a chip.

import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';

import { mentionTypes, styleOf, typedTriggerRe } from './mentionTypes.js';

// Unified trigger: `@` followed by a single word-token (no space). Stops at
// punctuation/whitespace so the menu closes naturally when the user types
// past the entity reference.
// What follows @ while typing: letters of any script (anti-β), digits and
// the - / . a name or catalogue number holds (Waf1/Cip1, 12D1.2).
const UNIFIED_TRIGGER_RE = /@([\p{L}\p{N}_\-/.]*)$/u;

class SuggestionMenu {
  constructor() {
    this.el = document.createElement('div');
    this.el.className = 'entity-suggestion';
    this.el.style.display = 'none';
    document.body.appendChild(this.el);
    this.items = [];
    this.activeIndex = 0;
    this.onPick = null;
  }

  show(items, coords, onPick) {
    this.items = items;
    this.activeIndex = 0;
    this.onPick = onPick;
    this.render();
    this.el.style.left = `${coords.left}px`;
    this.el.style.top = `${coords.top}px`;
    this.el.style.display = items.length ? 'block' : 'none';
  }

  hide() {
    this.el.style.display = 'none';
    this.items = [];
    this.onPick = null;
  }

  render() {
    this.el.innerHTML = '';
    this.items.forEach((item, idx) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'entity-suggestion-row' + (idx === this.activeIndex ? ' active' : '');
      // If the item carries its own type (unified search), prefix the row
      // with a small colored tag so the user knows which database they're
      // pointing at. Type-specific searches omit the tag since context is
      // already clear.
      if (item.type) {
        const tag = document.createElement('span');
        tag.className = `entity-suggestion-tag entity-suggestion-tag-${styleOf(item.type)}`;
        tag.textContent = item.type_label || mentionTypes().labels[item.type] || item.type;
        row.appendChild(tag);
      }
      const label = document.createElement('span');
      label.className = 'entity-suggestion-label';
      label.textContent = item.label;
      row.appendChild(label);
      row.addEventListener('mousedown', (event) => {
        event.preventDefault();
        if (this.onPick) this.onPick(item);
      });
      this.el.appendChild(row);
    });
  }

  move(delta) {
    if (!this.items.length) return;
    this.activeIndex = (this.activeIndex + delta + this.items.length) % this.items.length;
    this.render();
  }

  pickActive() {
    if (!this.items.length || !this.onPick) return false;
    this.onPick(this.items[this.activeIndex]);
    return true;
  }

  isOpen() {
    return this.el.style.display !== 'none';
  }
}

export const MentionSuggestion = Extension.create({
  name: 'mentionSuggestion',

  addProseMirrorPlugins() {
    const menu = new SuggestionMenu();
    let pendingFetch = null;
    let lastQuery = null;

    function getTriggerContext(state) {
      const { $from } = state.selection;
      if (!$from.parent.isTextblock) return null;
      const textBefore = $from.parent.textBetween(0, $from.parentOffset, '\n', '\0');
      // Try the typed form first. If the user has written "@mouse foo" we
      // want to show only mouse results, not unified ones.
      const typedMatch = textBefore.match(typedTriggerRe());
      if (typedMatch) {
        return {
          mode: 'typed',
          type: typedMatch[1],
          query: typedMatch[2] || '',
          triggerStart: $from.pos - typedMatch[0].length,
          triggerEnd: $from.pos,
        };
      }
      const unifiedMatch = textBefore.match(UNIFIED_TRIGGER_RE);
      if (unifiedMatch) {
        return {
          mode: 'unified',
          type: null,
          query: unifiedMatch[1] || '',
          triggerStart: $from.pos - unifiedMatch[0].length,
          triggerEnd: $from.pos,
        };
      }
      return null;
    }

    function getCaretCoords(view) {
      const coords = view.coordsAtPos(view.state.selection.from);
      return {
        top: coords.bottom + window.scrollY + 6,
        left: coords.left + window.scrollX,
      };
    }

    function closeMenu() {
      menu.hide();
      lastQuery = null;
      if (pendingFetch && pendingFetch.controller) pendingFetch.controller.abort();
      pendingFetch = null;
    }

    return [
      new Plugin({
        key: new PluginKey('mentionSuggestion'),
        view() {
          return {
            update(view) {
              const ctx = getTriggerContext(view.state);
              if (!ctx) {
                closeMenu();
                return;
              }
              const cacheKey = `${ctx.mode}:${ctx.type || ''}:${ctx.query}`;
              if (cacheKey === lastQuery && menu.isOpen()) return;
              lastQuery = cacheKey;
              if (pendingFetch && pendingFetch.controller) pendingFetch.controller.abort();
              const controller = new AbortController();
              pendingFetch = { controller };
              const endpoint = ctx.mode === 'typed' ? ctx.type : 'all';
              const url = `/notebook/search/${endpoint}?q=${encodeURIComponent(ctx.query)}`;
              fetch(url, { signal: controller.signal })
                .then((r) => (r.ok ? r.json() : { ok: false, items: [] }))
                .then((data) => {
                  if (!data || !data.ok) return;
                  const coords = getCaretCoords(view);
                  menu.show(data.items || [], coords, (item) => {
                    // In typed mode the type came from the text the user
                    // already wrote; in unified mode each item carries it.
                    const insertType = ctx.mode === 'typed' ? ctx.type : item.type;
                    if (!insertType) return;
                    // A person is "@jordan" (action items and mentions); a
                    // record is "@<type> <number>", which becomes a chip.
                    // A database: its word, and the menu goes on with its records.
                    const text = insertType === 'person' || insertType === 'database' ? `@${item.id} ` : `@${insertType} ${item.id} `;
                    const tr = view.state.tr.insertText(text, ctx.triggerStart, ctx.triggerEnd);
                    view.dispatch(tr);
                    if (insertType !== 'database') closeMenu();
                    view.focus();
                  });
                })
                .catch(() => {});
            },
            destroy() {
              closeMenu();
              if (menu.el && menu.el.parentNode) menu.el.parentNode.removeChild(menu.el);
            },
          };
        },
        props: {
          handleKeyDown(view, event) {
            if (!menu.isOpen()) return false;
            if (event.key === 'ArrowDown') { menu.move(1); event.preventDefault(); return true; }
            if (event.key === 'ArrowUp') { menu.move(-1); event.preventDefault(); return true; }
            if (event.key === 'Enter' || event.key === 'Tab') {
              if (menu.pickActive()) { event.preventDefault(); return true; }
            }
            if (event.key === 'Escape') { closeMenu(); event.preventDefault(); return true; }
            return false;
          },
        },
      }),
    ];
  },
});
